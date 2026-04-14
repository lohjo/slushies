"""enforce one growth card per participant

Revision ID: c4a2f5df8a41
Revises: 1eabd5ee9d28
Create Date: 2026-04-14 14:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4a2f5df8a41"
down_revision = "1eabd5ee9d28"
branch_labels = None
depends_on = None


def upgrade():
    # Keep latest card per participant before adding uniqueness.
    op.execute(
        """
        DELETE FROM growth_cards
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY participant_id
                        ORDER BY generated_at DESC, id DESC
                    ) AS rn
                FROM growth_cards
            ) ranked
            WHERE ranked.rn > 1
        )
        """
    )

    with op.batch_alter_table("growth_cards", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_growth_cards_participant_id", ["participant_id"]
        )


def downgrade():
    with op.batch_alter_table("growth_cards", schema=None) as batch_op:
        batch_op.drop_constraint("uq_growth_cards_participant_id", type_="unique")
