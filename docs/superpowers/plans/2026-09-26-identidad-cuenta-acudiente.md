# Plan — Identidad ADR-0019 + cuenta de acudiente (sub-proyecto A)

> **Estado:** propuesta, pendiente de aprobación. **NO se escribe código de
> implementación hasta que este plan esté aprobado.**

## Goal

Refactorizar el servicio **identidad** al patrón ADR-0019 (partir el monolito
`api.py` de 681 líneas en `api.py`-ensamblador + `routers/` + `dominio/` +
`repositorios/`) y, sobre esa base limpia, construir el **alta de cuenta del
acudiente con contraseña como paso 1 de `/empezar`** (cuentas reales desde el
minuto uno), los **hijos como apodos cifrados** (Ley 1581 / Anexo M: el nombre
del menor nunca en claro, y el apodo también cifrado), y un **panel de
acudientes por colegio en Admin** con el estado del trabajo de cada uno.

## Architecture

ADR-0019 "puertos y adaptadores ligero", calcado del servicio **operacion** que
ya lo aplica:

- **`api.py`** — solo ensambla: crea el motor y los clientes, los cuelga de
  `app.state`, monta el router. Nada de rutas ni SQL.
- **`routers/`** — adaptador HTTP: parsea la petición (incluidos los 422 de
  forma), llama al dominio por las reglas y al repo por las consultas, traduce a
  sobres de respuesta/error. No calcula negocio ni arma SQL.
- **`dominio/`** — puro, sin I/O: reglas, decisiones, validaciones. Se prueba
  sin fixtures.
- **`repositorios/`** — todo el SQL. `class RepoX(conexion)` con la conexión
  atada en `__init__` (mismo patrón que `RepoCasos`/`RepoPedidos`; sin Protocol).

Autorización: se **extiende** el RBAC por ámbitos del **ADR-0013**
(`Ambito`/`AmbitoTipo`, roles, permisos con techo de clasificación por campo).
No se inventa un modelo nuevo.

Frontend: Next.js App Router — `apps/web` (público, el acudiente), `apps/admin`
(back-office). El contrato compartido `@tukit/contrato` (`OrigenDatos` +
`ClienteApi` HTTP) es la única superficie; un solo gateway (`TUKIT_API_URL`); el
token va en cookie httpOnly puesta por Route Handlers, nunca lo ve el navegador.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy Core (async), `tukit_comun` (`crear_app`,
  `crear_motor`, `MotorServicio`, `ErrorDominio`, `cifrador_desde_entorno`).
- **Migraciones:** Alembic autoritativo (`make` corre `alembic upgrade head`);
  `create_all` solo para arranque-desde-cero y pruebas.
- **Frontend:** Next.js App Router; `@tukit/contrato` (TS). Pruebas de contrato
  con `node --test`; `apps/web`/`apps/admin` sin runner → se verifican por
  `tsc --noEmit` (`npm run typecheck`) + e2e manual documentado.
- **Seguridad:** PBKDF2 para la clave + tokens HMAC (`dominio/sesiones.py`).
  Registro progresivo por el centinela `sin-credencial`.

## Spec

`docs/superpowers/specs/2026-09-26-identidad-cuenta-acudiente-design.md`
(APROBADA y commiteada). Decisiones fijas: contraseña en el paso 1; calidad
tesis-grado (`REVISION_ARQUITECTURA.md` vinculante); extender el RBAC del
ADR-0013, no inventar.

## Global Constraints

- **TDD estricto (RED → GREEN).** Cada tarea de lógica no trivial: escribir el
  test que falla → correrlo y ver FALLAR → impl mínima → correr y ver PASAR →
  commit. Dominio puro se prueba sin fixtures; lo que toca I/O, contra SQLite
  (StaticPool) en memoria.
- **Sin placeholders.** Nada de `TODO`/`pass`/stubs que no compilan. Cada tarea
  deja el árbol en verde.
- **Ley 1581 / Anexo M.** El nombre de un menor nunca viaja ni se persiste en
  claro; el hijo se referencia por apodo, y el apodo también se cifra. El nombre
  del adulto es **PERSONAL**, no MENOR.
- **PONYTAIL activo** — de-overengineering; marcar los cortes deliberados con
  comentario `ponytail:` nombrando el techo y la vía de mejora.
- **Fuera de alcance:** el estado de despacho/entrega es el sub-proyecto C.
- **Git:** commitear/pushear como MapaRuiz (`@javeriana.edu.co`), NUNCA el correo
  corporativo. Cada mensaje de commit termina en
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## Review Focus

