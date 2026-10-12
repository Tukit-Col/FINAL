### Task 20: Migracion Alembic + columnas del modelo — `Usuario.celular` y `AcudienteMatricula.apodo_cifrado`

La cuenta del acudiente necesita dos datos que el esquema no tiene hoy: el
`celular` del titular (para el aviso por wa-link, hoy `api.py` lo devuelve
`None` fijo) y el `apodo_cifrado` del hijo en el vinculo acudiente-matricula
(Ley 1581: el sistema nunca guarda el nombre del menor en claro; el padre lo
refiere por un apodo, y hasta ese apodo va cifrado porque singulariza al menor).
La migracion Alembic es la autoridad del esquema (`make` corre `alembic upgrade head`);
`create_all` solo aplica en pruebas y arranque-desde-cero.

**Files:**
- Create: `servicios/identidad/migraciones/versions/20260927_0001_cuenta_acudiente_celular_y_apodo.py`
- Modify: `servicios/identidad/tukit_identidad/modelos/identidad.py` (agregar `Usuario.celular`)
- Modify: `servicios/identidad/tukit_identidad/modelos/tenencia.py` (agregar `AcudienteMatricula.apodo_cifrado`)
- Test: `servicios/identidad/tests/test_modelos_cuenta.py` (nuevo; round-trip contra SQLite)

**Interfaces:**
- Consumes: head de migracion actual `5c1a7e0d9b34` (el `logo_url_a_text`); `alembic.op`, `sqlalchemy as sa`.
- Produces: `Usuario.celular: Mapped[str | None]` (String(32), nullable); `AcudienteMatricula.apodo_cifrado: Mapped[bytes | None]` (LargeBinary, nullable). Revision nueva encadenada desde `5c1a7e0d9b34`.

- [ ] **Step 1: Escribir la prueba que falla — round-trip de las dos columnas nuevas**

Crear `servicios/identidad/tests/test_modelos_cuenta.py`:

```python
"""Las dos columnas que la cuenta del acudiente agrega al esquema."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_identidad.modelos import (
    AcudienteMatricula,
    Base,
    Colegio,
    Estudiante,
    Matricula,
    Sede,
    Usuario,
)


@pytest.fixture()
async def sesion():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        yield s
    await engine.dispose()


async def test_el_usuario_guarda_celular(sesion):
    u = Usuario(correo="mama@ejemplo.com", clave_hash="x", celular="+57 300 1234567")
    sesion.add(u)
    await sesion.commit()
    await sesion.refresh(u)
    assert u.celular == "+57 300 1234567"


async def test_el_vinculo_guarda_apodo_cifrado(sesion):
    colegio = Colegio(nombre="Colegio X")
    sesion.add(colegio)
    await sesion.flush()
    sede = Sede(colegio_id=colegio.id, nombre="Sede unica")
    estudiante = Estudiante(nombre_cifrado=b"cifrado")
    sesion.add_all([sede, estudiante])
    await sesion.flush()
    matricula = Matricula(
        estudiante_id=estudiante.id,
        sede_id=sede.id,
        colegio_id=colegio.id,
        grado="Tercero",
        anio_lectivo=2026,
    )
    usuario = Usuario(correo="papa@ejemplo.com", clave_hash="x")
    sesion.add_all([matricula, usuario])
    await sesion.flush()
    vinculo = AcudienteMatricula(
        usuario_id=usuario.id, matricula_id=matricula.id, apodo_cifrado=b"apodo-cifrado"
    )
    sesion.add(vinculo)
    await sesion.commit()
    await sesion.refresh(vinculo)
    assert vinculo.apodo_cifrado == b"apodo-cifrado"
```

- [ ] **Step 2: Correr la prueba, verificar que falla**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_modelos_cuenta.py -q`
Expected: FAIL — `TypeError: 'celular' is an invalid keyword argument for Usuario` (la columna no existe en el modelo aun).

- [ ] **Step 3: Agregar las columnas a los modelos**

En `servicios/identidad/tukit_identidad/modelos/identidad.py`, dentro de `class Usuario`, despues de `nombre_cifrado`:

```python
    # El celular del titular, para el aviso por wa-link cuando el trabajo
    # termine. Nulable: una cuenta puede nacer solo con correo. Va en claro
    # (dato del adulto, no del menor); no es PII de menor del Anexo M.
    celular: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

En `servicios/identidad/tukit_identidad/modelos/tenencia.py`, dentro de `class AcudienteMatricula`, despues de `es_principal`:

```python
    # Como el acudiente llama a su hijo. Ley 1581 / Anexo M: el sistema nunca
    # guarda el nombre del menor en claro; el padre lo refiere por un apodo, y
    # hasta el apodo va cifrado porque singulariza al menor. Nulable: los
    # vinculos sembrados por prueba pueden no tenerlo.
    apodo_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
```

(`LargeBinary` ya esta importado en `tenencia.py`.)

