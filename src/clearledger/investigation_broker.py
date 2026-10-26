"""Trusted evidence boundary; the provider receives only projected, bounded DTOs."""

from sqlalchemy.orm import Session

from clearledger.case_domain import CaseError
from clearledger.evidence_contract import ScopeInput, SearchInput, VerifyInput
from clearledger.evidence_reader import EvidenceReader, begin_readonly
from clearledger.investigation_contract import OfferedPointer


def offered(hit):
    if (
        hit.record_type != "DOCUMENT_EVIDENCE"
        or not hit.source_integrity
        or not hit.is_current
        or hit.metadata.get("privacy_review_required")
    ):
        return None
    return OfferedPointer(
        record_id=hit.id,
        document_id=hit.document_id,
        document_version=hit.document_version,
        raw_sha256=hit.raw_sha256,
        canonical_sha256=hit.canonical_sha256,
        page=hit.page,
        start=hit.start,
        end=hit.end,
        excerpt=hit.excerpt,
    )


class Broker:
    def __init__(self, engine, org, case_id, snapshot, settings):
        self.engine, self.org, self.case_id = engine, org, case_id
        self.snapshot, self.settings = snapshot, settings

    def scope(self, objective):
        return ScopeInput(
            expected_case_version=self.snapshot["case_version"],
            expected_context_sha256=self.snapshot["context_sha256"],
            customer_id=self.snapshot["customer_id"],
            claim_id=objective.claim_id,
            invoice_id=objective.invoice_id,
        )

    def search(self, objective, tool):
        if tool not in objective.tools:
            raise CaseError("TOOL_NOT_ALLOWED", 403)
        with Session(self.engine) as session:
            begin_readonly(session, self.org)
            reader = EvidenceReader(session, self.org, self.settings)
            return reader.search(
                self.case_id, SearchInput(**self.scope(objective).model_dump(), tool=tool, limit=20)
            )

    def verify(self, objective, proposal, permitted):
        if any(pointer not in permitted for pointer in proposal.citations):
            raise CaseError("FORGED_CITATION")
        if objective.invoice_id is None:
            return None, []
        with Session(self.engine) as session:
            begin_readonly(session, self.org)
            reader = EvidenceReader(session, self.org, self.settings)
            scope = self.scope(objective)
            citations = [
                reader.pointer(self.case_id, p.record_id, scope).citation
                for p in proposal.citations
            ]
            result = reader.verify(
                self.case_id,
                VerifyInput(**scope.model_dump(), question=objective.question, citations=citations),
            )
            # Include independently discovered contradictory/required records too.
            identifiers = {i for finding in result.findings for i in finding.record_ids}
            if "UNCERTAIN_EXTRACTION" in objective.unknowns:
                # The verifier deliberately abstains before predicates in this case.
                # Retain scoped, independently rechecked source pointers for human
                # review without removing uncertainty or granting factual support.
                identifiers.update(p.record_id for p in proposal.citations)
            if len(identifiers) > 20:
                raise CaseError("TOOL_LIMIT")
            visible = []
            for identifier in sorted(identifiers):
                record = reader.pointer(self.case_id, identifier, scope)
                from clearledger.evidence_models import EvidenceRecord
                from clearledger.matching import owned

                pointer = offered(
                    reader.document_hit(owned(session, EvidenceRecord, self.org, record.id))
                )
                if pointer is None:
                    raise CaseError("EVIDENCE_PRIVACY_FAILURE")
                visible.append(pointer)
            return result, visible