- ¿`api.py` quedó como puro ensamblador (sin `@app.<verbo>` ni `engine.begin()`
  en las rutas)? ¿Los routers no arman SQL? ¿El dominio no hace I/O?
- ¿El apodo del menor nunca aparece en claro en base, logs ni respuestas?
- ¿La cuenta del paso 1 crea una sesión real y el kit viaja autenticado (la
  tubería resuelve `usuario_id` de la sesión, no re-registra contacto)?
- ¿El guardian de esquema publicado sigue siendo exacto tras cada ruta nueva?
- ¿Cada tarea tiene su RED antes del GREEN, y un commit al final?

---

## Fases

- **Fase 1 (Tasks 1–5):** refactor ADR-0019 de identidad. Sin cambio de
  comportamiento observable — el esquema publicado no se mueve.
- **Fase 2 backend (Tasks 20–25):** migración `celular` + `apodo_cifrado`,
  `dominio/cuenta.py`, permisos, repo de alta, rutas `POST /v1/cuenta` +
  `/v1/cuenta/hijos`.
- **Fase 2 tubería + web (Tasks 26–29):** la tubería confía en el `usuario_id`
  de la sesión; `crearCuenta` en el contrato; Route Handler con cookie;
  `/empezar` arranca por la cuenta.
- **Fase 2 admin (Tasks 30–33):** endpoint de acudientes por colegio; contrato;
  fix Dolor-1; panel en `/colegios/{id}`.


---

# Fase 1 — Refactor ADR-0019 de identidad (Tasks 1–5)

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
    "Parvulos",
    "Prejardin",
    "Jardin",
    "Transicion",
    "Primero",
    "Segundo",
    "Tercero",
    "Cuarto",
    "Quinto",
    "Sexto",
    "Septimo",
    "Octavo",
    "Noveno",
    "Decimo",
    "Once",
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


---

# Fase 2 backend (Tasks 20–25)

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


---

## Fase 2 — Tubería + Web (Tasks 26–29)

Cierra el lazo del alta: la tubería de inteligencia deja de re-registrar
contacto cuando ya hay un `usuario_id` de sesión, el contrato TypeScript
aprende `crearCuenta`, un Route Handler pone la cookie httpOnly, y `/empezar`
arranca por la cuenta (paso 1) con un interruptor "Ya tengo cuenta".

**Precondición:** las Tasks 20–25 (Fase 2 backend) están en verde. El endpoint
`POST /v1/cuenta` ya existe y devuelve `{sesion, token}`.

---

### Task 26 — La tubería confía en el `usuario_id` de la sesión

**Contexto.** `subir_listas` (`servicios/inteligencia/tukit_inteligencia/api.py`,
def en :499) re-registra el contacto SIEMPRE, aunque el acudiente ya venga
autenticado. El defecto está en :632–636:

```python
contacto_referencia: str | None = None
if contacto and contacto.correo:
    contacto_referencia = await _identidad().registrar_contacto(contacto.correo, contacto.celular)
```

`trabajos.crear` (`trabajos.py:137`) ya trae el patrón correcto — el guard de
:160 es `if usuario_id is None and contacto and contacto.get("correo"):`. La
tubería debe mirar primero el `usuario_id` que viaja en la sesión y solo caer
al registro-por-contacto cuando no hay sesión (el flujo anónimo heredado sigue
vivo hasta que toda la web migre).

No hay lector de token en `api.py` de inteligencia hoy. El `usuario_id` llega
por cabecera `Authorization: Bearer <token>` desde el Route Handler; el propio
servicio de inteligencia no valida el token (no tiene la clave HMAC) — se lo
pasa a Identidad, que ya expone `GET /v1/sesion` (`usuario_del_token`). Para no
sostener un await de red dentro de la sesión de base (mismo cuidado que
`operacion/routers/operacion.py:186`), el `usuario_id` se resuelve ANTES de
abrir cualquier trabajo.

**26.1 — Test RED: `subir_listas` con sesión no vuelve a registrar contacto**

Añadir a `servicios/inteligencia/tests/test_api_inteligencia.py` (usa el mismo
doble de Identidad que las pruebas existentes — un `ClienteIdentidad` falso
colgado de `app.state.identidad`). El doble cuenta las llamadas a
`registrar_contacto` y expone `usuario_del_token`:

