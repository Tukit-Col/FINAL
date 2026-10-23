"""envio guarda localidad y place_id

Revision: b619c58fc0c3
Anterior: a58b45f8b14c
Fecha:    2026-10-10 14:00:00.000000+00:00

Por que este cambio: el checkout autocompleta la direccion con Google Places
(New) y pide la localidad de Bogota, para que la logistica agrupe el reparto
por localidad y el back-office abra el lugar exacto en Google Maps. Se guarda
el nombre canonico de la localidad y el `place_id` de Google; nunca
coordenadas (ADR 0044). Nullable: los pedidos ya escritos, los de fuera de
Bogota y las direcciones escritas a mano no los tienen.
"""

from __future__ import annotations

from collections.abc import Sequence

# `Vector` no es un tipo de SQLAlchemy sino de pgvector, asi que Alembic lo
# emite con el nombre completo y hace falta tenerlo importado. Se deja siempre,
# aunque la revision no lo use: que falte es un fallo en tiempo de migracion,
# que sobre no cuesta nada.
import pgvector.sqlalchemy  # noqa: F401

# `sa` y `op` van con noqa porque una revision legitima puede no usarlos: las
# que solo corren SQL a mano, o las de datos. Quitarlos de la plantilla
# obligaria a reponerlos a mano en las demas, que son la mayoria.
import sqlalchemy as sa  # noqa: F401
from alembic import op  # noqa: F401

revision: str = "b619c58fc0c3"
down_revision: str | None = "a58b45f8b14c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("envio", sa.Column("localidad", sa.String(length=64), nullable=True))
    op.add_column("envio", sa.Column("google_place_id", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("envio", "google_place_id")
    op.drop_column("envio", "localidad")