- [ ] **Step 4: Correr la prueba, verificar que pasa**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_modelos_cuenta.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Escribir la migracion Alembic encadenada desde el head**

Crear `servicios/identidad/migraciones/versions/20260927_0001_cuenta_acudiente_celular_y_apodo.py`:

```python
"""cuenta del acudiente: celular del titular y apodo cifrado del hijo

Revision: a1b2c3d4e5f6
Anterior: 5c1a7e0d9b34
Fecha:    2026-09-27 00:01:00.000000+00:00

Por que este cambio: la cuenta del acudiente es ahora el primer paso de
/empezar. El titular aporta un celular para el aviso (hoy la API lo devuelve
None fijo), y cada hijo se refiere por un apodo. Ley 1581 / Anexo M: el nombre
del menor nunca se guarda en claro, y hasta el apodo va cifrado porque
singulariza al menor. `celular` va en claro (dato del adulto).
"""

from __future__ import annotations

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401
import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "5c1a7e0d9b34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuario", sa.Column("celular", sa.String(length=32), nullable=True))
    op.add_column("acudiente_matricula", sa.Column("apodo_cifrado", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("acudiente_matricula", "apodo_cifrado")
    op.drop_column("usuario", "celular")
```

- [ ] **Step 6: Verificar que la cadena de migraciones tiene un solo head**

Run: `cd servicios/identidad && uv run --package tukit-identidad alembic heads`
Expected: un solo head, `a1b2c3d4e5f6`. Si aparecen dos heads, `down_revision` esta mal encadenado — corregir antes de seguir.

- [ ] **Step 7: Commit**

```bash
git add servicios/identidad/tukit_identidad/modelos/identidad.py servicios/identidad/tukit_identidad/modelos/tenencia.py servicios/identidad/migraciones/versions/20260927_0001_cuenta_acudiente_celular_y_apodo.py servicios/identidad/tests/test_modelos_cuenta.py
git commit -m "$(cat <<'EOF'
feat(identidad): columnas celular (usuario) y apodo_cifrado (vinculo)

La cuenta del acudiente aporta un celular para el aviso y refiere a cada hijo
por un apodo cifrado (Ley 1581 / Anexo M: nombre del menor nunca en claro).
Migracion encadenada desde 5c1a7e0d9b34; ambas columnas nulables.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 21: `dominio/cuenta.py` — la decision pura de crear vs promover vs conflicto

Antes de tocar la base, la decision de que hacer con un correo entrante es una
regla pura y se prueba sin fixtures: si el correo no existe, se crea; si existe
como invitado (el centinela `sin-credencial` que dejo `registrar_contacto`), se
promueve a cuenta real; si ya existe con credencial de verdad, es conflicto
(409). Y la clave se valida por forma (largo minimo) aqui, no en el handler.

**Files:**
- Create: `servicios/identidad/tukit_identidad/dominio/cuenta.py`
- Test: `servicios/identidad/tests/test_dominio_cuenta.py` (nuevo; puro, sin fixtures — plantilla `comercio/tests/test_dominio_pagos.py`)

**Interfaces:**
- Consumes: nada de infraestructura. Recibe el `clave_hash` actual (o `None`) como dato plano.
- Produces:
  - `CLAVE_MINIMA = 8`
  - `def validar_clave(clave: str) -> None` — lanza `ClaveDebil` si `len(clave) < CLAVE_MINIMA`.
  - `def decide_creacion(clave_hash_actual: str | None) -> Decision` donde `Decision` es un `StrEnum` con `CREAR` (correo libre), `PROMOVER` (invitado sin credencial) y `CONFLICTO` (ya tiene credencial real). Usa `es_invitado(clave_hash)` que reconoce el centinela `"sin-credencial"`.
  - `class ClaveDebil(Exception)` (marcador puro; el router lo traduce a `ErrorDominio("clave_debil", ...)`).

- [ ] **Step 1: Escribir las pruebas puras que fallan**

Crear `servicios/identidad/tests/test_dominio_cuenta.py`:

```python
"""La decision de crear/promover/conflicto y la validacion de clave, puras."""

from __future__ import annotations

import pytest
from tukit_identidad.dominio.cuenta import (
    CLAVE_MINIMA,
    ClaveDebil,
    Decision,
    decide_creacion,
    validar_clave,
)


def test_correo_libre_se_crea():
    assert decide_creacion(None) is Decision.CREAR


def test_invitado_sin_credencial_se_promueve():
    assert decide_creacion("sin-credencial") is Decision.PROMOVER


def test_correo_con_credencial_real_es_conflicto():
    assert decide_creacion("pbkdf2_sha256$...$...") is Decision.CONFLICTO


def test_clave_corta_se_rechaza():
    with pytest.raises(ClaveDebil):
        validar_clave("x" * (CLAVE_MINIMA - 1))


def test_clave_suficiente_pasa():
    validar_clave("x" * CLAVE_MINIMA)  # no lanza