```python
async def test_subir_listas_con_sesion_no_reregistra_contacto(cliente, identidad_doble):
    identidad_doble.usuario_por_token["tok-acudiente"] = "11111111-1111-1111-1111-111111111111"
    respuesta = await cliente.post(
        "/v1/listas",
        headers={"Authorization": "Bearer tok-acudiente"},
        files=_archivo_lista_valido(),
        data={"colegio_id": COLEGIO_PILOTO, "grado": "5"},
    )
    assert respuesta.status_code == 202
    assert identidad_doble.registros == 0  # ya venía autenticado: no re-registra
```

Correr y ver **FAIL** (hoy siempre llama a `registrar_contacto`, o `usuario_por_token`
no existe en el doble).

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_api_inteligencia.py -k con_sesion_no_reregistra -x
```

**26.2 — Ampliar el doble de Identidad y añadir el lector de token**

En el doble de pruebas (donde vive el `ClienteIdentidad` falso), añadir:

```python
self.usuario_por_token: dict[str, str] = {}
self.registros = 0


async def usuario_del_token(self, token: str) -> str | None:
    return self.usuario_por_token.get(token)


async def registrar_contacto(self, correo, celular=None):
    self.registros += 1
    return "22222222-2222-2222-2222-222222222222"
```

Y en `remoto.py` (`ClienteIdentidad`, junto a `registrar_contacto` :212) el
método real:

```python
async def usuario_del_token(self, token: str) -> str | None:
    """Resuelve el Bearer a un usuario_id contra Identidad. None si no vale."""
    try:
        r = await self._cliente.get("/v1/sesion", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()["sesion"]["usuario"]["id"]
    except httpx.HTTPError:
        return None
```

**26.3 — Impl mínima en `subir_listas`**

Leer el Bearer al inicio del handler (helper local, no hace falta uno global
para un solo uso), resolverlo a `usuario_id` ANTES de la sesión de base, y
pasar `usuario_id` a `trabajos.crear` — que ya sabe no registrar contacto
cuando lo recibe. El bloque :632–636 se colapsa: `contacto_referencia` solo se
calcula en la rama sin sesión.

```python
# cerca del inicio de subir_listas, tras parsear la forma
autorizacion = request.headers.get("Authorization", "")
token = autorizacion[7:] if autorizacion.startswith("Bearer ") else None
usuario_id = await _identidad().usuario_del_token(token) if token else None
```

Y en el punto donde hoy está :632–636, reemplazar por el guard que refleja
`trabajos.py:160`:

```python
contacto_referencia: str | None = None
if usuario_id is None and contacto and contacto.correo:
    contacto_referencia = await _identidad().registrar_contacto(contacto.correo, contacto.celular)
```

Pasar `usuario_id=usuario_id` a la llamada de `trabajos.crear` dentro de
`subir_listas` (hoy no lo pasa; `crear` ya acepta el kwarg, :137).

**26.4 — Test GREEN + no-regresión del flujo anónimo**

Correr el test nuevo y el que ya cubre el alta anónima (sin cabecera → sí
registra contacto, `registros == 1`):

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_api_inteligencia.py -x
```

Ver **PASS**. El flujo anónimo sigue registrando; el autenticado ya no.

**26.5 — Commit**

```bash
git add servicios/inteligencia/
git commit -m "inteligencia: subir_listas confía en el usuario_id de la sesión

Cuando el acudiente ya viene autenticado (Bearer), resolver el usuario_id
contra Identidad y no re-registrar el contacto. El flujo anónimo heredado
sigue registrando por contacto. Refleja el guard de trabajos.crear (ADR-0013).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 27 — El contrato TypeScript aprende `crearCuenta`

**Contexto.** `libs/ts/tukit-contrato/src/origen.ts` define `Credenciales`
(:100) y la interfaz `OrigenDatos` (:100–159) — tiene `iniciarSesion` pero no
`crearCuenta`. `cliente-http.ts` (:160–214) implementa `iniciarSesion` con
`this.pedir<{sesion; token}>("/v1/sesiones", …)`. El paquete SÍ tiene runner de
pruebas (`package.json`: `node --test "test/**/*.test.ts"`; existe
`test/atributos.test.ts`).

**27.1 — Test RED: el doble de `OrigenDatos` cumple `crearCuenta`**

Crear `libs/ts/tukit-contrato/test/cuenta.test.ts`. Primero un doble mínimo que
implemente `OrigenDatos` con `crearCuenta`, y una aserción de forma sobre lo que
devuelve (`{sesion, token}`). Esto es el "primer test double de OrigenDatos"
que el spec pide: fija el contrato antes que la impl HTTP.

```ts
import { test } from "node:test";
import assert from "node:assert/strict";
import type { OrigenDatos, NuevaCuenta } from "../src/origen.ts";

test("crearCuenta devuelve sesión y token", async () => {
  const origen = new OrigenFalso();
  const nueva: NuevaCuenta = { correo: "ana@ej.com", clave: "clave-fuerte", celular: "+57 300 000 0000" };
  const { sesion, token } = await origen.crearCuenta(nueva);
  assert.equal(sesion.usuario.correo, "ana@ej.com");
  assert.ok(token.length > 0);
});
```

Correr y ver **FAIL** (no compila: `NuevaCuenta`/`crearCuenta` no existen).

```bash
cd libs/ts/tukit-contrato && npm test
```

**27.2 — Impl: tipo + método en la interfaz + impl HTTP**

En `origen.ts`, junto a `Credenciales`:

```ts
export interface NuevaCuenta extends Credenciales {
  celular?: string;
}
```

En la interfaz `OrigenDatos`, junto a `iniciarSesion`:

```ts
crearCuenta(cuenta: NuevaCuenta): Promise<{ sesion: Sesion; token: string }>;
```

En `cliente-http.ts` (`ClienteApi`), reflejando `iniciarSesion`:

```ts
crearCuenta(cuenta: NuevaCuenta): Promise<{ sesion: Sesion; token: string }> {
  return this.pedir<{ sesion: Sesion; token: string }>("/v1/cuenta", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuenta),
  });
}
```

Completar el `OrigenFalso` del test con las demás firmas de `OrigenDatos` que
haga falta para compilar (mínimo: las que ya usan otros dobles; si no hay, dejar
`throw new Error("no usado")` en los métodos que el test no ejerce —
`ponytail:` doble de prueba, solo `crearCuenta` se ejerce aquí).

**27.3 — Test GREEN + typecheck del paquete**

```bash
cd libs/ts/tukit-contrato && npm test && npm run build
```

Ver **PASS** y build limpio.

**27.4 — Commit**

```bash
git add libs/ts/tukit-contrato/
git commit -m "contrato: crearCuenta en OrigenDatos + ClienteApi

