"""referencias en tarea_importacion

Revision: 7b4e2a9c1d36
Anterior: 5c1d8e2f7a90
Fecha:    2026-11-12 12:00:00.000000+00:00

Por que este cambio: el kit que se arma al aprobar la lista de un acudiente
tiene que llevar la referencia REAL del hijo que la subio (`hijo-2`...), porque
es la clave con la que el formulario guardo su personaje en
`personaje_por_hijo`. Antes el poller de Inteligencia la fijaba en `hijo-1`, y
con dos hermanos el kit salia neutral o con el personaje del otro. La
referencia viaja en la importacion, se guarda aqui y se reenvia en
`lista_verificada`. Nullable: las tareas de antes y el onboarding no la traen.
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "7b4e2a9c1d36"
down_revision: str | None = "5c1d8e2f7a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.add_column(sa.Column("referencias", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tarea_importacion") as batch:
        batch.drop_column("referencias")