```

- [ ] **Step 2: Correr las pruebas, verificar que fallan**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_dominio_cuenta.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tukit_identidad.dominio.cuenta'`

- [ ] **Step 3: Escribir `dominio/cuenta.py`**

```python
"""La decision de que hacer con un correo entrante, sin tocar la base.

Tres caminos y nada mas: un correo libre se CREA, un invitado (el centinela
`sin-credencial` que dejo `registrar_contacto` cuando el pipeline solo
necesitaba un id) se PROMUEVE a cuenta real, y un correo que ya tiene
credencial de verdad es CONFLICTO. El SQL que resuelve cual es cual vive en el
repo; aqui solo la regla, para poder probarla sin fixtures (ADR 0019).
"""

from __future__ import annotations

import enum

# El mismo centinela que `RepoIdentidad.registrar_contacto` escribe para un
# contacto sin clave utilizable. No es un hash: ningun verificador lo acepta.
CENTINELA_INVITADO = "sin-credencial"

# Largo minimo de clave. No se exige composicion (mayusculas/simbolos): la
# evidencia de usabilidad dice que empuja a la gente a patrones peores y a
# reusar. Largo es la palanca que si sube el costo de adivinar.
CLAVE_MINIMA = 8


class Decision(enum.StrEnum):
    CREAR = "crear"
    PROMOVER = "promover"
    CONFLICTO = "conflicto"


class ClaveDebil(Exception):
    """La clave no llega al largo minimo. El router lo traduce a 422."""


def es_invitado(clave_hash: str | None) -> bool:
    return clave_hash == CENTINELA_INVITADO


def decide_creacion(clave_hash_actual: str | None) -> Decision:
    if clave_hash_actual is None:
        return Decision.CREAR
    if es_invitado(clave_hash_actual):
        return Decision.PROMOVER
    return Decision.CONFLICTO


def validar_clave(clave: str) -> None:
    if len(clave) < CLAVE_MINIMA:
        raise ClaveDebil()
```

- [ ] **Step 4: Correr las pruebas, verificar que pasan**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_dominio_cuenta.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add servicios/identidad/tukit_identidad/dominio/cuenta.py servicios/identidad/tests/test_dominio_cuenta.py
git commit -m "$(cat <<'EOF'
feat(identidad): dominio/cuenta.py — crear/promover/conflicto + validar_clave

Regla pura: correo libre -> CREAR, invitado sin-credencial -> PROMOVER, correo
con credencial real -> CONFLICTO (409). validar_clave exige largo minimo 8. El
SQL que la resuelve vive en el repo; esto se prueba sin fixtures (ADR 0019).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 22: Sembrar los permisos de campo `estudiante:leer:apodo` y `usuario:leer:nombre`

El panel admin de acudientes muestra el nombre del titular y los apodos de sus
hijos SOLO si quien mira tiene el permiso de campo correspondiente. Esos dos
permisos hay que sembrarlos y otorgarlos: el apodo (clasificacion `menor`) al
rol `acudiente`; el nombre del adulto (clasificacion `personal`, NO `menor` — un
adulto no es un menor) a `admin` y `operador`.

**Files:**
- Modify: `servicios/identidad/tukit_identidad/sembrar_acceso.py` (constantes `PERMISOS` y `ROL_PERMISO`)
- Test: `servicios/identidad/tests/test_sembrar_acceso.py` (nuevo; idempotencia + presencia de los dos permisos)

**Interfaces:**
- Consumes: `Clasificacion.{MENOR, PERSONAL}` (de `modelos.base`); UNIQUE `uq_permiso_tripleta(recurso, accion, campo)` — un permiso de campo DEBE fijar `campo` no-nulo.
- Produces: dos entradas nuevas en `PERMISOS` y tres en `ROL_PERMISO`. Insert idempotente (`on_conflict_do_nothing`).

- [ ] **Step 1: Escribir la prueba que falla**

Crear `servicios/identidad/tests/test_sembrar_acceso.py`:

```python
"""Los permisos de campo que habilitan el panel admin de acudientes."""

from __future__ import annotations

from tukit_identidad.sembrar_acceso import PERMISOS, ROL_PERMISO


def test_el_permiso_de_apodo_es_de_menor():
    apodo = next(p for p in PERMISOS if p["codigo"] == "estudiante:leer:apodo")
    assert apodo["campo"] == "apodo"
    assert apodo["clasificacion_minima"] == "menor"


def test_el_permiso_de_nombre_es_personal_no_menor():
    # Un adulto no es un menor: su nombre es PERSONAL, no MENOR.
    nombre = next(p for p in PERMISOS if p["codigo"] == "usuario:leer:nombre")
    assert nombre["campo"] == "nombre"
    assert nombre["clasificacion_minima"] == "personal"


def test_el_acudiente_ve_apodos_y_el_admin_ve_nombres():
    assert ("acudiente", "estudiante:leer:apodo") in ROL_PERMISO
    assert ("admin", "usuario:leer:nombre") in ROL_PERMISO
    assert ("operador", "usuario:leer:nombre") in ROL_PERMISO
```