Tipo NuevaCuenta (Credenciales + celular opcional), método crearCuenta en la
interfaz y su impl HTTP contra POST /v1/cuenta. Primer test double de
OrigenDatos fija la forma {sesion, token}.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 28 — Route Handler: `POST /empezar/api/cuenta` pone la cookie

**Contexto.** `apps/web/src/app/api/sesion/route.ts` es el molde: llama a
`origenDeDatos().iniciarSesion(cred)`, y hace
`respuesta.cookies.set(COOKIE_SESION, token, {httpOnly:true, sameSite:"lax",
secure: prod, path:"/", maxAge: 60*60*8})`. Usa `destinoDe`, `respuestaDeError`,
`urlAdmin`, `export const dynamic = "force-dynamic"`. `apps/web` NO tiene runner
de pruebas — este handler se verifica por `tsc --noEmit` (script `typecheck`) y
por el e2e manual del formulario.

**28.1 — Escribir el handler**

Crear `apps/web/src/app/empezar/api/cuenta/route.ts`, calcado de
`api/sesion/route.ts` pero llamando a `crearCuenta`:

```ts
import { NextResponse } from "next/server";
import { origenDeDatos } from "@/lib/origen";
import { COOKIE_SESION, respuestaDeError } from "@/lib/sesion"; // mismos imports que api/sesion
import type { NuevaCuenta } from "@tukit/contrato";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request) {
  try {
    const cuerpo = (await peticion.json()) as NuevaCuenta;
    const { sesion, token } = await origenDeDatos().crearCuenta(cuerpo);
    const respuesta = NextResponse.json({ sesion });
    respuesta.cookies.set(COOKIE_SESION, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 8,
    });
    return respuesta;
  } catch (e) {
    return respuestaDeError(e);
  }
}
```

Reutilizar EXACTAMENTE los helpers/constantes que `api/sesion/route.ts`
importa (leerlo primero y copiar los mismos nombres de import — `COOKIE_SESION`,
`respuestaDeError`, `origenDeDatos`). No inventar nuevos.

**28.2 — Typecheck**

```bash
cd apps/web && npm run typecheck
```

Ver salida limpia.

**28.3 — Commit**

