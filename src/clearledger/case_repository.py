"""Company-scoped case graph and bounded queries; no workflow/policy decisions."""

from sqlalchemy import select

from clearledger.case_domain import CaseError
from clearledger.case_models import Case
from clearledger.matching import owned


def root(session, org, identifier):
    seen = set()
    while identifier not in seen and len(seen) < 64:
        seen.add(identifier)
        row = owned(session, Case, org, identifier)
        if row.merged_into_id is None:
            return row
        identifier = row.merged_into_id
    raise CaseError("CASE_GRAPH_LIMIT")


def members(session, org, case):
    found = {case.id}
    frontier = found.copy()
    while frontier:
        added = (
            set(
                session.scalars(
                    select(Case.id).where(
                        Case.organization_id == org, Case.merged_into_id.in_(frontier)
                    )
                )
            )
            - found
        )
        found.update(added)
        if len(found) > 256:
            raise CaseError("CASE_MEMBERSHIP_LIMIT")
        frontier = added
    return found


def scoped(session, model, org, **values):
    return session.scalar(
        select(model).where(
            model.organization_id == org,
            *(getattr(model, key) == value for key, value in values.items()),
        )
    )


def group_rows(session, model, org, member_ids, *, limit=2000):
    rows = list(
        session.scalars(
            select(model)
            .where(model.organization_id == org, model.case_id.in_(member_ids))
            .order_by(model.id)
            .limit(limit + 1)
        )
    )
    if len(rows) > limit:
        raise CaseError("CASE_ANALYSIS_LIMIT")
    return rows