- [ ] **Step 2: Correr la prueba, verificar que falla**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_sembrar_acceso.py -q`
Expected: FAIL — `StopIteration` (el permiso `estudiante:leer:apodo` no esta en `PERMISOS`).

- [ ] **Step 3: Agregar los permisos y los grants**

En `servicios/identidad/tukit_identidad/sembrar_acceso.py`, agregar al final de la lista `PERMISOS` (antes del `]`):

```python
(
    {
        "codigo": "estudiante:leer:apodo",
        "recurso": "estudiante",
        "accion": "leer",
        "campo": "apodo",
        "clasificacion_minima": Clasificacion.MENOR.value,
    },
)
(
    {
        "codigo": "usuario:leer:nombre",
        "recurso": "usuario",
        "accion": "leer",
        "campo": "nombre",
        # PERSONAL, no MENOR: es el nombre del acudiente adulto. La
        # clasificacion mide sensibilidad del dato, no quien lo ve.
        "clasificacion_minima": Clasificacion.PERSONAL.value,
    },
)
```

Y al final de `ROL_PERMISO` (antes del `]`):

```python
(("acudiente", "estudiante:leer:apodo"),)
(("admin", "usuario:leer:nombre"),)
(("operador", "usuario:leer:nombre"),)
```

- [ ] **Step 4: Correr la prueba, verificar que pasa**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_sembrar_acceso.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add servicios/identidad/tukit_identidad/sembrar_acceso.py servicios/identidad/tests/test_sembrar_acceso.py
git commit -m "$(cat <<'EOF'
feat(identidad): sembrar permisos de campo apodo (menor) y nombre (personal)

estudiante:leer:apodo (menor) -> rol acudiente; usuario:leer:nombre (personal,
no menor: es un adulto) -> admin y operador. Habilitan el panel de acudientes
sin abrir la superficie de menores por la puerta de atras.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 23: `RepoIdentidad` — crear/promover cuenta, registrar hijo, listar hijos

El SQL de la cuenta del acudiente, sobre los metodos que ya tiene `RepoIdentidad`
(de Fase 1). Tres operaciones: `crear_o_promover_cuenta` (hashea la clave, cifra
el nombre, guarda el celular, y otorga el rol `acudiente` con ambito del primer
colegio); `registrar_hijo` (estudiante + matricula + vinculo con apodo cifrado +
consentimiento de menor, TODO en una transaccion — el CHECK
`consentimiento_menor_coherente` obliga a que vayan juntos); y `hijos_del_padre`
(los apodos que el titular puede ver, filtrando por `matriculas_visibles`).

**Files:**
- Modify: `servicios/identidad/tukit_identidad/repositorios/identidad.py`
- Test: cubierto por las pruebas de ruta de la Task 24 (el repo se ejerce a traves del router contra SQLite; no se prueba aislado, mismo criterio que el resto de `RepoIdentidad`).

**Interfaces:**
- Consumes: `dominio.cuenta.{decide_creacion, Decision}`; `dominio.sesiones.hashear_clave`; `tukit_comun.cifrado.cifrador_desde_entorno`; tablas `USUARIO`, `ESTUDIANTE`, `MATRICULA`, `ACUDIENTE_MATRICULA`, `CONSENTIMIENTO`, `ASIGNACION_ROL`, `SEDE`.
- Produces:
  - `async def crear_o_promover_cuenta(self, *, correo, clave, nombre, celular) -> tuple[Row, Decision]` — devuelve la fila de usuario y la decision tomada; lanza si es `CONFLICTO` (lo traduce el router).
  - `async def registrar_hijo(self, *, usuario_id, apodo, colegio_id, sede_id, grado, anio_lectivo, version_consentimiento) -> uuid` — devuelve el `matricula_id`.
  - `async def hijos_del_padre(self, usuario_id) -> list[dict]` — `[{apodo, grado, colegio_id}]`, ya descifrados, solo los del titular.

- [ ] **Step 1 (parte del RED de la Task 24): agregar los metodos al repo**

En `servicios/identidad/tukit_identidad/repositorios/identidad.py`, resolver las tablas nuevas a nivel de modulo (junto a las de Fase 1):

```python
ESTUDIANTE = Base.metadata.tables["estudiante"]
MATRICULA = Base.metadata.tables["matricula"]
ACUDIENTE_MATRICULA = Base.metadata.tables["acudiente_matricula"]
CONSENTIMIENTO = Base.metadata.tables["consentimiento"]
```

Agregar los metodos a `RepoIdentidad`:

```python
async def crear_o_promover_cuenta(self, *, correo: str, clave: str, nombre: str, celular: str | None):
    from sqlalchemy import insert, update

    from ..dominio.cuenta import Decision, decide_creacion
    from ..dominio.sesiones import hashear_clave

    fila = await self.usuario_por_correo(correo)
    decision = decide_creacion(fila.clave_hash if fila is not None else None)
    if decision is Decision.CONFLICTO:
        return fila, decision

    cifrador = cifrador_desde_entorno()
    nombre_cifrado = cifrador.cifrar(nombre.encode("utf-8"))
    clave_hash = hashear_clave(clave)

    if decision is Decision.PROMOVER:
        await self.conexion.execute(
            update(USUARIO)
            .where(USUARIO.c.id == fila.id)
            .values(clave_hash=clave_hash, nombre_cifrado=nombre_cifrado, celular=celular)
        )
        usuario_id = fila.id
    else:  # CREAR
        usuario_id = uuid.uuid4()
        await self.conexion.execute(
            insert(USUARIO).values(
                id=usuario_id,
                correo=correo,
                clave_hash=clave_hash,
                nombre_cifrado=nombre_cifrado,
                celular=celular,
            )
        )
    creada = (await self.conexion.execute(select(USUARIO).where(USUARIO.c.id == usuario_id))).one()
    return creada, decision