```bash
git add apps/web/src/app/empezar/api/cuenta/
git commit -m "web: Route Handler POST /empezar/api/cuenta

Crea la cuenta contra el gateway y pone el token en cookie httpOnly (mismo
patrón que /api/sesion). El navegador nunca ve el token.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 29 — `/empezar` arranca por la cuenta (paso 1) + "Ya tengo cuenta"

**Contexto.** `FormularioEmpezar.tsx` ('use client') tiene `correo`/`celular`
useState (:362–363), el gate `listo` (:395–398), el `contacto` que se arma
(:419), y la sección "A dónde te avisamos" numerada como paso 2 (:741–775). El
spec fija: **contraseña en el paso 1**, cuentas reales desde el minuto uno.
Antes de armar el kit, hay una cuenta.

El cambio se verifica por `tsc` (no hay runner en `apps/web`) + el e2e manual.

**29.1 — Añadir estado de cuenta y el interruptor**

Junto a los useState de `correo`/`celular`, añadir:

```ts
const [clave, setClave] = useState("");
const [yaTengoCuenta, setYaTengoCuenta] = useState(false);
const [sesionLista, setSesionLista] = useState(false);
```

`sesionLista` marca que el paso 1 quedó resuelto (cuenta creada o sesión
iniciada) antes de habilitar el envío del kit.

**29.2 — Reescribir la sección de contacto como paso 1 "Tu cuenta"**

Reemplazar la sección `~741–775` (hoy "paso 2 · A dónde te avisamos") por el
paso 1 con correo + celular + **contraseña**, más el enlace "Ya tengo cuenta"
que alterna a modo inicio-de-sesión (sin celular). Renumerar los pasos que
siguen (preferencias pasa de 3 a 2, etc. — buscar los `<span className={styles.paso}>`
y correr la numeración).

Copy del bloque (respetando el tono existente — frases cortas, tú):

```tsx
<section className={styles.bloque} aria-labelledby={`${idBase}-cuenta`}>
  <h2 id={`${idBase}-cuenta`} className={styles.tituloBloque}>
    <span className={styles.paso}>1</span> Tu cuenta
  </h2>
  <p className={styles.explicacion}>
    Creas tu cuenta primero. Así guardamos tus kits y te escribimos cuando estén
    listos — armar el kit toma minutos, no segundos.
  </p>
  {/* correo, celular (solo si !yaTengoCuenta), clave */}
  {/* botón crear cuenta / iniciar sesión → llama al handler y setSesionLista(true) */}
  <button type="button" className={styles.enlaceSecundario}
          onClick={() => setYaTengoCuenta(v => !v)}>
    {yaTengoCuenta ? "Quiero crear una cuenta" : "Ya tengo cuenta"}
  </button>
</section>
```

**29.3 — Conectar el paso 1 a los handlers**

Un handler local `resolverCuenta()` que:
- si `yaTengoCuenta`: `POST /api/sesion` con `{correo, clave}`.
- si no: `POST /empezar/api/cuenta` con `{correo, clave, celular}`.
- en éxito: `setSesionLista(true)` (la cookie ya quedó puesta por el Route
  Handler; el formulario no toca el token).
- en 409 (`correo_ya_registrado`): mensaje "Ese correo ya tiene cuenta — inicia
  sesión" y `setYaTengoCuenta(true)`.

**29.4 — El gate `listo` exige la sesión; quitar `contacto` del envío del kit**

Actualizar el gate `listo` (:395) para pedir `sesionLista` en vez de validar
`correo`/`celular` sueltos:

```ts
const listo = sesionLista && hijos.every(hijoListo);
```

En las tres ramas de envío (`aplicarCanonico` :455, `crearTrabajo` :478,
`subirListas` :494) dejar de mandar `contacto` — el kit ya viaja autenticado por
la cookie; la tubería resuelve el `usuario_id` de la sesión (Task 26). Quitar la
construcción de `contacto` (:419). Si `crearTrabajo`/`subirListas` en el
contrato aún exigen `contacto`, hacerlo opcional en ese lado (mínimo cambio de
firma) — pero preferir no tocar el contrato si ya lo acepta ausente.

**29.5 — Typecheck + build**

```bash
cd apps/web && npm run typecheck && npm run build
```

Ver salida limpia.

**29.6 — Verificación e2e manual (documentar, no automatizar)**

Con el backend arriba (`make reanudar`): abrir `/empezar`, crear cuenta en el
paso 1, subir una lista, y confirmar en el panel de cola que el trabajo queda
atado al `usuario_id` de esa cuenta (no a un contacto anónimo). Registrar el
resultado en el PR.

**29.7 — Commit**

```bash
git add apps/web/src/app/empezar/
git commit -m "web: /empezar arranca por la cuenta (paso 1) + Ya tengo cuenta

