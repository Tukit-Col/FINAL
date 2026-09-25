"""logo del colegio: String(1024) -> Text

Revision: 5c1a7e0d9b34
Anterior: 3799d5a32ad7
Fecha:    2026-09-25 00:01:00+00:00

Por que este cambio: el logo del colegio puede llegar como URL corta o como un
data-URI (`data:image/...;base64,...`) que el revisor pega o sube en el perfil
del partner; esos superan de largo `String(1024)` y el alta del colegio (el
poller de `colegio_verificado`) reventaba con StringDataRightTruncationError,
perdiendo el colegio en silencio. `Text` no tiene limite y es dato institucional
publico (sin PII), a diferencia del estudiante cifrado del mismo esquema.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "5c1a7e0d9b34"
down_revision: str | None = "3799d5a32ad7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "colegio",
        "logo_url",
        existing_type=sa.String(length=1024),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Puede truncar filas con data-URI; solo tiene sentido si no las hay.
    op.alter_column(
        "colegio",
        "logo_url",
        existing_type=sa.Text(),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )
