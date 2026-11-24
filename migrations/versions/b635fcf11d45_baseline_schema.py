"""baseline schema

Revision ID: b635fcf11d45
Revises:
Create Date: 2026-11-24 13:13:12.518374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b635fcf11d45'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category", sa.Text),
        sa.Column("price", sa.Numeric(10, 2)),
        sa.Column("description", sa.Text),
        sa.Column("is_organic", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("credit_card_number", sa.Text, nullable=False),  # temporary, replaced in Phase 2
        sa.Column("location", sa.Text, nullable=False),
        sa.Column("age", sa.Integer, nullable=False),
        sa.UniqueConstraint("email", name="uq_customers_email"),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("reviewer_name", sa.Text),
        sa.Column("review_text", sa.Text),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
    )
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "ordered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("customers")
    op.drop_table("products")