Contraseña en el paso 1 — cuentas reales desde el minuto uno (spec). Correo +
celular + clave crean la cuenta contra /empezar/api/cuenta; interruptor a
inicio de sesión. El kit ya no manda contacto: viaja autenticado por cookie y
la tubería resuelve el usuario_id de la sesión.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```


---

## Fase 2 — Admin: acudientes por colegio (Tasks 30–33)

El back-office gana una vista de los acudientes de un colegio con el estado de
su trabajo (encolado / procesando / espera_revision / publicado / fallido), y
se corrige la etiqueta Dolor-1 de la pantalla de onboarding. La lista de
acudientes sale de `trabajo_pipeline` (que YA lleva `usuario_id`, el
identificador del acudiente — nunca su correo ni el nombre de un menor).

**Precondición:** Tasks 26–29 en verde. Los trabajos ya viajan con el
`usuario_id` de la sesión, así que agrupar por acudiente tiene sentido.

**Alcance de privacidad (Ley 1581 / Anexo M).** El panel muestra
`usuario_id` + estado + fechas, y —si el revisor lo pide— el correo del
acudiente resuelto contra Identidad (dato PERSONAL del titular, permitido). Los
apodos de los hijos NO se muestran aquí: son MENOR y el panel de colegio no los
necesita. `estudiante:leer:apodo` (MENOR) queda fuera de esta superficie.

---

### Task 30 — Backend: acudientes de un colegio con estado de trabajo

**Contexto.** `TrabajoPipeline` (`servicios/inteligencia/tukit_inteligencia/modelos/trabajo.py:50`)
tiene `usuario_id` (nullable), `estado`, `creado_en`, `actualizado_en`, y los
`hijos` en JSON (cada hijo trae `colegio_id`/`grado`). No hay columna
`colegio_id` en el trabajo — el colegio vive dentro de `hijos`. El endpoint
filtra los trabajos cuyo JSON `hijos` referencia el `colegio_id` pedido y los
agrupa por `usuario_id`, quedándose con el trabajo más reciente por acudiente
(el estado "vivo").

Este endpoint es de **inteligencia** (dueña de `trabajo_pipeline`), superficie
admin: `GET /v1/admin/colegios/{colegio_id}/acudientes`. Es RBAC-cerrado
(ADR-0013): solo personal con ámbito sobre ese colegio. El guardian de esquema
de inteligencia debe incluir la ruta nueva.

**30.1 — Test RED: dos acudientes del mismo colegio, un estado cada uno**

En `servicios/inteligencia/tests/test_admin_acudientes.py` (nuevo), con el
`cliente` de pruebas (SQLite StaticPool) sembrar dos `TrabajoPipeline` con
`usuario_id` distintos e `hijos` apuntando al mismo `colegio_id`, en estados
`espera_revision` y `publicado`. Pedir el endpoint y afirmar:

```python
async def test_acudientes_de_colegio_agrupa_por_usuario_con_ultimo_estado(cliente, ...):
    # sembrar trabajo A (usuario u1, colegio C, publicado, más viejo)
    # sembrar trabajo A' (usuario u1, colegio C, procesando, más nuevo)
    # sembrar trabajo B (usuario u2, colegio C, espera_revision)
    r = await cliente.get(f"/v1/admin/colegios/{C}/acudientes")
    assert r.status_code == 200
    filas = r.json()["acudientes"]
    assert len(filas) == 2                       # agrupado por usuario
    por_id = {f["usuario_id"]: f for f in filas}
    assert por_id[u1]["estado"] == "procesando"  # el más reciente, no el publicado viejo
    assert por_id[u2]["estado"] == "espera_revision"
```

Correr y ver **FAIL** (404, ruta inexistente).

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_admin_acudientes.py -x
```

**30.2 — Impl: consulta en el repo + ruta en el router admin**

La agrupación "último trabajo por usuario" es negocio ligero; el filtro por
colegio dentro del JSON `hijos` es lo delicado en SQL. Enfoque lazy: traer los
trabajos del colegio ordenados por `usuario_id, actualizado_en DESC` y quedarse
en Python con el primero de cada `usuario_id` (el conjunto por colegio es
pequeño — decenas, no millones).

Filtrado por colegio: en Postgres `hijos` es JSON; el modo portable (corre
también en el SQLite de pruebas) es un `LIKE` sobre el texto del JSON acotando
por el `colegio_id`, o —más honesto— cargar los trabajos recientes y filtrar en
Python por `any(h["colegio_id"] == colegio_id for h in trabajo.hijos)`. Dado el
volumen, filtrar en Python:

```python
# repositorios / consulta del servicio de inteligencia
async def trabajos_recientes(self) -> list[Fila]:
    q = select(TrabajoPipeline).order_by(TrabajoPipeline.usuario_id, TrabajoPipeline.actualizado_en.desc())
    return (await self._conn.execute(q)).all()
```