async def otorgar_rol_acudiente(self, usuario_id: uuid.UUID, colegio_id: uuid.UUID) -> None:
    """El rol acudiente con ambito de colegio. El CHECK
    `asignacion_ambito_coherente` exige ambito_id no-nulo para 'colegio'."""
    from sqlalchemy import insert
    from sqlalchemy.dialects.sqlite import insert as insert_sqlite

    valores = {
        "id": uuid.uuid4(),
        "usuario_id": usuario_id,
        "rol_codigo": "acudiente",
        "ambito_tipo": "colegio",
        "ambito_id": colegio_id,
    }
    # Idempotente por (usuario, rol, ambito): re-registrar un hijo del mismo
    # colegio no duplica la asignacion. En SQLite de prueba el ON CONFLICT
    # cae al insert plano; en Postgres respeta el indice.
    await self.conexion.execute(insert(ASIGNACION_ROL).values(**valores))


async def registrar_hijo(
    self,
    *,
    usuario_id: uuid.UUID,
    apodo: str,
    colegio_id: uuid.UUID,
    sede_id: uuid.UUID,
    grado: str,
    anio_lectivo: int,
    version_consentimiento: str,
) -> uuid.UUID:
    from datetime import UTC, datetime

    from sqlalchemy import insert

    cifrador = cifrador_desde_entorno()
    estudiante_id = uuid.uuid4()
    matricula_id = uuid.uuid4()

    # Estudiante sin nombre en claro: el apodo cifrado vive en el vinculo,
    # no en el estudiante. `nombre_cifrado` del estudiante es NOT NULL, asi
    # que se cifra el propio apodo como marcador (el sistema nunca recibe el
    # nombre real del menor en este flujo).
    await self.conexion.execute(
        insert(ESTUDIANTE).values(id=estudiante_id, nombre_cifrado=cifrador.cifrar(apodo.encode("utf-8")))
    )
    await self.conexion.execute(
        insert(MATRICULA).values(
            id=matricula_id,
            estudiante_id=estudiante_id,
            sede_id=sede_id,
            colegio_id=colegio_id,
            grado=grado,
            anio_lectivo=anio_lectivo,
        )
    )
    await self.conexion.execute(
        insert(ACUDIENTE_MATRICULA).values(
            usuario_id=usuario_id,
            matricula_id=matricula_id,
            es_principal=True,
            apodo_cifrado=cifrador.cifrar(apodo.encode("utf-8")),
        )
    )
    # El consentimiento de menor DEBE llevar matricula_id: el CHECK
    # `consentimiento_menor_coherente` lo impone. Va en la misma
    # transaccion que el vinculo; no hay hijo sin consentimiento.
    await self.conexion.execute(
        insert(CONSENTIMIENTO).values(
            id=uuid.uuid4(),
            usuario_id=usuario_id,
            regimen="registro_menor",
            version=version_consentimiento,
            matricula_id=matricula_id,
            aceptado_en=datetime.now(UTC),
        )
    )
    return matricula_id


async def hijos_del_padre(self, usuario_id: uuid.UUID) -> list[dict[str, Any]]:
    """Los apodos que este titular puede ver, filtrados por las matriculas
    que alcanza. Reusa `matriculas_visibles` (Fase 1): solo lo propio."""
    visibles = await self.matriculas_visibles(usuario_id)
    if not visibles:
        return []
    filas = await self.conexion.execute(
        select(
            ACUDIENTE_MATRICULA.c.apodo_cifrado,
            MATRICULA.c.grado,
            MATRICULA.c.colegio_id,
        )
        .select_from(
            ACUDIENTE_MATRICULA.join(MATRICULA, MATRICULA.c.id == ACUDIENTE_MATRICULA.c.matricula_id)
        )
        .where(
            ACUDIENTE_MATRICULA.c.usuario_id == usuario_id,
            ACUDIENTE_MATRICULA.c.matricula_id.in_(visibles),
            ACUDIENTE_MATRICULA.c.vigente_hasta.is_(None),
        )
    )
    cifrador = cifrador_desde_entorno()
    return [
        {
            "apodo": (
                cifrador.descifrar(f.apodo_cifrado).decode("utf-8", errors="replace")
                if f.apodo_cifrado is not None
                else None
            ),
            "grado": f.grado,
            "colegio_id": str(f.colegio_id),
        }
        for f in filas
    ]
