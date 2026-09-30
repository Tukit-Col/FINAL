### Task 1: Scaffold `dominio/` — mover `sesiones.py`, extraer `Ambito`, mover `directorio_bogota.py`

**Files:**
- Create: `servicios/identidad/tukit_identidad/dominio/__init__.py`
- Create: `servicios/identidad/tukit_identidad/dominio/sesiones.py` (contenido movido de `sesiones.py`)
- Create: `servicios/identidad/tukit_identidad/dominio/autorizacion.py` (solo `Ambito`)
- Create: `servicios/identidad/tukit_identidad/dominio/directorio.py` (contenido movido de `directorio_bogota.py`)
- Modify: `servicios/identidad/tukit_identidad/api.py` (import `L42`: `from .sesiones import ...` → `from .dominio.sesiones import ...`; import inline `L155`: `from .directorio_bogota import datos_colegio_nuevo_por_dane` → `from .dominio.directorio import datos_colegio_nuevo_por_dane`)
- Modify: `servicios/identidad/tukit_identidad/sembrar_acceso.py` (`L37`: `from .sesiones import hashear_clave` → `from .dominio.sesiones import hashear_clave`)
- Modify: `servicios/identidad/tests/test_sesiones.py` (`L23-28`: `from tukit_identidad.sesiones import (...)` → `from tukit_identidad.dominio.sesiones import (...)`)
- Modify: `servicios/identidad/tests/test_cuenta.py` (`L26`: `from tukit_identidad.sesiones import emitir_token, hashear_clave` → `from tukit_identidad.dominio.sesiones import emitir_token, hashear_clave`)
- Modify: `servicios/identidad/tests/test_autorizacion.py` (`L15-21`: separar el import de `Ambito` del de las funciones con SQL, que quedan apuntando al modulo viejo hasta la Task 2)
- Modify: `servicios/identidad/tests/test_directorio_bogota.py` (`L16-18`: `from tukit_identidad.directorio_bogota import (parsear_directorio)` → `from tukit_identidad.dominio.directorio import (parsear_directorio)`)
- Delete: `servicios/identidad/tukit_identidad/sesiones.py`
- Delete: `servicios/identidad/tukit_identidad/directorio_bogota.py`
- Test: `servicios/identidad/tests/test_dominio_ambito.py` (crear, prueba pura nueva que fija el contrato de `Ambito` en su nueva casa)

**Interfaces:**
- Consumes: nada nuevo — `dominio/sesiones.py` y `dominio/directorio.py` son movimientos verbatim; `dominio/autorizacion.py` extrae solo la `dataclass Ambito` de `autorizacion.py` (que sigue viviendo, sin cambios todavia, para las 4 funciones con SQL — esas se mueven en la Task 2).
- Produces: `dominio.sesiones.{hashear_clave, verificar_clave, emitir_token, leer_token, VARIABLE_LLAVE, VIDA_SEGUNDOS}`; `dominio.autorizacion.Ambito` (mismo `frozen dataclass`, mismos classmethods `global_/colegio/sede/matricula`); `dominio.directorio.{ColegioDirectorio, parsear_directorio, generar_json_busqueda, datos_colegio_nuevo_por_dane}`.

- [ ] **Step 1: Write a failing pure test for `Ambito` en su nueva casa**

```python
# servicios/identidad/tests/test_dominio_ambito.py
"""`Ambito` como dataclass puro: fija el contrato antes de moverlo a dominio/."""

from __future__ import annotations

import uuid

import pytest
from tukit_identidad.dominio.autorizacion import Ambito
from tukit_identidad.modelos import AmbitoTipo


def test_ambito_global_no_lleva_id():
    assert Ambito.global_() == Ambito(AmbitoTipo.GLOBAL, None)


def test_ambito_colegio_lleva_su_id():
    cid = uuid.uuid4()
    assert Ambito.colegio(cid) == Ambito(AmbitoTipo.COLEGIO, cid)


def test_ambito_global_con_id_es_incoherente():
    with pytest.raises(ValueError, match="incoherente"):
        Ambito(AmbitoTipo.GLOBAL, uuid.uuid4())


def test_ambito_no_global_sin_id_es_incoherente():
    with pytest.raises(ValueError, match="incoherente"):
        Ambito(AmbitoTipo.SEDE, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_dominio_ambito.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tukit_identidad.dominio'`

- [ ] **Step 3: Crear `dominio/__init__.py` y `dominio/autorizacion.py` con `Ambito`**

```python
# servicios/identidad/tukit_identidad/dominio/__init__.py
"""El dominio puro de Identidad: reglas sin FastAPI, sin SQLAlchemy, sin HTTP.

Nada aqui hace una consulta ni conoce una peticion (ADR 0019, la regla de
dependencia apunta hacia adentro): son `dataclass` y funciones que reciben
datos planos y devuelven datos planos. El hasheo de clave y la firma de
tokens (`sesiones.py`), el ambito sobre el que se pregunta un permiso
(`autorizacion.py`) y el lookup del directorio DUEB (`directorio.py`) viven
aqui porque ninguno necesita la base para responder. Las consultas que SI
tocan la base (`puede`, `roles_vigentes`, `campos_visibles`,
`matriculas_visibles`) viven en `repositorios/identidad.py`.
"""
```

