"""avisos_descartados en item_lista_oficial

Revision: 9f3c8d5b1a24
Anterior: 8e2b7c4a9f13
Fecha:    2026-10-07 19:00:00.000000+00:00

Por que este cambio: la pagina de un grado ahora muestra avisos sobre sus
renglones (posible repetido, atributo que no se pudo exigir, sin producto que
cumpla). Cuando el revisor decide que un aviso no aplica ("son distintos"),
esa decision tiene que quedar en el RENGLON —es sobre lo que el colegio
escribio, no sobre un kit— y viajar con la curaduria a otras maquinas, para
que el aviso no vuelva a salir. Una lista de claves (`repetido:61`,
`revisar:forma`, `sin_producto`), vacia por omision.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "9f3c8d5b1a24"
down_revision: str | None = "8e2b7c4a9f13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("item_lista_oficial") as batch:
        batch.add_column(
            sa.Column(
                "avisos_descartados",
                sa.JSON().with_variant(JSONB(), "postgresql"),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("item_lista_oficial") as batch:
        batch.drop_column("avisos_descartados")