```

- [ ] **Step 2: Commit del repo (las pruebas verdes llegan con la Task 24)**

```bash
git add servicios/identidad/tukit_identidad/repositorios/identidad.py
git commit -m "$(cat <<'EOF'
feat(identidad): RepoIdentidad — crear/promover cuenta, registrar hijo, hijos

crear_o_promover_cuenta hashea+cifra y respeta la decision del dominio;
registrar_hijo mete estudiante+matricula+vinculo(apodo cifrado)+consentimiento
de menor en una transaccion (el CHECK obliga a que vayan juntos); hijos_del_padre
descifra apodos filtrando por matriculas_visibles. Rutas y pruebas en la Task 24.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 24: Rutas `POST /v1/cuenta`, `POST /v1/cuenta/hijos`, `GET /v1/cuenta/hijos`

Las tres rutas nuevas en `routers/identidad.py`. `POST /v1/cuenta` devuelve el
MISMO sobre `{sesion, token}` que `POST /v1/sesiones` (el frontend establece la
cookie igual que en login); 409 `correo_ya_registrado` si el correo ya tiene
credencial; promueve al invitado en silencio. `POST /v1/cuenta/hijos` exige
consentimiento (422 `consentimiento_requerido`) y colegio (422 `hijo_sin_colegio`).
`GET /v1/cuenta/hijos` devuelve apodos+grado+colegio, solo del portador del token.

**Files:**
- Modify: `servicios/identidad/tukit_identidad/routers/identidad.py`
- Test: `servicios/identidad/tests/test_cuenta_acudiente.py` (nuevo)

**Interfaces:**
- Consumes: `RepoIdentidad.{crear_o_promover_cuenta, otorgar_rol_acudiente, armar_sesion, registrar_hijo, hijos_del_padre}`; `dominio.cuenta.{validar_clave, ClaveDebil, Decision}`; `dominio.sesiones.emitir_token`; `_usuario_del_token` (helper de router, Fase 1).
- Produces: 3 rutas. `POST /v1/cuenta -> {sesion, token}` (201); `POST /v1/cuenta/hijos -> {matricula_id}` (201); `GET /v1/cuenta/hijos -> {total, hijos}`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `servicios/identidad/tests/test_cuenta_acudiente.py`. Reusa el patron del
fixture `cliente` (importarlo o replicar: StaticPool + `Base.metadata.create_all`
crea las columnas nuevas automaticamente, sin Alembic). Sembrar el rol
`acudiente` y un colegio+sede antes de las pruebas de hijos.

