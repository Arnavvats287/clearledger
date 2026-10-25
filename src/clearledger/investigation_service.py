"""Scoped request/snapshot lifecycle, never exposed to the Investigator."""

from sqlalchemy import select

from clearledger.case_domain import CaseError
from clearledger.case_events import publish
from clearledger.case_models import Claim, ClaimSource
from clearledger.case_repository import members, root, scoped
from clearledger.case_sources import claim_basis, current_context, extraction_facts
from clearledger.evidence_runtime import EvidenceOriginals
from clearledger.investigation_contract import ALGORITHM, Objective, RunView
from clearledger.investigation_director import PRIMARY, SEARCH
from clearledger.investigation_models import (
    Investigation,
    InvestigationFinding,
    InvestigationInvalidation,
    InvestigationRequest,
)
from clearledger.matching import digest, lock_company, owned
from clearledger.models import DocumentExtraction, Invoice


def configuration(settings, provider):
    return digest(
        {
            "algorithm": ALGORITHM,
            "provider": provider,
            "model": settings.gemini_model,
            "enabled": settings.external_ai_enabled,
            "workflow_enabled": settings.investigation_external_enabled,
            "rates": [
                settings.llm_input_paise_per_million_tokens,
                settings.llm_output_paise_per_million_tokens,
            ],
            "token_limits": [settings.llm_max_input_tokens, settings.llm_max_output_tokens],
            "attempts": settings.llm_attempts,
            "trust": settings.evidence_trusted_sources_json.get_secret_value()
            if settings.evidence_trusted_sources_json
            else None,
            "review": settings.privacy_review_reference,
        }
    )


def snapshot(session, org, case, body, settings, provider):
    store = EvidenceOriginals(settings.document_root)
    context = current_context(session, org, case, store)
    if (
        case.version != body.expected_case_version
        or case.context_sha256 != body.expected_context_sha256
        or digest(context) != case.context_sha256
    ):
        raise CaseError("STALE_INVESTIGATION_INPUTS")
    if len(body.claim_ids) > settings.investigation_limits.max_claims:
        raise CaseError("INVESTIGATION_CLAIM_LIMIT", 422)
    ids = members(session, org, case)
    objectives = []
    for identifier in sorted(body.claim_ids):
        claim = owned(session, Claim, org, identifier)
        if claim.case_id not in ids:
            raise CaseError("CLAIM_OUTSIDE_INVESTIGATION_CASE", 404)
        if claim.state == "RESOLVED":
            raise CaseError("CLAIM_ALREADY_RESOLVED")
        unknowns, numbers = [], set()
        if case.customer_id is None:
            unknowns.append("UNKNOWN_CUSTOMER")
        if claim.amount_paise is None:
            unknowns.append("UNKNOWN_AMOUNT")
        sources = list(
            session.scalars(
                select(ClaimSource)
                .where(ClaimSource.organization_id == org, ClaimSource.claim_id == claim.id)
                .limit(101)
            )
        )
        if len(sources) > 100:
            raise CaseError("INVESTIGATION_SOURCE_BUDGET")
        latest = session.scalar(
            select(DocumentExtraction)
            .where(
                DocumentExtraction.organization_id == org,
                DocumentExtraction.document_id == claim.document_id,
            )
            .order_by(DocumentExtraction.extraction_version.desc())
            .limit(1)
        )
        active = [s for s in sources if latest and s.extraction_id == latest.id]
        if active:
            _, facts = extraction_facts(session, org, latest, store)
            if facts:
                numbers = {r.value for r in facts.invoice_references}
                if facts.uncertainty != "none":
                    unknowns.append("UNCERTAIN_EXTRACTION")
            else:
                unknowns.append("UNCERTAIN_EXTRACTION")
        else:
            unknowns.append("UNCERTAIN_EXTRACTION")
        invoice = None
        if len(numbers) == 1 and case.customer_id:
            invoice = session.scalar(
                select(Invoice).where(
                    Invoice.organization_id == org,
                    Invoice.customer_id == case.customer_id,
                    Invoice.invoice_number == next(iter(numbers)),
                )
            )
        if invoice is None:
            unknowns.append("AMBIGUOUS_INVOICE")
        question = PRIMARY[claim.category]
        tools = ["get_invoice_evidence", "get_remittance_evidence", *SEARCH[question]]
        objectives.append(
            Objective(
                claim_id=claim.id,
                claim_version=claim.version,
                category=claim.category,
                amount_paise=claim.amount_paise,
                basis_sha256=claim_basis(session, org, case, claim, store, context=context),
                invoice_id=invoice.id if invoice else None,
                question=question,
                tools=tools,
                unknowns=sorted(set(unknowns)),
            )
        )
    from clearledger.evidence_models import EvidenceRecord

    source_kinds = set(
        session.scalars(
            select(EvidenceRecord.kind)
            .where(
                EvidenceRecord.organization_id == org,
                EvidenceRecord.customer_id == case.customer_id,
            )
            .distinct()
        )
    )
    return {
        "case_id": str(case.id),
        "case_version": case.version,
        "context_sha256": case.context_sha256,
        "customer_id": str(case.customer_id) if case.customer_id else None,
        "objectives": [o.model_dump(mode="json") for o in objectives],
        "limits": settings.investigation_limits.model_dump(),
        "provider": provider,
        "configuration_sha256": configuration(settings, provider),
        "allow_external": body.allow_external,
        "available_source_kinds": sorted(source_kinds),
        "algorithm": ALGORITHM,
        "model_id": settings.gemini_model if provider == "gemini" else None,
    }


