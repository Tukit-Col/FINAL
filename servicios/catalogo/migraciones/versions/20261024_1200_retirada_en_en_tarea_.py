"""retirada_en en tarea_importacion

Revision: 5c1d8e2f7a90
Anterior: 3e7a1c9d5b62
Fecha:    2026-10-24 12:00:00.000000+00:00

Por que este cambio: cuando el acudiente cancela una lista que subio, el
catalogo le borra `contacto_referencia` y la version seguia en la cola de
verificacion como pendiente, ya sin nadie que la espere (H-07). Sin contacto no
se distingue de una importacion que nunca lo tuvo (onboarding), asi que la
cancelacion deja su fecha aqui y la cola la excluye. Nullable: las tareas de
antes y las que no se retiran no la traen.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "5c1d8e2f7a90"
down_revision: str | None = "3e7a1c9d5b62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table por las FK de la tabla: SQLite no soporta ALTER de
    # constraints y esta migracion se prueba tambien contra SQLite.
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("retirada_en", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("retirada_en")