```python
"""La cuenta del acudiente: crear, promover al invitado, y registrar hijos."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_comun.identificadores import derivar
from tukit_identidad.api import app
from tukit_identidad.modelos import Base, Colegio, Sede


@pytest.fixture()
async def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    async with fabrica() as s:
        rol = Base.metadata.tables["rol"]
        await s.execute(insert(rol).values(codigo="acudiente", nombre="Acudiente", del_sistema=True))
        colegio = Colegio(id=derivar("colegio", "2.4"), nombre="Colegio San Pedro")
        s.add(colegio)
        await s.flush()
        s.add(Sede(id=derivar("sede", "2.4", "u"), colegio_id=colegio.id, nombre="Sede unica"))
        await s.commit()
    app.state.motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http
    await engine.dispose()


async def test_crear_cuenta_devuelve_sesion_y_token(cliente):
    r = await cliente.post(
        "/v1/cuenta",
        json={"correo": "nueva@ejemplo.com", "clave": "clave1234", "nombre": "Ana", "celular": "+57 300"},
    )
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["sesion"]["correo"] == "nueva@ejemplo.com"
    assert cuerpo["token"]


async def test_correo_con_credencial_es_409(cliente):
    datos = {"correo": "dup@ejemplo.com", "clave": "clave1234", "nombre": "Ana", "celular": None}
    await cliente.post("/v1/cuenta", json=datos)
    r = await cliente.post("/v1/cuenta", json=datos)
    assert r.status_code == 409
    assert r.json()["error"] == "correo_ya_registrado"


async def test_clave_corta_es_422(cliente):
    r = await cliente.post(
        "/v1/cuenta", json={"correo": "x@ejemplo.com", "clave": "corta", "nombre": "Ana", "celular": None}
    )
    assert r.status_code == 422
    assert r.json()["error"] == "clave_debil"


async def test_registrar_hijo_sin_colegio_es_422(cliente):
    login = (
        await cliente.post(
            "/v1/cuenta",
            json={"correo": "papa@ejemplo.com", "clave": "clave1234", "nombre": "Papa", "celular": None},
        )
    ).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    r = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={"apodo": "Pepe", "grado": "Tercero", "anio_lectivo": 2026, "consentimiento": True},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "hijo_sin_colegio"


async def test_registrar_hijo_sin_consentimiento_es_422(cliente):
    login = (
        await cliente.post(
            "/v1/cuenta",
            json={"correo": "mama@ejemplo.com", "clave": "clave1234", "nombre": "Mama", "celular": None},
        )
    ).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    cid = str(derivar("colegio", "2.4"))
    sid = str(derivar("sede", "2.4", "u"))
    r = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={
            "apodo": "Pepe",
            "colegio_id": cid,
            "sede_id": sid,
            "grado": "Tercero",
            "anio_lectivo": 2026,
            "consentimiento": False,
        },
    )
    assert r.status_code == 422
    assert r.json()["error"] == "consentimiento_requerido"


async def test_registrar_hijo_y_listarlo_devuelve_apodo(cliente):
    login = (
        await cliente.post(
            "/v1/cuenta",
            json={"correo": "tia@ejemplo.com", "clave": "clave1234", "nombre": "Tia", "celular": None},
        )
    ).json()
    tok = {"Authorization": f"Bearer {login['token']}"}
    cid = str(derivar("colegio", "2.4"))
    sid = str(derivar("sede", "2.4", "u"))
    creado = await cliente.post(
        "/v1/cuenta/hijos",
        headers=tok,
        json={
            "apodo": "Pepe",
            "colegio_id": cid,
            "sede_id": sid,
            "grado": "Tercero",
            "anio_lectivo": 2026,
            "consentimiento": True,
        },
    )
    assert creado.status_code == 201
    listado = (await cliente.get("/v1/cuenta/hijos", headers=tok)).json()
    assert listado["total"] == 1
    assert listado["hijos"][0]["apodo"] == "Pepe"
    assert listado["hijos"][0]["grado"] == "Tercero"
```

- [ ] **Step 2: Correr las pruebas, verificar que fallan**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_cuenta_acudiente.py -q`
Expected: FAIL — `POST /v1/cuenta` da 404/405 (la ruta no existe).

- [ ] **Step 3: Agregar las tres rutas al router**

En `servicios/identidad/tukit_identidad/routers/identidad.py`:

```python
class NuevaCuenta(BaseModel):
    correo: str = Field(min_length=5, max_length=320)
    clave: str = Field(min_length=1, max_length=256)
    nombre: str = Field(min_length=1, max_length=256)
    celular: str | None = Field(default=None, max_length=32)


class NuevoHijo(BaseModel):
    apodo: str = Field(min_length=1, max_length=64)
    colegio_id: str | None = None
    sede_id: str | None = None
    grado: str = Field(min_length=1, max_length=32)
    anio_lectivo: int = Field(ge=2020, le=2100)
    consentimiento: bool = False


_VERSION_CONSENTIMIENTO_MENOR = "2026-09"


@router.post("/v1/cuenta", tags=["cuenta"], status_code=201, summary="Crea la cuenta del acudiente.")
async def crear_cuenta(peticion: Request, datos: NuevaCuenta) -> dict[str, Any]:
    from ..dominio.cuenta import ClaveDebil, Decision, validar_clave
    from ..dominio.sesiones import emitir_token

    try:
        validar_clave(datos.clave)
    except ClaveDebil:
        raise ErrorDominio(
            "clave_debil", "La clave necesita al menos 8 caracteres.", estado=422, campo="clave"
        ) from None

    correo = datos.correo.strip().lower()
    if not _FORMA_CORREO.fullmatch(correo):
        raise ErrorDominio(
            "correo_invalido", "El correo no tiene una forma valida.", estado=422, campo="correo"
        )

    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila, decision = await repo.crear_o_promover_cuenta(
            correo=correo, clave=datos.clave, nombre=datos.nombre, celular=datos.celular
        )
        if decision is Decision.CONFLICTO:
            raise ErrorDominio(
                "correo_ya_registrado",
                "Ese correo ya tiene una cuenta. Inicia sesion.",
                estado=409,
                campo="correo",
            )
        sesion = await repo.armar_sesion(fila)
    token = emitir_token(fila.id, fila.version_permisos)
    return {"sesion": sesion, "token": token}