def start(session, org, case_id, body, key, actor, settings, provider=None):
    lock_company(session, org)
    case = root(session, org, case_id)
    if case.id != case_id:
        raise CaseError("CASE_MERGED_USE_CANONICAL_ID")
    mode = provider.name if provider else settings.investigation_provider
    if body.allow_external and not settings.investigation_external_enabled:
        raise CaseError("INVESTIGATION_EXTERNAL_DISABLED", 403)
    fingerprint = digest(
        {"case": str(case_id), "body": body.model_dump(mode="json"), "actor": actor}
    )
    prior = scoped(session, InvestigationRequest, org, idempotency_key=key)
    if prior:
        if prior.request_sha256 != fingerprint:
            raise CaseError("INVESTIGATION_IDEMPOTENCY_CONFLICT")
        return owned(session, Investigation, org, prior.run_id)
    state = snapshot(session, org, case, body, settings, mode)
    identity = digest(state)
    run = scoped(session, Investigation, org, input_sha256=identity)
    if run is None:
        run = Investigation(
            organization_id=org,
            case_id=case_id,
            source_case_version=case.version,
            input_sha256=identity,
            provider=mode,
            snapshot=state,
        )
        session.add(run)
        session.flush()
        publish(
            session,
            org,
            "investigation.requested",
            "case_id",
            case_id,
            actor,
            {"run_id": str(run.id)},
            key={"investigation": str(run.id)},
            case_version=case.version,
        )
    session.add(
        InvestigationRequest(
            organization_id=org,
            run_id=run.id,
            idempotency_key=key,
            request_sha256=fingerprint,
            actor_id=actor,
        )
    )
    session.commit()
    return run


def current(session, org, run, settings):
    case = root(session, org, run.case_id)
    if case.id != run.case_id or case.version not in {
        run.source_case_version,
        run.result_case_version,
    }:
        return False
    try:
        context = current_context(session, org, case, EvidenceOriginals(settings.document_root))
        return (
            digest(context) == run.snapshot["context_sha256"] == case.context_sha256
            and configuration(settings, run.provider) == run.snapshot["configuration_sha256"]
        )
    except Exception:
        return False


def view(session, org, run, settings):
    return RunView(
        id=run.id,
        case_id=run.case_id,
        version=run.version,
        status=run.status,
        recommendation=run.recommendation,
        source_case_version=run.source_case_version,
        result_case_version=run.result_case_version,
        input_sha256=run.input_sha256,
        provider=run.provider,
        is_stale=not current(session, org, run, settings),
        claim_ids=[o["claim_id"] for o in run.snapshot["objectives"]],
        tool_calls=run.tool_calls,
        provider_attempts=run.provider_attempts,
        reserved_input_tokens=run.reserved_input_tokens,
        reserved_output_tokens=run.reserved_output_tokens,
        reserved_cost_paise=run.reserved_cost_paise,
        error_code=run.error_code,
    )


