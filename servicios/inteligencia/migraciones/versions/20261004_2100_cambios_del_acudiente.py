"""cambios del acudiente

Revision: 5c1e8a3f9b20
Anterior: 3f7b9e2d4c18
Fecha:    2026-10-04 21:00:00.000000+00:00

Por que este cambio: el acudiente ya puede cambiar un producto de su kit por
una de las alternativas de la linea. Sus cambios no se escriben en
`linea_kit` —esas lineas pueden ser el kit canonico del grado, el que reciben
los demas acudientes por la ruta rapida— sino en su propio trabajo, en
`cambios` (`{perfil: {item_id: producto}}`), y `ver` los aplica al leer.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5c1e8a3f9b20"
down_revision: str | None = "3f7b9e2d4c18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.add_column(
            sa.Column(
                "cambios",
                sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("trabajo_pipeline") as batch:
        batch.drop_column("cambios")
