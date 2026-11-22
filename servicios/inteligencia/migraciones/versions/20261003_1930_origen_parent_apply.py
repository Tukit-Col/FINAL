from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "8a4d2f6c1b97"
down_revision: str | None = "5c1e8b7d2a64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NUEVO = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada', 'parent_apply')"


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_NUEVO))


def downgrade() -> None:
    pass