def invalidate(session, org, case, affected, event):
    for finding in session.scalars(
        select(InvestigationFinding).where(
            InvestigationFinding.organization_id == org, InvestigationFinding.claim_id.in_(affected)
        )
    ):
        if (
            scoped(
                session, InvestigationInvalidation, org, finding_id=finding.id, event_id=event.id
            )
            is None
        ):
            session.add(
                InvestigationInvalidation(
                    organization_id=org, finding_id=finding.id, event_id=event.id
                )
            )


def finding_current(session, org, finding, settings):
    run = owned(session, Investigation, org, finding.run_id)
    if run.status not in {"COMPLETED", "AWAITING_REVIEW"}:
        return False
    if scoped(session, InvestigationInvalidation, org, finding_id=finding.id):
        return False
    if configuration(settings, run.provider) != run.snapshot["configuration_sha256"]:
        return False
    try:
        case = root(session, org, finding.case_id)
        claim = owned(session, Claim, org, finding.claim_id)
        return (
            claim_basis(session, org, case, claim, EvidenceOriginals(settings.document_root))
            == finding.basis_sha256
        )
    except Exception:
        return False


def schedule_affected(session, org, case, affected, settings, event_id):
    """Reinvestigate only already investigated affected claims, never unrelated claims."""
    from uuid import NAMESPACE_URL, uuid5

    from clearledger.investigation_contract import StartInput

    targets = set(
        session.scalars(
            select(InvestigationFinding.claim_id).where(
                InvestigationFinding.organization_id == org,
                InvestigationFinding.claim_id.in_(affected),
            )
        )
    )
    if not targets:
        return
    if len(targets) > settings.investigation_limits.max_claims:
        from clearledger.case_domain import CaseState, case_transition
        from clearledger.case_lifecycle import revise

        if case.state == "AWAITING_EVIDENCE":
            case_transition(CaseState(case.state), CaseState.INVESTIGATING)
            case.state = "INVESTIGATING"
            revise(
                session,
                org,
                case,
                "investigation-worker",
                "case.investigation_limit",
                EvidenceOriginals(settings.document_root),
                invalidate=False,
                enqueue=False,
            )
        if case.state == "INVESTIGATING":
            case_transition(CaseState(case.state), CaseState.AWAITING_REVIEW)
            case.state = "AWAITING_REVIEW"
            revise(
                session,
                org,
                case,
                "investigation-worker",
                "case.investigation_limit",
                EvidenceOriginals(settings.document_root),
                invalidate=False,
                enqueue=False,
            )
        publish(
            session,
            org,
            "investigation.limit_reached",
            "case_id",
            case.id,
            "investigation-worker",
            {
                "code": "INVESTIGATION_CLAIM_LIMIT",
                "affected_claim_ids": sorted(str(i) for i in targets),
                "max_claims": settings.investigation_limits.max_claims,
                "recommendation": "AWAITING_REVIEW",
                "financial_authority": False,
            },
            key={"investigation_limit": str(event_id)},
            queued=False,
        )
        return
    body = StartInput(
        expected_case_version=case.version,
        expected_context_sha256=case.context_sha256,
        claim_ids=sorted(targets),
    )
    # Same transaction as reevaluation: no nested commit/outbox gap.
    state = snapshot(session, org, case, body, settings, "deterministic")
    identity = digest(state)
    run = scoped(session, Investigation, org, input_sha256=identity)
    if run is None:
        run = Investigation(
            organization_id=org,
            case_id=case.id,
            source_case_version=case.version,
            input_sha256=identity,
            provider="deterministic",
            snapshot=state,
        )
        session.add(run)
        session.flush()
        publish(
            session,
            org,
            "investigation.requested",
            "case_id",
            case.id,
            "investigation-worker",
            {"run_id": str(run.id)},
            key={"investigation": str(run.id)},
            case_version=case.version,
        )
    key = uuid5(NAMESPACE_URL, f"clearledger:investigate:{org}:{event_id}")
    if scoped(session, InvestigationRequest, org, idempotency_key=key) is None:
        session.add(
            InvestigationRequest(
                organization_id=org,
                run_id=run.id,
                idempotency_key=key,
                request_sha256=digest(state),
                actor_id="investigation-worker",
            )
        )