```python
# servicios/identidad/tukit_identidad/dominio/autorizacion.py
"""El ambito sobre el que se pregunta un permiso, como dato puro.

`Ambito` reemplaza comparar `if usuario.rol not in roles`: la pregunta
correcta es "que puede hacer este usuario SOBRE ESTE recurso", y `Ambito` es
justo ese recurso, tipado. Las funciones que RESUELVEN la pregunta contra la
base (`puede`, `roles_vigentes`, `campos_visibles`, `matriculas_visibles`,
`_cadena_de_contencion`) no son dominio puro —hacen SQL— y viven en
`repositorios/identidad.py`. Ver ADR 0013.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..modelos import AmbitoTipo


@dataclass(frozen=True, slots=True)
class Ambito:
    """Sobre que se pregunta. `GLOBAL` no lleva identificador."""

    tipo: AmbitoTipo
    id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        # Misma regla que el CHECK `asignacion_ambito_coherente`. Se valida
        # tambien aqui para que un ambito mal armado falle al construirse y no
        # al comparar, donde el error seria un permiso denegado sin explicacion.
        if (self.tipo is AmbitoTipo.GLOBAL) != (self.id is None):
            raise ValueError(
                f"Ambito incoherente: tipo={self.tipo} con id={self.id}. "
                "El ambito global no lleva identificador, y los demas si."
            )

    @classmethod
    def global_(cls) -> Ambito:
        return cls(AmbitoTipo.GLOBAL)

    @classmethod
    def colegio(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.COLEGIO, id)

    @classmethod
    def sede(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.SEDE, id)

    @classmethod
    def matricula(cls, id: uuid.UUID) -> Ambito:
        return cls(AmbitoTipo.MATRICULA, id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_dominio_ambito.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add servicios/identidad/tukit_identidad/dominio/__init__.py servicios/identidad/tukit_identidad/dominio/autorizacion.py servicios/identidad/tests/test_dominio_ambito.py
git commit -m "$(cat <<'EOF'
refactor(identidad): extraer Ambito puro a dominio/autorizacion.py

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Mover `sesiones.py` a `dominio/sesiones.py`, verbatim**

Copiar el contenido integro de `servicios/identidad/tukit_identidad/sesiones.py` (163 lineas: `hashear_clave`, `verificar_clave`, `_llave`, `_b64`, `_desb64`, `emitir_token`, `leer_token`, y las constantes `VARIABLE_LLAVE`/`_LLAVE_DESARROLLO`/`VIDA_SEGUNDOS`/`_ITERACIONES_PBKDF2`/`_ALGORITMO`) a `servicios/identidad/tukit_identidad/dominio/sesiones.py` sin ningun cambio de codigo — el modulo no importa nada de `tukit_identidad`, asi que no hay imports relativos que ajustar. Borrar el archivo viejo:

```bash
git mv servicios/identidad/tukit_identidad/sesiones.py servicios/identidad/tukit_identidad/dominio/sesiones.py
```

- [ ] **Step 7: Actualizar los import call-sites de `sesiones`**

En `servicios/identidad/tukit_identidad/api.py` linea 42:

```python
# antes
from .sesiones import emitir_token, leer_token, verificar_clave
# despues
from .dominio.sesiones import emitir_token, leer_token, verificar_clave
```

En `servicios/identidad/tukit_identidad/sembrar_acceso.py` linea 37:

```python
# antes
from .sesiones import hashear_clave
# despues
from .dominio.sesiones import hashear_clave
```

En `servicios/identidad/tests/test_sesiones.py` lineas 23-28:

```python
# antes
from tukit_identidad.sesiones import (
    emitir_token,
    hashear_clave,
    leer_token,
    verificar_clave,
)
# despues
from tukit_identidad.dominio.sesiones import (
    emitir_token,
    hashear_clave,
    leer_token,
    verificar_clave,
)
```

En `servicios/identidad/tests/test_cuenta.py` linea 26:

```python
# antes
from tukit_identidad.sesiones import emitir_token, hashear_clave
# despues
from tukit_identidad.dominio.sesiones import emitir_token, hashear_clave
```

- [ ] **Step 8: Run the sesiones + cuenta suites to verify green**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_sesiones.py servicios/identidad/tests/test_cuenta.py -q`
Expected: PASS (todas las pruebas de ambos archivos, sin `ImportError`)

- [ ] **Step 9: Commit**

```bash
git add servicios/identidad/tukit_identidad/dominio/sesiones.py servicios/identidad/tukit_identidad/api.py servicios/identidad/tukit_identidad/sembrar_acceso.py servicios/identidad/tests/test_sesiones.py servicios/identidad/tests/test_cuenta.py
git commit -m "$(cat <<'EOF'
refactor(identidad): mover sesiones.py a dominio/sesiones.py, verbatim

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 10: Mover `directorio_bogota.py` a `dominio/directorio.py`, con el fix de ruta**

Copiar el contenido integro de `directorio_bogota.py` (225 lineas) a `dominio/directorio.py`. El unico cambio de codigo es la ruta al dato: el modulo ahora vive un nivel mas adentro (`dominio/` en vez de la raiz de `tukit_identidad/`), asi que `Path(__file__).parent` ya no apunta a `tukit_identidad/datos/` sino a `tukit_identidad/dominio/datos/`, que no existe. Se corrige a `.parent.parent`:

```python
# dentro de dominio/directorio.py, funcion _indice_por_dane()
def _indice_por_dane() -> dict[str, ColegioDirectorio]:
    global _POR_DANE
    if _POR_DANE is None:
        from pathlib import Path

        ruta = Path(__file__).parent.parent / _FUENTE
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        _POR_DANE = {c.dane: c for c in parsear_directorio(texto)}
    return _POR_DANE
```

Todo lo demas (`_ETIQUETAS`, `_SEPARADOR_MULTIVALOR`, `ColegioDirectorio`, `_limpio`, `_primer_valor`, `_bloque_a_colegio`, `parsear_directorio`, `generar_json_busqueda`, `datos_colegio_nuevo_por_dane`, `_main`, `__all__`) se copia tal cual. Borrar el archivo viejo:

```bash
git mv servicios/identidad/tukit_identidad/directorio_bogota.py servicios/identidad/tukit_identidad/dominio/directorio.py
```

- [ ] **Step 11: Actualizar los import call-sites de `directorio_bogota`**

En `servicios/identidad/tukit_identidad/api.py` linea 155 (import inline dentro de `datos_directorio`):

```python
# antes
from .directorio_bogota import datos_colegio_nuevo_por_dane
# despues
from .dominio.directorio import datos_colegio_nuevo_por_dane
```

En `servicios/identidad/tests/test_directorio_bogota.py` lineas 16-18:

```python
# antes
from tukit_identidad.directorio_bogota import (
    parsear_directorio,
)
# despues
from tukit_identidad.dominio.directorio import (
    parsear_directorio,
)
```

- [ ] **Step 12: Run the directorio + full api-level tests that touch `/v1/directorio`**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_directorio_bogota.py servicios/identidad/tests/test_api_identidad.py -q`
Expected: PASS (ningun `ImportError`; el lookup por DANE sigue leyendo `datos/colegios_bogota.txt` con la ruta corregida)

- [ ] **Step 13: Commit**

```bash
git add servicios/identidad/tukit_identidad/dominio/directorio.py servicios/identidad/tukit_identidad/api.py servicios/identidad/tests/test_directorio_bogota.py
git commit -m "$(cat <<'EOF'
refactor(identidad): mover directorio_bogota.py a dominio/directorio.py

Corrige Path(__file__).parent -> .parent.parent: el modulo bajo dominio/
queda un nivel mas adentro que la raiz de tukit_identidad/, y datos/ sigue
viviendo junto al paquete, no junto al dominio.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 14: Separar el import de `Ambito` en `test_autorizacion.py`**

`autorizacion.py` (raiz de `tukit_identidad/`) sigue existiendo sin cambios hasta la Task 2 — todavia declara `Ambito` y las 4 funciones con SQL. Para que el test ya ejercite la `Ambito` NUEVA (la de `dominio/autorizacion.py`) sin esperar a la Task 2, se separa el import en dos lineas: `Ambito` desde `dominio.autorizacion`, las funciones con SQL siguen desde el modulo viejo (se moveran en la Task 2).

En `servicios/identidad/tests/test_autorizacion.py` lineas 15-21:

```python
# antes
from tukit_identidad.autorizacion import (
    Ambito,
    campos_visibles,
    matriculas_visibles,
    puede,
    roles_vigentes,
)
# despues
from tukit_identidad.autorizacion import (
    campos_visibles,
    matriculas_visibles,
    puede,
    roles_vigentes,
)
from tukit_identidad.dominio.autorizacion import Ambito
```

Y en `servicios/identidad/tukit_identidad/autorizacion.py`, borrar la `dataclass Ambito` (lineas 37-68) y su import de `dataclass` si queda sin uso, e importar la nueva desde dominio para que las funciones que se quedan (`puede`, `roles_vigentes`, `campos_visibles`, `matriculas_visibles`, `_cadena_de_contencion`) sigan resolviendo el tipo:

```python
# en autorizacion.py, agregar tras los imports existentes:
from .dominio.autorizacion import Ambito
```

(y borrar `from dataclasses import dataclass` si ya no se usa en el archivo, y el bloque `@dataclass(frozen=True, slots=True) class Ambito: ...` completo).

- [ ] **Step 15: Run the full autorizacion suite**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_autorizacion.py -q`
Expected: PASS (19 tests, sin `ImportError`, sin duplicar `Ambito`)

- [ ] **Step 16: Commit**

```bash
git add servicios/identidad/tukit_identidad/autorizacion.py servicios/identidad/tests/test_autorizacion.py
git commit -m "$(cat <<'EOF'
refactor(identidad): autorizacion.py importa Ambito desde dominio/

Ambito ya vive en dominio/autorizacion.py (Task 1); las funciones con SQL
(puede, roles_vigentes, campos_visibles, matriculas_visibles) se quedan aqui
hasta moverse a repositorios/identidad.py en la Task 2.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 17: Run the full identidad suite (regression net)**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests -q`
Expected: `110 passed` (los 106 originales + las 4 nuevas de `test_dominio_ambito.py`)

### Task 2: Scaffold `repositorios/identidad.py` — `RepoIdentidad` con todo el SQL

**Files:**
- Create: `servicios/identidad/tukit_identidad/repositorios/__init__.py`
- Create: `servicios/identidad/tukit_identidad/repositorios/identidad.py`
- Modify: `servicios/identidad/tests/test_autorizacion.py` (import de `puede/roles_vigentes/campos_visibles/matriculas_visibles`: del modulo viejo `tukit_identidad.autorizacion` al nuevo `tukit_identidad.repositorios.identidad`; la fixture `db` sigue siendo un `AsyncSession`, que expone `.execute/.scalar/.scalars` igual que un `AsyncConnection`, asi que las funciones movidas no cambian de firma)
- Delete: `servicios/identidad/tukit_identidad/autorizacion.py` (queda vacio de logica: `Ambito` ya se fue a `dominio/` en la Task 1, y las 4 funciones + `_cadena_de_contencion` se van aqui)
- Test: `servicios/identidad/tests/test_autorizacion.py` (se reusa integro; solo cambia el import, Step 3)

**Interfaces:**
- Consumes: `dominio.autorizacion.Ambito` (de la Task 1); `modelos.{AcudienteMatricula, AmbitoTipo, AsignacionRol, Clasificacion, Matricula, ORDEN_CLASIFICACION, Permiso, RolPermiso, Sede}`.
- Produces: `RepoIdentidad` con los metodos de instancia `async def puede(usuario_id, permiso, ambito) -> bool`, `async def roles_vigentes(usuario_id, ambito) -> set[str]`, `async def campos_visibles(usuario_id, recurso, ambito, clasificacion_por_campo) -> set[str]`, `async def matriculas_visibles(usuario_id) -> set[uuid.UUID]`, mas el privado `async def _cadena_de_contencion(ambito) -> list[Ambito]`. La firma cambia de funcion-modulo `f(db, usuario_id, ...)` a metodo `repo.f(usuario_id, ...)` — mismo patron que `RepoCasos`/`RepoPedidos` (conexion atada en `__init__`, no en cada llamada).

- [ ] **Step 1: Write the failing test — actualizar el import de `test_autorizacion.py`**

En `servicios/identidad/tests/test_autorizacion.py` lineas 15-19 (ya sin `Ambito`, movido en la Task 1):

```python
# antes
from tukit_identidad.autorizacion import (
    campos_visibles,
    matriculas_visibles,
    puede,
    roles_vigentes,
)
from tukit_identidad.dominio.autorizacion import Ambito
```

El test llama las 4 funciones como funciones sueltas (`puede(db, ...)`, `roles_vigentes(db, ...)`, etc.), pero el destino es un metodo de `RepoIdentidad`. Para no reescribir las 19 pruebas linea por linea, se agregan 4 wrappers de compatibilidad al PIE del archivo de test que instancian `RepoIdentidad(db)` y delegan — son las mismas funciones que el test ya conoce, ahora construidas sobre el repo:

```python
# despues (reemplaza el bloque de import de arriba)
from tukit_identidad.dominio.autorizacion import Ambito
from tukit_identidad.repositorios.identidad import RepoIdentidad


async def puede(db, usuario_id, permiso, ambito):
    return await RepoIdentidad(db).puede(usuario_id, permiso, ambito)


async def roles_vigentes(db, usuario_id, ambito):
    return await RepoIdentidad(db).roles_vigentes(usuario_id, ambito)


async def campos_visibles(db, usuario_id, recurso, ambito, clasificacion_por_campo):
    return await RepoIdentidad(db).campos_visibles(usuario_id, recurso, ambito, clasificacion_por_campo)


async def matriculas_visibles(db, usuario_id):
    return await RepoIdentidad(db).matriculas_visibles(usuario_id)
```

Este bloque va inmediatamente despues de los imports (antes de `_rol_rector`), para que las 19 pruebas existentes (que llaman `puede(db, ...)`, etc.) sigan compilando sin tocar una sola linea de assert.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_autorizacion.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tukit_identidad.repositorios'`

- [ ] **Step 3: Crear `repositorios/__init__.py` y `repositorios/identidad.py` con `RepoIdentidad`**

```python
# servicios/identidad/tukit_identidad/repositorios/__init__.py
"""El SQL de Identidad contra su propia base, detras de nombres de metodo.

No hay un Protocol de repositorio: es una sola implementacion (`RepoIdentidad`)
que las pruebas ejercen contra SQLite real, no un doble. El router (o, en el
caso de autorizacion, quien necesite resolver un permiso) abre la sesion y le
pide cada paso; el repo no decide negocio ni conoce HTTP (ADR 0019).
"""

from .identidad import RepoIdentidad

__all__ = ["RepoIdentidad"]
```

```python
# servicios/identidad/tukit_identidad/repositorios/identidad.py
"""El SQL de autorizacion: resuelve `Ambito` contra `asignacion_rol` y sus vecinas.

Todo lo que aqui vive salio, verbatim en la logica, de `autorizacion.py`: la
cadena de contencion, los roles vigentes, `puede()` y la visibilidad por campo
o por matricula. Lo unico que cambio de forma es la superficie: eran funciones
sueltas que recibian `db` en cada llamada; aqui son metodos de `RepoIdentidad`,
atado a una conexion, igual que `RepoCasos`/`RepoPedidos` en los otros
servicios. `Ambito` es dato puro y vive en `dominio/autorizacion.py`; aqui solo
el SQL que lo resuelve (ADR 0013, ADR 0019).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from ..dominio.autorizacion import Ambito
from ..modelos import (
    ORDEN_CLASIFICACION,
    AcudienteMatricula,
    AmbitoTipo,
    AsignacionRol,
    Clasificacion,
    Matricula,
    Permiso,
    RolPermiso,
    Sede,
)


class RepoIdentidad:
    """Resuelve permisos con ambito, atado a una conexion de una unidad de
    trabajo. Se construye dentro del `async with motor.sesion()` de quien la
    use, con la conexion ya abierta; no abre ni cierra la sesion."""

    def __init__(self, conexion: Any) -> None:
        self.conexion = conexion

    async def _cadena_de_contencion(self, ambito: Ambito) -> list[Ambito]:
        """Ambitos que CONTIENEN al pedido, del mas amplio al mas estrecho.

        Un rol otorgado sobre un colegio alcanza sus sedes y las matriculas de
        esas sedes. Al reves no: ser acudiente de una matricula no da autoridad
        sobre la sede. Resolver la cadena es lo que hace que la jerarquia
        funcione sin duplicar asignaciones en cada nivel.
        """
        cadena: list[Ambito] = [Ambito.global_()]

        if ambito.tipo is AmbitoTipo.GLOBAL:
            return cadena

        if ambito.tipo is AmbitoTipo.COLEGIO:
            cadena.append(ambito)
            return cadena

        if ambito.tipo is AmbitoTipo.SEDE:
            colegio_id = await self.conexion.scalar(select(Sede.colegio_id).where(Sede.id == ambito.id))
            if colegio_id:
                cadena.append(Ambito.colegio(colegio_id))
            cadena.append(ambito)
            return cadena

        # MATRICULA: sube hasta el colegio pasando por la sede.
        fila = (
            await self.conexion.execute(
                select(Matricula.sede_id, Matricula.colegio_id).where(Matricula.id == ambito.id)
            )
        ).first()
        if fila:
            cadena.append(Ambito.colegio(fila.colegio_id))
            cadena.append(Ambito.sede(fila.sede_id))
        cadena.append(ambito)
        return cadena

    async def roles_vigentes(self, usuario_id: uuid.UUID, ambito: Ambito) -> set[str]:
        """Roles que el usuario tiene vigentes sobre `ambito` o sobre algo que lo contenga."""
        cadena = await self._cadena_de_contencion(ambito)
        ahora = datetime.now(UTC)

        condiciones = [
            (AsignacionRol.ambito_tipo == a.tipo.value)
            & (AsignacionRol.ambito_id.is_(None) if a.id is None else AsignacionRol.ambito_id == a.id)
            for a in cadena
        ]

        consulta = select(AsignacionRol.rol_codigo).where(
            AsignacionRol.usuario_id == usuario_id,
            AsignacionRol.vigente_desde <= ahora,
            or_(AsignacionRol.vigente_hasta.is_(None), AsignacionRol.vigente_hasta > ahora),
            or_(*condiciones),
        )
        return set((await self.conexion.scalars(consulta)).all())

    async def puede(self, usuario_id: uuid.UUID, permiso: str, ambito: Ambito) -> bool:
        """¿Puede este usuario ejercer `permiso` sobre `ambito`?

        Falla CERRADA: sin asignacion vigente que alcance el ambito, es
        `False`. No hay rama que conceda por ausencia de contexto.
        """
        roles = await self.roles_vigentes(usuario_id, ambito)
        if not roles:
            return False

        existe = await self.conexion.scalar(
            select(RolPermiso.permiso_codigo)
            .where(RolPermiso.rol_codigo.in_(roles), RolPermiso.permiso_codigo == permiso)
            .limit(1)
        )
        return existe is not None

    async def campos_visibles(
        self,
        usuario_id: uuid.UUID,
        recurso: str,
        ambito: Ambito,
        clasificacion_por_campo: dict[str, Clasificacion],
    ) -> set[str]:
        """Campos de `recurso` que este usuario puede LEER en este ambito.

        Dos ejes, no uno. El permiso dice quien ve que; la clasificacion dice
        que tan sensible es. Un permiso `estudiante:leer` con
        `clasificacion_minima` de `interno` NO alcanza un campo clasificado
        `menor`, aunque el permiso nombre el recurso.
        """
        roles = await self.roles_vigentes(usuario_id, ambito)
        if not roles:
            return set()

        filas = (
            await self.conexion.execute(
                select(Permiso.campo, Permiso.clasificacion_minima)
                .join(RolPermiso, RolPermiso.permiso_codigo == Permiso.codigo)
                .where(RolPermiso.rol_codigo.in_(roles), Permiso.recurso == recurso, Permiso.accion == "leer")
            )
        ).all()
        if not filas:
            return set()

        # Un permiso sin `campo` cubre el recurso entero hasta su clasificacion.
        techo_general = -1
        techo_por_campo: dict[str, int] = {}
        for campo, minima in filas:
            nivel = ORDEN_CLASIFICACION[Clasificacion(minima)]
            if campo is None:
                techo_general = max(techo_general, nivel)
            else:
                techo_por_campo[campo] = max(techo_por_campo.get(campo, -1), nivel)

        return {
            campo
            for campo, clasificacion in clasificacion_por_campo.items()
            if max(techo_general, techo_por_campo.get(campo, -1)) >= ORDEN_CLASIFICACION[clasificacion]
        }

    async def matriculas_visibles(self, usuario_id: uuid.UUID) -> set[uuid.UUID]:
        """Matriculas que este usuario alcanza, por vinculo o por rol con ambito.

        Las politicas son ASIMETRICAS a proposito: para LEER basta que el
        recurso toque alguna matricula visible; para ESCRIBIR tienen que estar
        TODAS contenidas.
        """
        ahora = datetime.now(UTC)

        directas = set(
            (
                await self.conexion.scalars(
                    select(AcudienteMatricula.matricula_id).where(
                        AcudienteMatricula.usuario_id == usuario_id,
                        AcudienteMatricula.vigente_desde <= ahora,
                        or_(
                            AcudienteMatricula.vigente_hasta.is_(None),
                            AcudienteMatricula.vigente_hasta > ahora,
                        ),
                    )
                )
            ).all()
        )

        asignaciones = (
            await self.conexion.execute(
                select(AsignacionRol.ambito_tipo, AsignacionRol.ambito_id).where(
                    AsignacionRol.usuario_id == usuario_id,
                    AsignacionRol.vigente_desde <= ahora,
                    or_(AsignacionRol.vigente_hasta.is_(None), AsignacionRol.vigente_hasta > ahora),
                )
            )
        ).all()

        colegios = {a.ambito_id for a in asignaciones if a.ambito_tipo == AmbitoTipo.COLEGIO.value}
        sedes = {a.ambito_id for a in asignaciones if a.ambito_tipo == AmbitoTipo.SEDE.value}
        por_rol = {a.ambito_id for a in asignaciones if a.ambito_tipo == AmbitoTipo.MATRICULA.value}

        if colegios or sedes:
            condiciones = []
            if colegios:
                condiciones.append(Matricula.colegio_id.in_(colegios))
            if sedes:
                condiciones.append(Matricula.sede_id.in_(sedes))
            por_rol |= set((await self.conexion.scalars(select(Matricula.id).where(or_(*condiciones)))).all())

        return directas | por_rol
```

- [ ] **Step 4: Borrar `autorizacion.py` (ya vacio de logica propia)**

```bash
git rm servicios/identidad/tukit_identidad/autorizacion.py
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_autorizacion.py -q`
Expected: PASS (19 tests)

- [ ] **Step 6: Commit**

```bash
git add servicios/identidad/tukit_identidad/repositorios/__init__.py servicios/identidad/tukit_identidad/repositorios/identidad.py servicios/identidad/tests/test_autorizacion.py
git commit -m "$(cat <<'EOF'
refactor(identidad): mover el SQL de autorizacion a repositorios/identidad.py

puede/roles_vigentes/campos_visibles/matriculas_visibles/_cadena_de_contencion
pasan de funciones sueltas a metodos de RepoIdentidad, atado a una conexion
como RepoCasos/RepoPedidos. Ambito (dato puro) ya vivia en dominio/ desde la
Task 1; autorizacion.py queda sin logica propia y se borra.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Run the full identidad suite (regression net)**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests -q`
Expected: `110 passed` (106 originales + las 4 de `test_dominio_ambito.py` agregadas en la Task 1)

---

### Task 3: Mover las 15 rutas a `routers/identidad.py` y su SQL a `RepoIdentidad`

Esta es la Task grande y la de mayor riesgo: mueve los 15 handlers `@app` de
`api.py` a un `APIRouter`, y baja al `RepoIdentidad` de la Task 2 el SQL que hoy
vive inline en cada handler mas los 4 ayudantes SQL sueltos (`_armar_sesion`,
`_usuario_del_token`, `_direcciones_de`, `_limpiar_predeterminada`). El cambio de
forma es uno solo y se repite en cada ruta: `async with app.state.motor.engine.begin() as conexion:`
pasa a `async with peticion.app.state.motor.sesion() as db: repo = RepoIdentidad(await db.connection())`.
La logica de cada handler es byte-identica; lo unico que cambia es de donde sale
la conexion y que el SQL ahora se pide por nombre de metodo. La red de regresion
son las ~87 pruebas de `test_api_identidad.py` que ya ejercen estas 15 rutas
contra SQLite.

**Files:**
- Create: `servicios/identidad/tukit_identidad/routers/__init__.py`
- Create: `servicios/identidad/tukit_identidad/routers/identidad.py`
- Modify: `servicios/identidad/tukit_identidad/repositorios/identidad.py` (agregar los metodos del SQL de handler + los 4 ayudantes; ya existe de la Task 2 con el SQL de autorizacion)
- Modify: `servicios/identidad/tukit_identidad/dominio/directorio.py` (ya existe de la Task 1) — sin cambios, solo se importa desde el router
- Test: `servicios/identidad/tests/test_api_identidad.py` (se reusa integro; el `cliente` fixture construye la app igual, ahora con `include_router`)

**Interfaces:**
- Consumes: `dominio.sesiones.{emitir_token, leer_token, verificar_clave}` (Task 1); `dominio.directorio.datos_colegio_nuevo_por_dane` (Task 1); `tukit_comun.cifrado.cifrador_desde_entorno`; `tukit_comun.http.ErrorDominio`.
- Produces:
  - `router = APIRouter()` con las 15 rutas (`GET /v1/colegios`, `GET /v1/directorio/{dane}`, `GET /v1/colegios/{colegio_id}`, `PATCH /v1/colegios/{colegio_id}`, `GET /v1/grados`, `POST /v1/contactos`, `GET /v1/contactos/{usuario_id}`, `POST /v1/sesiones`, `GET /v1/sesiones/actual`, `POST /v1/sesiones/cierre`, `GET /v1/cuenta`, `GET /v1/cuenta/direcciones`, `POST /v1/cuenta/direcciones`, `PATCH /v1/cuenta/direcciones/{direccion_id}`, `DELETE /v1/cuenta/direcciones/{direccion_id}`).
  - Dos funciones puras de modulo en el router: `_token_del_encabezado(authorization) -> str | None` y `_direccion_publica(fila) -> dict` (parseo/forma, no tocan la base).
  - Nuevos metodos de `RepoIdentidad` (conexion atada en `__init__`): `async def listar_colegios(busqueda) -> list[Row]`, `async def ver_colegio(colegio_id) -> Row | None`, `async def sedes_de(colegio_id) -> list[Row]`, `async def existe_colegio(colegio_id) -> uuid | None`, `async def editar_colegio(colegio_id, valores) -> None`, `async def usuario_por_correo(correo) -> Row | None`, `async def registrar_contacto(correo) -> tuple[uuid, bool]`, `async def contacto_de(usuario_id) -> Row | None`, `async def armar_sesion(fila_usuario) -> dict` (era `_armar_sesion`), `async def usuario_del_token(usuario_id) -> Row | None` (era el cuerpo SQL de `_usuario_del_token`), `async def direcciones_de(usuario_id) -> list[Row]` (era `_direcciones_de`), `async def limpiar_predeterminada(usuario_id) -> None` (era `_limpiar_predeterminada`), `async def crear_direccion(...) -> Row`, `async def obtener_direccion(direccion_id, usuario_id) -> Row | None`, `async def editar_direccion(...) -> Row`, `async def archivar_direccion(direccion_id, usuario_id) -> int` (devuelve rowcount).

- [ ] **Step 1: Escribir la prueba que falla — que la app monte el router**

En `servicios/identidad/tests/test_api_identidad.py`, agregar una prueba de
estructura que exige que las rutas vengan de un router incluido, no de handlers
`@app` en el modulo:

```python
def test_las_rutas_vienen_de_un_router_incluido(cliente):
    # ADR 0019: api.py es solo ensamblador; las rutas viven en routers/identidad.py.
    from tukit_identidad.routers import router

    montadas = {r.path for r in router.routes}
    assert "/v1/colegios" in montadas
    assert "/v1/sesiones" in montadas
    assert "/v1/cuenta/direcciones/{direccion_id}" in montadas
```

- [ ] **Step 2: Correr la prueba, verificar que falla**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_api_identidad.py::test_las_rutas_vienen_de_un_router_incluido -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tukit_identidad.routers'`

- [ ] **Step 3: Agregar los metodos de handler-SQL a `RepoIdentidad`**

Al final de la clase `RepoIdentidad` en `servicios/identidad/tukit_identidad/repositorios/identidad.py`,
agregar los metodos que absorben el SQL inline de los handlers. Las tablas se
resuelven una vez a nivel de modulo (como en `api.py` hoy):

```python
# Al principio del modulo, junto a los imports de ..modelos:
from ..modelos import Base

COLEGIO = Base.metadata.tables["colegio"]
SEDE = Base.metadata.tables["sede"]
USUARIO = Base.metadata.tables["usuario"]
ASIGNACION_ROL = Base.metadata.tables["asignacion_rol"]
DIRECCION = Base.metadata.tables["direccion"]
```

```python
# Metodos nuevos de RepoIdentidad (mismo cuerpo SQL que api.py, ahora sobre self.conexion):
    async def listar_colegios(self, busqueda: str | None) -> list[Any]:
        from sqlalchemy import and_, func

        consulta = (
            select(
                COLEGIO.c.id,
                COLEGIO.c.nombre,
                COLEGIO.c.logo_url,
                func.count(SEDE.c.id).label("sedes"),
            )
            .select_from(
                COLEGIO.outerjoin(SEDE, and_(SEDE.c.colegio_id == COLEGIO.c.id, SEDE.c.activa.is_(True)))
            )
            .where(COLEGIO.c.activo.is_(True))
            .group_by(COLEGIO.c.id, COLEGIO.c.nombre, COLEGIO.c.logo_url)
            .order_by(COLEGIO.c.nombre)
        )
        if busqueda:
            consulta = consulta.where(func.lower(COLEGIO.c.nombre).like(f"%{busqueda.lower()}%"))
        return list(await self.conexion.execute(consulta))

    async def ver_colegio(self, colegio_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(select(COLEGIO).where(COLEGIO.c.id == colegio_id))
        ).one_or_none()

    async def sedes_de(self, colegio_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(SEDE).where(SEDE.c.colegio_id == colegio_id, SEDE.c.activa.is_(True))
            )
        )

    async def existe_colegio(self, colegio_id: uuid.UUID) -> uuid.UUID | None:
        return await self.conexion.scalar(select(COLEGIO.c.id).where(COLEGIO.c.id == colegio_id))

    async def editar_colegio(self, colegio_id: uuid.UUID, valores: dict[str, Any]) -> None:
        from sqlalchemy import update

        if valores:
            await self.conexion.execute(
                update(COLEGIO).where(COLEGIO.c.id == colegio_id).values(**valores)
            )

    async def usuario_por_correo(self, correo: str) -> Any:
        return (
            await self.conexion.execute(select(USUARIO).where(USUARIO.c.correo == correo))
        ).one_or_none()

    async def registrar_contacto(self, correo: str) -> tuple[uuid.UUID, bool]:
        from sqlalchemy import insert

        existente = await self.conexion.scalar(select(USUARIO.c.id).where(USUARIO.c.correo == correo))
        if existente is not None:
            return existente, False
        nuevo = uuid.uuid4()
        await self.conexion.execute(
            insert(USUARIO).values(id=nuevo, correo=correo, clave_hash="sin-credencial")
        )
        return nuevo, True

    async def contacto_de(self, usuario_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(
                select(USUARIO.c.correo, USUARIO.c.activo).where(USUARIO.c.id == usuario_id)
            )
        ).one_or_none()

    async def armar_sesion(self, fila_usuario: Any) -> dict[str, Any]:
        ahora = datetime.now(UTC)
        filas = await self.conexion.execute(
            select(
                ASIGNACION_ROL.c.rol_codigo, ASIGNACION_ROL.c.ambito_tipo, ASIGNACION_ROL.c.ambito_id
            ).where(
                ASIGNACION_ROL.c.usuario_id == fila_usuario.id,
                ASIGNACION_ROL.c.vigente_desde <= ahora,
                or_(ASIGNACION_ROL.c.vigente_hasta.is_(None), ASIGNACION_ROL.c.vigente_hasta > ahora),
            )
        )
        roles = [
            {
                "rol": f.rol_codigo,
                "ambito": {"tipo": f.ambito_tipo, "id": str(f.ambito_id) if f.ambito_id is not None else None},
            }
            for f in filas
        ]
        nombre = fila_usuario.correo
        if fila_usuario.nombre_cifrado is not None:
            from tukit_comun.cifrado import cifrador_desde_entorno

            nombre = cifrador_desde_entorno().descifrar(fila_usuario.nombre_cifrado).decode(
                "utf-8", errors="replace"
            )
        return {
            "usuario_id": str(fila_usuario.id),
            "correo": fila_usuario.correo,
            "nombre": nombre,
            "roles": roles,
            "version_permisos": int(fila_usuario.version_permisos),
        }

    async def usuario_del_token(self, usuario_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(select(USUARIO).where(USUARIO.c.id == usuario_id))
        ).one_or_none()

    async def direcciones_de(self, usuario_id: uuid.UUID) -> list[Any]:
        return list(
            await self.conexion.execute(
                select(DIRECCION)
                .where(DIRECCION.c.usuario_id == usuario_id, DIRECCION.c.archivada_en.is_(None))
                .order_by(DIRECCION.c.predeterminada.desc(), DIRECCION.c.creado_en)
            )
        )

    async def limpiar_predeterminada(self, usuario_id: uuid.UUID) -> None:
        from sqlalchemy import update

        await self.conexion.execute(
            update(DIRECCION)
            .where(
                DIRECCION.c.usuario_id == usuario_id,
                DIRECCION.c.predeterminada.is_(True),
                DIRECCION.c.archivada_en.is_(None),
            )
            .values(predeterminada=False)
        )

    async def crear_direccion(self, **valores: Any) -> Any:
        from sqlalchemy import insert

        nueva = uuid.uuid4()
        await self.conexion.execute(insert(DIRECCION).values(id=nueva, **valores))
        return (await self.conexion.execute(select(DIRECCION).where(DIRECCION.c.id == nueva))).one()

    async def obtener_direccion(self, direccion_id: uuid.UUID, usuario_id: uuid.UUID) -> Any:
        return (
            await self.conexion.execute(
                select(DIRECCION).where(
                    DIRECCION.c.id == direccion_id,
                    DIRECCION.c.usuario_id == usuario_id,
                    DIRECCION.c.archivada_en.is_(None),
                )
            )
        ).one_or_none()

    async def editar_direccion(self, direccion_id: uuid.UUID, **valores: Any) -> Any:
        from sqlalchemy import update

        await self.conexion.execute(
            update(DIRECCION).where(DIRECCION.c.id == direccion_id).values(**valores)
        )
        return (await self.conexion.execute(select(DIRECCION).where(DIRECCION.c.id == direccion_id))).one()

    async def archivar_direccion(self, direccion_id: uuid.UUID, usuario_id: uuid.UUID) -> int:
        from sqlalchemy import update

        resultado = await self.conexion.execute(
            update(DIRECCION)
            .where(
                DIRECCION.c.id == direccion_id,
                DIRECCION.c.usuario_id == usuario_id,
                DIRECCION.c.archivada_en.is_(None),
            )
            .values(archivada_en=datetime.now(UTC), predeterminada=False)
        )
        return resultado.rowcount
```

- [ ] **Step 4: Crear `routers/__init__.py`**

```python
# servicios/identidad/tukit_identidad/routers/__init__.py
"""El adaptador de entrada HTTP de Identidad: parsear, verificar token, traducir.

Un solo router (`identidad`) que `api.py` monta. Parsea la peticion (incluidos
los 422 de forma), resuelve el token, pide el SQL a `repositorios/` y las reglas
puras a `dominio/`, y traduce el resultado a un sobre de respuesta o de error. No
arma SQL ni conoce el motor mas alla de `peticion.app.state` (ADR 0019).
"""

from .identidad import router

__all__ = ["router"]
```

- [ ] **Step 5: Crear `routers/identidad.py` con las 15 rutas**

Cada handler conserva su docstring y su logica; solo cambia (a) `@app.` por
`@router.`, (b) recibe `peticion: Request` para llegar a `app.state.motor`, y (c)
`engine.begin()` -> `motor.sesion()` + `RepoIdentidad(await db.connection())`. Se
muestran las tres formas representativas; las 12 restantes siguen exactamente el
mismo patron sobre los metodos de repo del Step 3:

```python
# servicios/identidad/tukit_identidad/routers/identidad.py  (extracto representativo)
from __future__ import annotations

import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, Field
from tukit_comun.cifrado import cifrador_desde_entorno
from tukit_comun.http import ErrorDominio

from ..dominio.directorio import datos_colegio_nuevo_por_dane
from ..dominio.sesiones import emitir_token, leer_token, verificar_clave
from ..repositorios import RepoIdentidad

router = APIRouter()

_FORMA_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

GRADOS = (
    "Parvulos", "Prejardin", "Jardin", "Transicion", "Primero", "Segundo",
    "Tercero", "Cuarto", "Quinto", "Sexto", "Septimo", "Octavo", "Noveno",
    "Decimo", "Once",
)


def _token_del_encabezado(authorization: str | None) -> str | None:
    if not authorization:
        return None
    partes = authorization.split(" ", 1)
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1].strip()
    return authorization.strip()


def _direccion_publica(fila: Any) -> dict[str, Any]:
    cifrador = cifrador_desde_entorno()
    linea = cifrador.descifrar(fila.linea_cifrada).decode("utf-8", errors="replace")
    contacto = None
    if fila.contacto_cifrado is not None:
        contacto = cifrador.descifrar(fila.contacto_cifrado).decode("utf-8", errors="replace")
    return {
        "direccion_id": str(fila.id),
        "etiqueta": fila.etiqueta,
        "ciudad": fila.ciudad,
        "localidad": fila.localidad,
        "linea": linea,
        "contacto": contacto,
        "predeterminada": bool(fila.predeterminada),
    }


async def _usuario_del_token(peticion: Request, authorization: str | None, repo: RepoIdentidad) -> Any:
    token = _token_del_encabezado(authorization)
    payload = leer_token(token) if token else None
    if payload is None:
        raise ErrorDominio("sesion_invalida", "El token no es valido o expiro.", estado=401)
    fila = await repo.usuario_del_token(uuid.UUID(payload["sub"]))
    if fila is None or not fila.activo:
        raise ErrorDominio("sesion_invalida", "La cuenta ya no esta activa.", estado=401)
    if int(payload.get("vp", -1)) != int(fila.version_permisos):
        raise ErrorDominio("sesion_revocada", "La sesion fue revocada. Vuelve a entrar.", estado=401)
    return fila


@router.get("/v1/colegios", tags=["colegios"], summary="Colegios activos, con su numero de sedes")
async def listar_colegios(
    peticion: Request,
    busqueda: Annotated[str | None, Query(description="Texto en el nombre")] = None,
) -> dict[str, Any]:
    async with peticion.app.state.motor.sesion() as db:
        filas = await RepoIdentidad(await db.connection()).listar_colegios(busqueda)
    datos = [
        {"colegio_id": str(f.id), "nombre": f.nombre, "sedes": int(f.sedes), "logo_url": f.logo_url}
        for f in filas
    ]
    return {"total": len(datos), "colegios": datos}


class Credenciales(BaseModel):
    correo: str = Field(min_length=5, max_length=320)
    clave: str = Field(min_length=1, max_length=256)


@router.post("/v1/sesiones", tags=["sesion"], summary="Inicia sesion: correo + clave -> token con roles.")
async def iniciar_sesion(peticion: Request, credenciales: Credenciales) -> dict[str, Any]:
    correo = str(credenciales.correo).strip().lower()
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await repo.usuario_por_correo(correo)
        if fila is None or not fila.activo or not verificar_clave(credenciales.clave, fila.clave_hash):
            raise ErrorDominio(
                "credenciales_invalidas", "El correo o la clave no son correctos.", estado=401, campo="correo"
            )
        sesion = await repo.armar_sesion(fila)
    token = emitir_token(fila.id, fila.version_permisos)
    return {"sesion": sesion, "token": token}


@router.delete(
    "/v1/cuenta/direcciones/{direccion_id}",
    tags=["cuenta"],
    status_code=204,
    summary="Archiva una direccion mia. Baja logica: un envio en curso la sigue viendo.",
)
async def archivar_direccion(
    peticion: Request,
    direccion_id: uuid.UUID,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    async with peticion.app.state.motor.sesion() as db:
        repo = RepoIdentidad(await db.connection())
        fila = await _usuario_del_token(peticion, authorization, repo)
        if await repo.archivar_direccion(direccion_id, fila.id) == 0:
            raise ErrorDominio("direccion_no_existe", "No hay ninguna direccion tuya con ese id.", estado=404)
    return None

# ... las 12 rutas restantes (directorio, ver_colegio, editar_colegio, grados,
# contactos POST/GET, sesiones/actual, sesiones/cierre, cuenta, cuenta/direcciones
# GET/POST/PATCH) siguen el MISMO patron: @router, peticion: Request,
# motor.sesion() + RepoIdentidad, misma logica y mismos docstrings que api.py.
```

> Nota (Anexo M): `editar_colegio` reusa `ver_colegio(peticion, colegio_id)`
> como hoy — la llamada interna se mantiene, ahora ambas son funciones de
> router y comparten la misma sesion abriendo una segunda; es identico al
> comportamiento actual (dos `engine.begin()` secuenciales).

- [ ] **Step 6: Correr la prueba de estructura, verificar que pasa**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_api_identidad.py::test_las_rutas_vienen_de_un_router_incluido -q`
Expected: FAIL todavia — `api.py` aun define los `@app` y no incluye el router. Se arregla en la Task 4 (el router existe pero la app no lo monta hasta que api.py sea el ensamblador). Dejar la prueba en rojo y continuar; el verde llega al final de la Task 4.

- [ ] **Step 7: Commit del router + repo (sin tocar api.py todavia)**

```bash
git add servicios/identidad/tukit_identidad/routers servicios/identidad/tukit_identidad/repositorios/identidad.py servicios/identidad/tests/test_api_identidad.py
git commit -m "$(cat <<'EOF'
refactor(identidad): rutas a routers/identidad.py y su SQL a RepoIdentidad

