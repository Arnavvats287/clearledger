"""Add proposal-only advanced matching outcomes; preserve immutable history."""

from alembic import op

revision = "0004_advanced_matching"
down_revision = "0003_exact_matching"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_matching_proposal_outcome", "matching_proposals", type_="check")
    op.create_check_constraint(
        "ck_matching_proposal_outcome",
        "matching_proposals",
        "outcome IN ('EXACT_MATCH','AMBIGUOUS','NO_SUPPORTED_MATCH',"
        "'UNIQUE','UNRESOLVED','SEARCH_INCOMPLETE')",
    )


def downgrade():
    # PostgreSQL rejects this downgrade if newer outcomes exist: never delete/rewrite history.
    op.drop_constraint("ck_matching_proposal_outcome", "matching_proposals", type_="check")
    op.create_check_constraint(
        "ck_matching_proposal_outcome",
        "matching_proposals",
        "outcome IN ('EXACT_MATCH','AMBIGUOUS','NO_SUPPORTED_MATCH')",
    )
