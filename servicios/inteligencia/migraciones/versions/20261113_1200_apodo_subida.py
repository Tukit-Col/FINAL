"""apodo_subida: el apodo del hijo de una lista subida, cifrado, hasta que se arma su kit

Revision: 4d9a1c7e2b58
Anterior: 8b2e4d6f0a13
Fecha:    2026-11-13 12:00:00.000000+00:00

Por que este cambio: el kit que se arma al aprobar la lista que un acudiente
subio no traia el apodo del hijo, y la pagina tenia que adivinarlo cruzando
colegio y grado con las matriculas (falla con hermanos del mismo grado). El
apodo no puede viajar por el Catalogo (no guarda datos de menores, Ley 1581),
asi que se queda aqui, cifrado y ligado a la version importada, y el poller lo
copia al trabajo. La supresion del titular lo borra.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d9a1c7e2b58"
down_revision: str | None = "8b2e4d6f0a13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "apodo_subida",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.String(length=64), nullable=False),
        sa.Column("referencia", sa.String(length=64), nullable=False),
        sa.Column("contacto_referencia", sa.String(length=64), nullable=True),
        sa.Column("apodo_cifrado", sa.LargeBinary(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apodo_subida_version_id", "apodo_subida", ["version_id"])
    op.create_index("ix_apodo_subida_contacto_referencia", "apodo_subida", ["contacto_referencia"])


def downgrade() -> None:
    op.drop_index("ix_apodo_subida_contacto_referencia", table_name="apodo_subida")
    op.drop_index("ix_apodo_subida_version_id", table_name="apodo_subida")
    op.drop_table("apodo_subida")