```python
# router admin de inteligencia
@router.get("/v1/admin/colegios/{colegio_id}/acudientes")
async def acudientes_de_colegio(request: Request, colegio_id: str) -> dict:
    async with request.app.state.motor.sesion() as db:
        filas = await Repo(await db.connection()).trabajos_recientes()
    del_colegio = [
        f for f in filas if f.usuario_id and any(h.get("colegio_id") == colegio_id for h in f.hijos)
    ]
    ultimos: dict[str, Fila] = {}
    for f in del_colegio:  # ya vienen ordenados por usuario, más reciente primero
        ultimos.setdefault(str(f.usuario_id), f)
    acudientes = [
        {
            "usuario_id": uid,
            "estado": f.estado,
            "actualizado_en": _iso(f.actualizado_en),
            "trabajo_id": str(f.id),
        }
        for uid, f in ultimos.items()
    ]
    return {"acudientes": acudientes}
```

`ponytail:` filtro por colegio en Python sobre trabajos recientes — un colegio
tiene decenas de acudientes, no hace falta índice sobre el JSON. Subir a JSON
containment (`hijos @> …`) si un colegio pasa de miles de trabajos.

**30.3 — Test GREEN**

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia/tests/test_admin_acudientes.py -x
```

Ver **PASS**.

**30.4 — Guardian de esquema**

Añadir `/v1/admin/colegios/{colegio_id}/acudientes` al set del test de esquema
publicado de inteligencia (el equivalente al guardian de identidad). Correr la
suite de inteligencia completa:

```bash
uv run --package tukit-inteligencia pytest servicios/inteligencia -x
```

Ver **PASS**.

**30.5 — Commit**

```bash
git add servicios/inteligencia/
git commit -m "inteligencia: GET /v1/admin/colegios/{id}/acudientes

Los acudientes de un colegio con el estado de su trabajo más reciente,
agrupado por usuario_id. Sin correo ni apodos de menores en esta superficie
(Ley 1581); solo usuario_id + estado + fecha.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 31 — Contrato: `acudientesDeColegio` + `AcudienteResumen`

**Contexto.** `origen.ts` ya tiene la familia de trabajos/colegios (`colegios()`
:148, `trabajoAdmin` :200). Añadir un método de lectura admin y su tipo. El
paquete tiene runner (`node --test`).

**31.1 — Test RED: el doble cumple `acudientesDeColegio`**

En `libs/ts/tukit-contrato/test/acudientes.test.ts`, un doble de `OrigenDatos`
que devuelve dos `AcudienteResumen` y una aserción de forma
(`usuario_id`/`estado`/`actualizado_en`/`trabajo_id`). Correr → **FAIL** (tipo y
método no existen).

**31.2 — Impl: tipo + método + impl HTTP**

En `contrato.ts` (donde viven los demás tipos) o el archivo de tipos que use el
contrato:

```ts
export interface AcudienteResumen {
  usuario_id: string;
  estado: EstadoTrabajo;      // ya exportado por el contrato
  actualizado_en: string;
  trabajo_id: string;
}
```

En `origen.ts` (`OrigenDatos`, junto a `trabajoAdmin`):

```ts
acudientesDeColegio(colegioId: string): Promise<AcudienteResumen[]>;
```

En `cliente-http.ts`:

```ts
acudientesDeColegio(colegioId: string): Promise<AcudienteResumen[]> {
  return this.pedir<{ acudientes: AcudienteResumen[] }>(
    `/v1/admin/colegios/${encodeURIComponent(colegioId)}/acudientes`,
  ).then((r) => r.acudientes);
}
```

**31.3 — Test GREEN + build**

```bash
cd libs/ts/tukit-contrato && npm test && npm run build
```

Ver **PASS** y build limpio.

**31.4 — Commit**

```bash
git add libs/ts/tukit-contrato/
git commit -m "contrato: acudientesDeColegio + AcudienteResumen

Lectura admin de los acudientes de un colegio con el estado de su trabajo.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 32 — Fix Dolor-1: la etiqueta de la pantalla de onboarding

**Contexto.** `apps/admin/src/app/onboarding/[version_id]/page.tsx:100` pinta el
título de la revisión. El spec marca un ajuste de etiqueta Dolor-1 aquí (una
afirmación imprecisa en la copy del encabezado / bajada :102–107). El cambio es
puramente de texto — se verifica por `tsc` y lectura.

**32.1 — Corregir la copy**

Leer :96–109 y ajustar la etiqueta/bajada a la redacción correcta del spec
(sección Dolor-1). Es un cambio de una o dos líneas de texto en el JSX; no toca
lógica ni tipos.

**32.2 — Typecheck**

```bash
cd apps/admin && npm run typecheck
```

Ver salida limpia.

**32.3 — Commit**

```bash
git add apps/admin/src/app/onboarding/
git commit -m "admin: corregir etiqueta Dolor-1 en la revisión de onboarding

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 33 — Panel de acudientes en `/colegios/{colegio}`

**Contexto.** `apps/admin/src/app/colegios/[colegio]/page.tsx` es un Server
Component que ya trae `colegio()` y deriva `grados` de `colegios()`. Tiene dos
`<section className={styles.tarjeta}>`: "Ficha del colegio" y "Grados
verificados". Añadir una tercera: "Acudientes", que llama a
`acudientesDeColegio(colegioId)` y lista `usuario_id` + estado + fecha. Sin
runner en `apps/admin`: se verifica por `tsc` + e2e manual.

**33.1 — Traer los acudientes en el Server Component**

Junto a la derivación de `grados` (:39–42):

```ts
const acudientes = await origenDeDatos().acudientesDeColegio(colegioId);
```

**33.2 — Sección "Acudientes" con estado**

Tras la sección "Grados verificados" (:78–97), añadir:

```tsx
<section className={styles.tarjeta}>
  <h2 className={styles.subtitulo}>Acudientes</h2>
  <p className={styles.bajada}>
    Quiénes han pedido kits para este colegio y en qué va su trabajo. Sin datos
    de menores: solo el identificador del acudiente y el estado.
  </p>
  {acudientes.length === 0 ? (
    <p className={styles.sinGrados}>Ningún acudiente todavía.</p>
  ) : (
    <ul className={styles.listaAcudientes}>
      {acudientes.map((a) => (
        <li key={a.usuario_id}>
          <code>{a.usuario_id.slice(0, 8)}</code>
          <span className={styles[`estado_${a.estado}`] ?? styles.estado}>{a.estado}</span>
          <time dateTime={a.actualizado_en}>{a.actualizado_en.slice(0, 10)}</time>
        </li>
      ))}
    </ul>
  )}
</section>
```

Reutilizar clases de `Colegios.module.css` que ya existan (`.tarjeta`,
`.subtitulo`, `.bajada`, `.sinGrados`); añadir `.listaAcudientes` y un chip de
estado solo si el CSS no tiene ya algo equivalente (mirar antes — el módulo ya
pinta insignias `insigniaAliado`/`insigniaBorrador`, reutilizables como chip).

**33.3 — Typecheck + build**

```bash
cd apps/admin && npm run typecheck && npm run build
```

Ver salida limpia.

**33.4 — Verificación e2e manual (documentar)**

Con backend arriba y al menos un trabajo publicado para un colegio piloto,
abrir `/colegios/{colegio}` en admin y confirmar que el acudiente aparece con su
estado. Registrar en el PR.

**33.5 — Commit**

```bash
git add apps/admin/src/app/colegios/
git commit -m "admin: panel de acudientes por colegio con estado de trabajo

Tercera sección en /colegios/{id}: quién pidió kits y en qué va su trabajo.
Solo usuario_id + estado + fecha (Ley 1581, sin datos de menores).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Verificación e2e (29.6 + 33.4) — ejecutada 2026-09-27

Backend vivo (`make reanudar` + `make bd-migrar`, migración `a1b2c3d4e5f6`
aplicada), contra el gateway `:8010`:

- **29.6 — ownership por sesión.** `POST /v1/cuenta` crea la cuenta (correo +
  nombre del adulto + celular + clave) y devuelve `{sesion, token}`.
  `GET /v1/sesiones/actual` con ese Bearer resuelve el mismo `usuario_id`.
  `POST /v1/trabajos` con el Bearer y **sin** `contacto` crea el trabajo, y
  `GET /v1/admin/trabajos/{id}` reporta `contacto_id == usuario_id` de la
  cuenta. El kit no queda huérfano: la propiedad viaja por la cookie→Bearer.
- **33.4 — panel de acudientes.** `GET /v1/admin/colegios/{id}/acudientes`
  lista al acudiente agrupado por `usuario_id` con `estado: procesando`, y
  expone SOLO `usuario_id / estado / actualizado_en / trabajo_id` — ni correo
  ni datos de menores (Ley 1581 confirmada en vivo).

Suites al cierre: identidad 128, inteligencia 162, contrato 4 — todo verde.
