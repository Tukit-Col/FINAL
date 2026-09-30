"""perfil del colegio: logo, sitio y contactos

Revision: 3799d5a32ad7
Anterior: 3abe3d8e2e31
Fecha:    2026-09-23 04:51:38.794276+00:00

Por que este cambio: el colegio nacia con nombre, nit y activo, y el padre no
tenia como reconocer si su institucion ya es partner de Tukit. Se agrega el
perfil institucional —logo, sitio y contactos— que el administrador completa y
la tarjeta de partner muestra. Son datos de la INSTITUCION, no del menor: por
eso van en claro y nulables (los sembrados nacen sin perfil), a diferencia del
estudiante cifrado del Anexo M en el mismo esquema.
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
import sqlalchemy as sa
from alembic import op

revision: str = "3799d5a32ad7"
down_revision: str | None = "3abe3d8e2e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Las seis columnas del perfil, con su largo. Todas nulables: los colegios
# sembrados existen ya y nacen sin perfil, que se completa despues.
_COLUMNAS = (
    ("logo_url", 1024),
    ("sitio_web", 512),
    ("contacto_nombre", 256),
    ("contacto_email", 256),
    ("contacto_telefono", 64),
    ("direccion", 512),
)


def upgrade() -> None:
    for nombre, largo in _COLUMNAS:
        op.add_column("colegio", sa.Column(nombre, sa.String(length=largo), nullable=True))


def downgrade() -> None:
    for nombre, _ in reversed(_COLUMNAS):
        op.drop_column("colegio", nombre)
