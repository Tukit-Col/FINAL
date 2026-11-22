from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "9a4b7c2e1d05"
down_revision: str | None = "3d8f5a1c9e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTERIOR = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada')"
_NUEVO = "origen IN ('colegio_grado', 'archivo', 'preview_onboarding', 'lista_verificada', 'parent_apply')"


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_NUEVO))


def downgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_constraint("trabajo_origen_valido", type_="check")
        batch.create_check_constraint("trabajo_origen_valido", sa.text(_ANTERIOR))