Las 15 rutas pasan de handlers @app en api.py a un APIRouter, y el SQL que
vivia inline en cada handler (mas _armar_sesion/_usuario_del_token/
_direcciones_de/_limpiar_predeterminada) baja a metodos de RepoIdentidad. El
cambio de forma es uno solo por ruta: engine.begin() -> motor.sesion() +
RepoIdentidad(await db.connection()). Logica byte-identica. api.py todavia
define los @app; la Task 4 lo convierte en ensamblador y monta el router.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Adelgazar `api.py` al ensamblador y montar el router

`api.py` deja de tener rutas: queda solo el `crear_app` + `include_router` +
`main()`, calcado de `operacion/api.py`. Es el paso que pone en verde tanto la
prueba de estructura de la Task 3 como TODA la suite de API existente, porque
las 15 rutas vuelven a estar montadas (ahora via router).

**Files:**
- Modify: `servicios/identidad/tukit_identidad/api.py` (de 681 lineas a ~50; borra los 15 handlers, las clases Pydantic movidas al router, los 4 ayudantes SQL movidos al repo, las constantes movidas al router)
- Test: `servicios/identidad/tests/test_api_identidad.py` (integro, sin cambios)

**Interfaces:**
- Consumes: `tukit_comun.bd.crear_motor`, `tukit_comun.http.crear_app`, `.routers.router`.
- Produces: `app = crear_app(...); app.include_router(router)` + `main()`. Mismo `PUERTO_POR_OMISION = 8011`. La app expone exactamente las mismas 15 rutas (+ `/salud` que inyecta `crear_app`).

- [ ] **Step 1: Reemplazar `api.py` por el ensamblador**

Contenido COMPLETO nuevo de `servicios/identidad/tukit_identidad/api.py` (calcado de `operacion/api.py`):

```python
"""La superficie minima de Identidad: monta el router y ata el motor.

Identidad es la frontera de cumplimiento del sistema: aqui viven los datos de
menores, asi que cada ruta que se abre hay que poder defenderla (Anexo M). Las
rutas — colegios/sedes/grados, contacto, sesiones y "mi cuenta" — viven en
`routers/identidad.py`; el SQL en `repositorios/identidad.py`; las reglas puras
(token, autorizacion, directorio) en `dominio/`. Este modulo solo ensambla
(ADR 0019).

    python -m tukit_identidad.api            # localhost:8011
"""

from __future__ import annotations

import argparse

from fastapi import FastAPI
from tukit_comun.bd import crear_motor
from tukit_comun.http import crear_app

from .routers import router

PUERTO_POR_OMISION = 8011


async def _arrancar(app: FastAPI) -> None:
    app.state.motor = crear_motor("identidad")


async def _apagar(app: FastAPI) -> None:
    await app.state.motor.cerrar()


app = crear_app(
    titulo="Tukit Identidad",
    descripcion=(
        "Colegios, sedes y grados para que el acudiente escoja, registro del contacto "
        "que convierte un correo en un identificador, sesiones y mi cuenta. Contrato: seccion 12.4."
    ),
    al_arrancar=_arrancar,
    al_apagar=_apagar,
)
app.include_router(router)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Levanta la API de Identidad.")
    analizador.add_argument("--puerto", type=int, default=PUERTO_POR_OMISION)
    analizador.add_argument("--host", default="127.0.0.1")
    argumentos = analizador.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=argumentos.host, port=argumentos.puerto, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Correr la prueba de estructura de la Task 3, verificar que pasa**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_api_identidad.py::test_las_rutas_vienen_de_un_router_incluido -q`
Expected: PASS

- [ ] **Step 3: Correr TODA la suite de API (la red de regresion real)**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_api_identidad.py -q`
Expected: PASS — mismas ~87 pruebas verdes. Incluye la guardiana de superficie
`test_el_esquema_publicado_no_anuncia_ninguna` (:241): el `set(app.openapi()['paths'])`
tiene que ser IDENTICO al de antes (las mismas 13/15 rutas publicadas), porque
no agregamos ni quitamos rutas, solo las movimos.

- [ ] **Step 4: Commit**

```bash
git add servicios/identidad/tukit_identidad/api.py
git commit -m "$(cat <<'EOF'
refactor(identidad): api.py queda como ensamblador y monta el router

De 681 lineas a ~50, calcado de operacion/api.py: crear_motor al arrancar,
crear_app + include_router, main(). Las 15 rutas ya viven en routers/ y su SQL
en repositorios/ desde la Task 3; este commit las vuelve a montar y pone en
verde la suite completa. Cierra el split ADR 0019 de Identidad.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Compuerta de Fase 1 — suite completa verde y api.py adelgazado

Tarea de verificacion, sin codigo nuevo: confirma que el split no cambio ningun
comportamiento observable. Cualquier rojo aqui significa que una extraccion
cambio la logica y hay que revertir el commit culpable, no parchear el sintoma.

**Files:**
- (ninguno — solo se corre y se lee)

**Interfaces:**
- Consumes: todo lo producido en Tasks 1-4.
- Produces: la certeza de que Fase 1 es un refactor puro. Fase 2 arranca sobre `dominio/`, `repositorios/identidad.py` y `routers/identidad.py`.

- [ ] **Step 1: Suite completa de identidad verde**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests -q`
Expected: `110 passed` (106 originales + 4 de `test_dominio_ambito.py`). Cero fallos, cero errores.

- [ ] **Step 2: Confirmar que api.py es ensamblador (sin rutas propias)**

Run: `rg -c "@app\.(get|post|patch|delete|put)" servicios/identidad/tukit_identidad/api.py`
Expected: sin coincidencias (exit 1) — ningun decorador de ruta queda en `api.py`.

- [ ] **Step 3: Confirmar la conversion de idiom (sin engine.begin en routers)**

Run: `rg -c "engine\.begin" servicios/identidad/tukit_identidad/routers/identidad.py`
Expected: sin coincidencias (exit 1) — el router usa `motor.sesion()`, no `engine.begin()`.

- [ ] **Step 4: Confirmar la superficie publicada intacta (Anexo M)**

Run: `uv run --package tukit-identidad pytest servicios/identidad/tests/test_api_identidad.py -k superficie -q`
Expected: PASS — la guardiana de superficie sigue verde: el split no anuncio
ninguna ruta nueva de menores.

- [ ] **Step 5: Commit de cierre de fase (opcional, si algo quedo pendiente)**

Si los Steps 1-4 pasan sin tocar nada, no hay commit: Fase 1 ya quedo en los
commits de las Tasks 1-4. Si algun ajuste menor fue necesario para poner en
verde, va en un commit:

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor(identidad): cierre de Fase 1 — split ADR 0019 completo y suite verde

Compuerta: 110 pruebas verdes, api.py sin rutas propias, routers/ sin
engine.begin, superficie publicada intacta. Fase 1 es un refactor puro; Fase 2
construye sobre dominio/ + repositorios/ + routers/.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```