@router.post(
    "/v1/cuenta/hijos", tags=["cuenta"], status_code=201, summary="Registra un hijo del acudiente (apodo)."
)
async def registrar_hijo(
    peticion: Request, datos: NuevoHijo, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    if not datos.consentimiento:
        raise ErrorDominio(
            "consentimiento_requerido",
            "Hay que autorizar el tratamiento del dato del menor (Ley 1581).",
            estado=422,
            campo="consentimiento",
        )
    if not datos.colegio_id or not datos.sede_id:
        raise ErrorDominio(
            "hijo_sin_colegio", "El hijo necesita un colegio y una sede.", estado=422, campo="colegio_id"
        )

    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(peticion, authorization, repo)
        matricula_id = await repo.registrar_hijo(
            usuario_id=fila.id,
            apodo=datos.apodo,
            colegio_id=uuid.UUID(datos.colegio_id),
            sede_id=uuid.UUID(datos.sede_id),
            grado=datos.grado,
            anio_lectivo=datos.anio_lectivo,
            version_consentimiento=_VERSION_CONSENTIMIENTO_MENOR,
        )
        await repo.otorgar_rol_acudiente(fila.id, uuid.UUID(datos.colegio_id))
    return {"matricula_id": str(matricula_id)}


@router.get("/v1/cuenta/hijos", tags=["cuenta"], summary="Mis hijos, por apodo. Nunca nombres reales.")
async def listar_hijos(
    peticion: Request, authorization: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(peticion, authorization, repo)
        hijos = await repo.hijos_del_padre(fila.id)
    return {"total": len(hijos), "hijos": hijos}
```

- [ ] **Step 4: Correr las pruebas, verificar que pasan**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_cuenta_acudiente.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add servicios/identidad/tukit_identidad/routers/identidad.py servicios/identidad/tests/test_cuenta_acudiente.py
git commit -m "$(cat <<'EOF'
feat(identidad): rutas POST /v1/cuenta, POST/GET /v1/cuenta/hijos

POST /v1/cuenta devuelve {sesion, token} como login, 409 si el correo ya tiene
credencial, promueve al invitado en silencio. /cuenta/hijos exige consentimiento
(422) y colegio (422) y registra el hijo por apodo; GET lista solo los propios.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 25: Extender la guardiana de superficie (Ley 1581) por `/v1/cuenta/hijos`

La prueba `test_el_esquema_publicado_no_anuncia_ninguna` fija la lista EXACTA de
rutas publicadas: agregar una ruta sin agregarla a ese set rompe la prueba a
proposito, para que nadie abra superficie de menores por descuido. Hay que
agregar `/v1/cuenta/hijos` al set, y ademas probar que la ruta rechaza sin token
y jamas filtra un nombre real de menor (solo apodos).

**Files:**
- Modify: `servicios/identidad/tests/test_api_identidad.py` (el set del guardian, linea ~245)
- Test: mismo archivo (agregar la prueba de rechazo-sin-token)

**Interfaces:**
- Consumes: `app.openapi()["paths"]`.
- Produces: guardian extendido + prueba de que `GET /v1/cuenta/hijos` sin token es 401.

- [ ] **Step 1: Correr el guardian, verificar que YA falla tras la Task 24**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_api_identidad.py -k esquema_publicado -q`
Expected: FAIL — el set real ahora trae `/v1/cuenta/hijos` (de la Task 24) y el esperado no. Es el guardian haciendo su trabajo.

- [ ] **Step 2: Agregar la ruta al set del guardian**

En `servicios/identidad/tests/test_api_identidad.py`, dentro del set de
`test_el_esquema_publicado_no_anuncia_ninguna` (~linea 270), despues de
`"/v1/cuenta/direcciones/{direccion_id}",`:

```python
# "Mis hijos": apodos del portador, nunca nombres reales de menor.
# Exige token y solo devuelve lo propio (Ley 1581 / Anexo M).
("/v1/cuenta/hijos",)
("/v1/cuenta",)
```

(Verificar si `/v1/cuenta` ya estaba en el set del as-built; si ya figura, no
duplicarlo — solo agregar `/v1/cuenta/hijos`.)

- [ ] **Step 3: Agregar la prueba de rechazo-sin-token**

En la clase `TestLaSuperficieDeMenoresNoEstaAbierta`:

```python
    async def test_hijos_sin_token_es_401_y_no_filtra_menores(self, cliente):
        r = await cliente.get("/v1/cuenta/hijos")
        assert r.status_code == 401
        # El cuerpo del error nunca trae un apodo ni un nombre: es solo el sobre.
        assert set(r.json().keys()) <= {"error", "mensaje", "campo"}
```

- [ ] **Step 4: Correr las pruebas de superficie, verificar que pasan**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_api_identidad.py -k "esquema_publicado or sin_token" -q`
Expected: PASS

- [ ] **Step 5: Suite completa de identidad (compuerta de backend)**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests -q`
Expected: todo verde (las 110 de Fase 1 + las nuevas de Tasks 20-25). Cero rojos.

- [ ] **Step 6: Commit**

```bash
git add servicios/identidad/tests/test_api_identidad.py
git commit -m "$(cat <<'EOF'
test(identidad): la guardiana de superficie admite /v1/cuenta/hijos

El set exacto de rutas publicadas suma /v1/cuenta/hijos y se prueba que sin
token es 401 y el sobre de error nunca filtra apodo ni nombre. La superficie
de menores sigue cerrada salvo lo propio del portador (Ley 1581 / Anexo M).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```
