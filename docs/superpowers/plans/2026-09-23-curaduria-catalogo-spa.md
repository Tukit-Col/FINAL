# Curaduría del catálogo en la SPA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portar la curaduría proactiva del viejo `tukit_catalogo.admin` (CLI/`http.server`) a la SPA `/catalogo` de `apps/admin`: cola de propuestas, alta de útiles (búsqueda en vivo VTEX/Shopify), alta de libros (manual + link Buscalibre), y editor de productos que edita **todos** los atributos sin perder su tipo.

**Architecture:** Enfoque A (aprobado en el spec). Endpoints nuevos en `catalogo/admin_http.py` bajo `/v1/admin/catalogo/*`, reusando `_encolar`/`resolver`/`tiendas.buscar` sin reimplementar dominio; gateway rutea `/v1/admin/catalogo` → catálogo; `api.py` sigue read-only salvo endurecer una guarda; contrato TS gana tipos + métodos + simulado; la SPA gana editor tipado, cola y formularios de alta con Route Handlers que ocultan el backend.

**Tech Stack:** Python 3.12 (FastAPI, SQLAlchemy async, pytest + httpx.ASGITransport + aiosqlite), TypeScript (contrato `libs/ts/tukit-contrato`), Next.js 16 App Router (`apps/admin`, Server Components + Route Handlers).

**Spec:** `docs/superpowers/specs/2026-09-23-curaduria-catalogo-spa-design.md`

## Global Constraints

- Catálogo solo puede importar `.` y `tukit_comun` (fronteras ADR 0008/0012). `make fronteras` debe seguir verde.
- `api.py` es **solo lectura** por contrato: toda escritura nueva va en `admin_http.py`. La única edición permitida en `api.py` es endurecer `_validar_edicion` (no agrega escritura).
- Encolar y aprobar son **dos pasos separados** en la SPA (a diferencia de `admin.agregar_util`, que los encadena): la propuesta cae en la cola visible y una persona decide el nivel al aprobar.
- Precio: entero en **pesos** en la superficie HTTP/SPA; la base guarda **centavos** (`* 100`). Validar precio > 0 tres veces: form, Route Handler, origen (patrón `AltaProducto.tsx`).
- El link a Buscalibre (`https://www.buscalibre.com.co/libros/search?q=<isbn|titulo>`, `target="_blank"`) es requisito fijo: no se elimina ni se reemplaza por búsqueda automática.
- Rechazar NO estrena ruta: la SPA reusa `POST /v1/admin/propuestas/{id}/rechazar` (ya existe en `admin_http.py`, prefijo `/v1/admin/propuestas` ya ruteado a catálogo).
- Atributos: valores **escalares** (str/int/float/bool/null). Ni listas ni dicts anidados. El tipo lo fija el cliente (`serializarAtributos`); el backend solo lo endurece.
- Next.js 16: leer `apps/admin/node_modules/next/dist/docs/` antes de escribir código Next.js (breaking changes vs training data).
- Mensajes de error del backend: `ErrorDominio(codigo, mensaje, estado=..., campo=...)` nombrando el campo ofensor. La SPA muestra el mensaje del backend tal cual.

## Review Focus

1. **Alta de útil con SKU que ya no está en la tienda** → la SPA re-busca por SKU al encolar (patrón `admin._util`); si no aparece, `ErrorDominio("candidato_no_disponible", …, 422)`, no un 500. (Task A3)
2. **Encolar un útil/libro sobre un concepto inexistente** → `concepto_no_existe` (422), no un IntegrityError 500. (Task A3/A4)
3. **PATCH atributos con un valor lista/objeto** (`{"materias": ["a","b"]}`) → `atributos_invalido` nombrando la clave, no persistir basura. (Task A5)
4. **Editor sobre un producto cuyo concepto declara claves que el producto no trae** (el caso del screenshot: cuaderno con solo `materias`, el concepto declara `hojas`/`rayado`) → filas vacías pre-pobladas; guardar una vacía NO afirma la clave (no se guarda). (Task D2)
5. **`serializarAtributos` con `"80"`, `"true"`, `"3.5"`, `"cuadriculado"`, `""`** → `80` int, `true` bool, `3.5` float, `"cuadriculado"` str, y `""` se descarta (clave no afirmada). (Task C5)

---

## Track A — Backend (servicio catálogo)

Archivos: `servicios/catalogo/tukit_catalogo/{admin.py, descubrir.py, admin_http.py, api.py}`, `servicios/catalogo/tests/test_api_admin.py` (+ nuevo `test_curaduria_http.py`).

### Task A1: Extraer los builders de propuesta de `admin.py`

**Files:**
- Modify: `servicios/catalogo/tukit_catalogo/admin.py` (`agregar_util` L557, `agregar_libro` L644)
- Test: `servicios/catalogo/tests/test_curaduria_builders.py` (crear)

**Interfaces:**
- Produces: en `admin.py`, dos funciones puras (sin I/O, sin motor):
  - `construir_propuesta_util(concepto_id: uuid.UUID, nombre_concepto: str, slug: str, tienda_id: uuid.UUID, oferta: tiendas.Oferta, nivel: str) -> dict[str, Any]`
  - `construir_propuesta_libro(concepto_id: uuid.UUID, nombre_concepto: str, slug: str, tienda_id: uuid.UUID, isbn: str, titulo: str, precio_cop: int, nivel: str) -> dict[str, Any]`
  - Cada una devuelve el dict que hoy se pasa inline a `_encolar` (puntaje 0.6 útil / 0.9 libro, `origen="manual"`, `version_lista_id=None`, `id=_uuid_estable(...)`). `agregar_util`/`agregar_libro` quedan reescritas para llamar a estos builders + `_encolar` + `resolver` (comportamiento CLI idéntico).

- [ ] **Step 1: Write the failing test**

```python
# test_curaduria_builders.py
import uuid
from tukit_catalogo import tiendas
from tukit_catalogo.admin import construir_propuesta_util, construir_propuesta_libro

def test_util_conserva_precio_en_centavos_y_puntaje():
    cid = uuid.uuid4(); tid = uuid.uuid4()
    o = tiendas.Oferta(tienda="exito", nombre="Cuaderno 100h", precio_cop=5000,
                       disponible=True, imagen_url=None, url="http://x", sku="SKU1",
                       ean=None, marca="Norma", especificaciones={})
    d = construir_propuesta_util(cid, "Cuaderno", "exito", tid, o, "confiable")
    assert d["precio_centavos"] == 500000 and d["puntaje"] == 0.6
    assert d["origen"] == "manual" and d["version_lista_id"] is None
    assert d["concepto_id"] == cid and d["referencia_externa"] == "SKU1"

def test_libro_usa_isbn_como_referencia_y_puntaje_0_9():
    cid = uuid.uuid4(); tid = uuid.uuid4()
    d = construir_propuesta_libro(cid, "Libro", "panamericana", tid,
                                  "9781234567897", "El Principito", 30000, "confiable")
    assert d["referencia_externa"] == "9781234567897" and d["puntaje"] == 0.9
    assert d["especificaciones"] == {"isbn": "9781234567897"} and d["precio_centavos"] == 3000000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd servicios/catalogo && python -m pytest tests/test_curaduria_builders.py -v`
Expected: FAIL (`ImportError: cannot import name 'construir_propuesta_util'`)

- [ ] **Step 3: Extract the builders**

Mover el dict inline de `agregar_util` a `construir_propuesta_util` y el de `agregar_libro` a `construir_propuesta_libro`, tomando `concepto_id`/`tienda_id` ya resueltos y `nombre_concepto` como parámetros. Reescribir `agregar_util`/`agregar_libro` para: resolver tienda+concepto (como hoy), llamar al builder, `_encolar([dict])`, `resolver(str(pid)[:8], aprobar=True, ...)`. `_uuid_estable("util", slug, oferta.sku)` / `_uuid_estable("propuesta", slug, isbn)` va DENTRO del builder (necesita `id`).

- [ ] **Step 4: Run test + regresión de admin**

Run: `cd servicios/catalogo && python -m pytest tests/test_curaduria_builders.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add servicios/catalogo/tukit_catalogo/admin.py servicios/catalogo/tests/test_curaduria_builders.py
git commit -m "refactor(catalogo): extraer builders de propuesta reutilizables por HTTP"
```

### Task A2: `GET /v1/admin/catalogo/propuestas` (la cola, en JSON)

**Files:**
- Modify: `servicios/catalogo/tukit_catalogo/admin_http.py` (añadir bajo `router`, prefijo `/v1/admin`; las rutas nuevas usan el sub-path `/catalogo/...`)
- Test: `servicios/catalogo/tests/test_curaduria_http.py` (crear; fixture idéntica a `test_api_admin.py`: `create_async_engine("sqlite+aiosqlite://", StaticPool)`, `Base.metadata.create_all`, `app.state.motor = MotorServicio(...)`, `httpx.AsyncClient(ASGITransport(app=app))`)

**Interfaces:**
- Produces: `GET /v1/admin/catalogo/propuestas?concepto=<codigo>` → `{"total": int, "propuestas": [{id, id_corto, texto_origen, nombre, marca, imagen_url, precio (pesos|null), nivel_sugerido, puntaje, concepto: {codigo, nombre} | {sugerido}, origen}]}` para `estado=='pendiente'`, orden `propuesta_en`. Reusa las tablas `PROPUESTA`/`CONCEPTO` ya cacheadas en el módulo y el patrón `async with _motor().engine.begin()`.
- Consumes: `_motor()` (L59), `PROPUESTA` (L46), `CONCEPTO` (L42).

- [ ] **Step 1: Write the failing test**

```python
# test_curaduria_http.py (con la fixture `cliente` sembrando 1 propuesta pendiente)
async def test_lista_propuestas_pendientes(cliente):
    r = await cliente.get("/v1/admin/catalogo/propuestas")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] >= 1
    p = cuerpo["propuestas"][0]
    assert set(p) >= {"id", "id_corto", "nombre", "precio", "nivel_sugerido", "concepto"}
    assert len(p["id_corto"]) == 8
```

- [ ] **Step 2: Run to verify it fails** — Run: `python -m pytest tests/test_curaduria_http.py::test_lista_propuestas_pendientes -v` → FAIL (404).

- [ ] **Step 3: Implement** el endpoint (select de la misma forma que `ver_revision` L247-282 pero sin filtrar por `version_lista_id`, con `estado=='pendiente'`; `id_corto = str(p.id)[:8]`; precio `None if precio_centavos is None else int(precio_centavos)//100`). Filtro opcional por `concepto` (código → join CONCEPTO).

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit** `feat(catalogo): GET /v1/admin/catalogo/propuestas expone la cola en JSON`.

### Task A3: `GET .../tiendas/{slug}/buscar` + `POST .../propuestas/util`

**Files:** Modify `admin_http.py`; Test `test_curaduria_http.py`.

**Interfaces:**
- Produces:
  - `GET /v1/admin/catalogo/tiendas/{slug}/buscar?consulta=&cuantos=` → `{"candidatos": [{slug, sku, nombre, precio (pesos), marca, ean, url, imagen_url, disponible, especificaciones}]}`. Envuelve `tiendas.buscar(slug, consulta, cuantos)`. `slug` fuera de `{exito, panamericana, grancentral}` → `ErrorDominio("tienda_desconocida", …, 422)`. NO escribe.
  - `POST /v1/admin/catalogo/propuestas/util` cuerpo `{concepto, slug, sku, consulta, nivel}` → re-busca por `(slug, sku)` como `admin._util`; si no está → `ErrorDominio("candidato_no_disponible", …, 422)`; resuelve `tienda_id`/`concepto_id` (usar `_concepto_id` L104 → `concepto_no_existe`); `admin.construir_propuesta_util(...)`; `_encolar([dict])`. Devuelve `{id, id_corto, estado: "pendiente"}`. **No aprueba.**
- Consumes: `tiendas.buscar`, `admin.buscar_candidatos` (L537), `admin.construir_propuesta_util` (Task A1), `descubrir._encolar`.

- [ ] **Step 1: Failing test** (mockear `tiendas.buscar`/`buscar_candidatos` con `monkeypatch` para no salir a la red):

```python
async def test_encolar_util_cae_en_la_cola(cliente, monkeypatch):
    from tukit_catalogo import admin, tiendas
    o = tiendas.Oferta(tienda="exito", nombre="Cuaderno", precio_cop=5000, disponible=True,
                       imagen_url=None, url="http://x", sku="SKU9", ean=None, marca="Norma",
                       especificaciones={})
    monkeypatch.setattr(admin, "buscar_candidatos", lambda c: [("exito", o)])
    r = await cliente.post("/v1/admin/catalogo/propuestas/util",
        json={"concepto": cliente.ids["concepto_c001"], "slug": "exito",
              "sku": "SKU9", "consulta": "cuaderno", "nivel": "confiable"})
    assert r.status_code == 201 and r.json()["estado"] == "pendiente"
    cola = (await cliente.get("/v1/admin/catalogo/propuestas")).json()
    assert any(p["nombre"] == "Cuaderno" for p in cola["propuestas"])

async def test_encolar_util_concepto_inexistente_es_422(cliente, monkeypatch):
    from tukit_catalogo import admin, tiendas
    o = tiendas.Oferta(tienda="exito", nombre="X", precio_cop=1, disponible=True, imagen_url=None,
                       url="", sku="S", ean=None, marca=None, especificaciones={})
    monkeypatch.setattr(admin, "buscar_candidatos", lambda c: [("exito", o)])
    r = await cliente.post("/v1/admin/catalogo/propuestas/util",
        json={"concepto": "NOPE", "slug": "exito", "sku": "S", "consulta": "x", "nivel": "confiable"})
    assert r.status_code == 422 and r.json()["error"] == "concepto_no_existe"
```

- [ ] **Step 2: Run → FAIL** (404).
- [ ] **Step 3: Implement** ambos endpoints. Para `tienda_id`, seleccionar de la tabla `tienda` por nombre/slug dentro de la conexión (mismo patrón que `admin._tienda_por_slug` L515, pero sobre `_motor()`). `buscar` es sync → llamar directo (o `await run_in_threadpool` si bloquea; `tiendas.buscar` es sync con caché en disco — envolver con `from starlette.concurrency import run_in_threadpool`).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(catalogo): buscar en tienda + encolar util a la cola de curaduria`.

### Task A4: `POST .../propuestas/libro` + `POST .../propuestas/{id}/aprobar`

**Files:** Modify `admin_http.py`; Test `test_curaduria_http.py`.

**Interfaces:**
- Produces:
  - `POST /v1/admin/catalogo/propuestas/libro` cuerpo `{concepto, isbn, titulo, precio, slug, nivel}` → valida ISBN con `cargador.isbn13_valido`/`normalizar_isbn` (→ `isbn_invalido` 422); precio entero > 0 pesos (→ `precio_invalido` 422); `admin.construir_propuesta_libro(...)`; `_encolar`. Devuelve `{id, id_corto, estado: "pendiente"}`. `slug` default `"panamericana"`.
  - `POST /v1/admin/catalogo/propuestas/{id}/aprobar` cuerpo `{nivel}` → `descubrir.resolver(str(id)[:8], aprobar=True, nivel=nivel, motivo=None)`; `resolver` devuelve 0 en éxito. Si != 0 → `ErrorDominio("no_se_pudo_aprobar", …, 409)`. Devuelve `{id, estado: "aprobada"}`. (Nace producto+oferta+precio dentro de `resolver`.)
- Consumes: `admin.construir_propuesta_libro`, `descubrir.resolver`, `descubrir._encolar`, `cargador.isbn13_valido`/`normalizar_isbn`.

- [ ] **Step 1: Failing test**

```python
async def test_encolar_libro_valida_isbn(cliente):
    r = await cliente.post("/v1/admin/catalogo/propuestas/libro",
        json={"concepto": cliente.ids["concepto_c001"], "isbn": "123", "titulo": "T",
              "precio": 30000, "slug": "panamericana", "nivel": "confiable"})
    assert r.status_code == 422 and r.json()["error"] == "isbn_invalido"

async def test_aprobar_propuesta_nace_producto(cliente):
    prop_id = cliente.ids["propuesta_pendiente"]  # sembrada con concepto en la fixture
    r = await cliente.post(f"/v1/admin/catalogo/propuestas/{prop_id}/aprobar",
        json={"nivel": "confiable"})
    assert r.status_code == 200 and r.json()["estado"] == "aprobada"
```

- [ ] **Step 2: Run → FAIL.**  (Nota: `resolver` abre su propio `crear_motor("catalogo")`, que en test apunta a la BD de entorno, no al SQLite inyectado. Si el test de `aprobar` no puede correr contra SQLite, mockear `descubrir.resolver` con `monkeypatch` devolviendo 0 y verificar que el endpoint traduce el código a la respuesta — la creación real de producto ya la cubre `descubrir` en sus propios tests. Documentar esta frontera en el test.)
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(catalogo): encolar libro por ISBN + aprobar propuesta desde la cola`.

### Task A5: Guarda `atributos_invalido` en `api.py`

**Files:**
- Modify: `servicios/catalogo/tukit_catalogo/api.py` (`_validar_edicion`)
- Test: `servicios/catalogo/tests/test_api_admin.py` (añadir)

**Interfaces:**
- Produces: en `_validar_edicion`, si `"atributos"` está en `cambios` y algún valor no es escalar (`str|int|float|bool|None`), `raise ErrorDominio("atributos_invalido", f"El atributo '{clave}' debe ser un valor simple.", estado=422, campo="atributos")`. `bool` es subclase de `int` en Python — aceptar ambos; rechazar `list`/`dict`.

- [ ] **Step 1: Failing test**

```python
async def test_patch_atributos_no_escalar_es_422(cliente):
    sku = cliente.ids["sku_p1"]
    r = await cliente.patch(f"/v1/catalogo/productos/{sku}",
        json={"atributos": {"materias": ["a", "b"]}})
    assert r.status_code == 422 and r.json()["error"] == "atributos_invalido"

async def test_patch_atributos_escalares_ok(cliente):
    sku = cliente.ids["sku_p1"]
    r = await cliente.patch(f"/v1/catalogo/productos/{sku}",
        json={"atributos": {"hojas": 80, "rayado": "cuadriculado", "deposito": True}})
    assert r.status_code == 200
```

- [ ] **Step 2: Run → FAIL** (hoy acepta la lista, 200).
- [ ] **Step 3: Implement** la guarda en `_validar_edicion`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(catalogo): PATCH rechaza atributos no escalares (atributos_invalido)`.

---

## Track B — Gateway

### Task B1: Rutear `/v1/admin/catalogo` → catálogo

**Files:**
- Modify: `servicios/gateway/tukit_gateway/api.py` (`RUTAS`)
- Modify: `servicios/gateway/tests/test_ruteo.py`

**Interfaces:**
- Produces: `RUTAS["/v1/admin/catalogo"] = "catalogo"`. Como `destino()` ordena por longitud desc, `/v1/admin/catalogo/...` gana sobre `/v1/admin` → inteligencia, y `/v1/admin/propuestas/{id}/rechazar` sigue yendo a catálogo por su propio prefijo.

- [ ] **Step 1: Failing test** — añadir a `TestElPrefijoMasLargoGana` (parametrizado):

```python
("/v1/admin/catalogo/propuestas", "catalogo"),
("/v1/admin/catalogo/tiendas/exito/buscar", "catalogo"),
("/v1/admin/propuestas/abc/rechazar", "catalogo"),
```

- [ ] **Step 2: Run → FAIL** (`/v1/admin/catalogo/...` cae en inteligencia).
- [ ] **Step 3: Implement** — añadir la entrada a `RUTAS`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(gateway): rutear /v1/admin/catalogo a catalogo`.

---

## Track C — Contrato (libs/ts/tukit-contrato)

### Task C1: Tipos nuevos

**Files:** Modify `libs/ts/tukit-contrato/src/contrato.ts` (o `catalogo.ts` si viven ahí los tipos de catálogo).

**Interfaces (Produces):**
```ts
export interface PropuestaCola {
  id: string; id_corto: string; texto_origen: string; nombre: string;
  marca: string | null; imagen_url: string | null; precio: number | null;
  nivel_sugerido: string | null; puntaje: number;
  concepto: { codigo: string; nombre: string } | { sugerido: string | null };
  origen: string;
}
export interface CandidatoTienda {
  slug: string; sku: string; nombre: string; precio: number;
  marca: string | null; ean: string | null; url: string;
  imagen_url: string | null; disponible: boolean;
  especificaciones: Record<string, string>;
}
export interface AltaUtil { concepto: string; slug: string; sku: string; consulta: string; nivel: string; }
export interface AltaLibro { concepto: string; isbn: string; titulo: string; precio: number; slug: string; nivel: string; }
export interface AprobarPropuesta { nivel: string; }
export interface RechazarPropuesta { motivo?: string; no_surtir?: boolean; }
export interface PropuestaEncolada { id: string; id_corto: string; estado: string; }
```

- [ ] Steps: no hay test unitario propio; se validan al compilar en C2-C5. Añadir tipos → `pnpm --filter @tukit/contrato build` (o `tsc --noEmit`) verde → Commit `feat(contrato): tipos de curaduria de catalogo`.

### Task C2: Método en la interfaz `origen.ts`

**Files:** Modify `libs/ts/tukit-contrato/src/origen.ts` (bloque §Catalogo).

**Interfaces (Produces):**
```ts
  colaPropuestas(concepto?: string): Promise<PropuestaCola[]>;
  buscarEnTienda(slug: string, consulta: string, cuantos?: number): Promise<CandidatoTienda[]>;
  altaUtil(cuerpo: AltaUtil): Promise<PropuestaEncolada>;
  altaLibro(cuerpo: AltaLibro): Promise<PropuestaEncolada>;
  aprobarPropuesta(id: string, cuerpo: AprobarPropuesta): Promise<{ id: string; estado: string }>;
  rechazarPropuesta(id: string, cuerpo: RechazarPropuesta): Promise<{ id: string; estado: string }>;
```
- [ ] Add to interface → build FAIL en `cliente-http.ts` y `origen-simulado.ts` (no implementan) → esto guía C3/C4. Commit junto con C3+C4.

### Task C3: Impl API en `cliente-http.ts`

**Files:** Modify `libs/ts/tukit-contrato/src/cliente-http.ts`.

**Interfaces:** implementar los 6 métodos contra el gateway:
- `colaPropuestas` → `GET /v1/admin/catalogo/propuestas` (+ `?concepto=`), devuelve `cuerpo.propuestas`.
- `buscarEnTienda` → `GET /v1/admin/catalogo/tiendas/{slug}/buscar?consulta=&cuantos=`, devuelve `cuerpo.candidatos`.
- `altaUtil` → `POST /v1/admin/catalogo/propuestas/util`.
- `altaLibro` → `POST /v1/admin/catalogo/propuestas/libro`.
- `aprobarPropuesta` → `POST /v1/admin/catalogo/propuestas/{id}/aprobar`.
- `rechazarPropuesta` → `POST /v1/admin/propuestas/{id}/rechazar` (ruta existente).

- [ ] Reusar el helper `pedir`/`fetch` ya presente; mapear errores a `ErrorTukit` como el resto. Build → PASS.

### Task C4: Impl simulado en `origen-simulado.ts`

**Files:** Modify `libs/ts/tukit-contrato/src/simulado/origen-simulado.ts`.

**Interfaces:** implementar los 6 métodos leyendo del corpus para que la SPA en modo `simulado` muestre cola con datos reales. Mínimo viable: `colaPropuestas` devuelve un arreglo derivado de N productos del corpus como "pendientes"; `buscarEnTienda` devuelve candidatos del corpus filtrados por `consulta`; `altaUtil`/`altaLibro` empujan a un arreglo en memoria y lo devuelven en `colaPropuestas`; `aprobar`/`rechazar` lo quitan del arreglo. No debe romper los tests existentes del simulado.

- [ ] Build + tests del contrato → PASS. Commit `feat(contrato): metodos de curaduria en cliente-http y simulado`.

### Task C5: `serializarAtributos` + `inferirTipoAtributo`

**Files:**
- Create/Modify: `libs/ts/tukit-contrato/src/catalogo.ts` (o un `atributos.ts`)
- Test: `libs/ts/tukit-contrato/test/atributos.test.ts` (mismo runner que usa el paquete)

**Interfaces (Produces):**
```ts
export function inferirTipoAtributo(texto: string): string | number | boolean;
// pares: [{clave, valor}]; descarta clave vacía y valor "" (clave no afirmada)
export function serializarAtributos(pares: {clave: string; valor: string}[]): Record<string, string | number | boolean>;
```

- [ ] **Step 1: Failing test**
```ts
test("inferir tipos", () => {
  expect(inferirTipoAtributo("80")).toBe(80);
  expect(inferirTipoAtributo("3.5")).toBe(3.5);
  expect(inferirTipoAtributo("true")).toBe(true);
  expect(inferirTipoAtributo("cuadriculado")).toBe("cuadriculado");
});
test("serializar descarta vacíos", () => {
  const r = serializarAtributos([{clave:"hojas",valor:"80"},{clave:"rayado",valor:""},{clave:"",valor:"x"}]);
  expect(r).toEqual({ hojas: 80 });
});
```
- [ ] **Step 2: Run → FAIL.** — [ ] **Step 3: Implement** (regex enteros/decimales; `"true"/"false"` → bool; resto texto; number sólo si el string entero round-trips, p.ej. `String(n) === texto` para no comerse ceros a la izquierda de un código). — [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** `feat(contrato): serializarAtributos tipa los atributos del editor`.

---

## Track D — SPA (apps/admin) — depende de Track C

Leer `apps/admin/node_modules/next/dist/docs/` antes de tocar código Next.js.

### Task D1: Route Handlers

**Files (Create):**
- `apps/admin/src/app/api/catalogo/propuestas/route.ts` (GET cola)
- `apps/admin/src/app/api/catalogo/propuestas/util/route.ts` (POST)
- `apps/admin/src/app/api/catalogo/propuestas/libro/route.ts` (POST)
- `apps/admin/src/app/api/catalogo/propuestas/[id]/aprobar/route.ts` (POST)
- `apps/admin/src/app/api/catalogo/propuestas/[id]/rechazar/route.ts` (POST)
- `apps/admin/src/app/api/catalogo/tiendas/[slug]/buscar/route.ts` (GET)
- Modify: `apps/admin/src/lib/api-catalogo.ts` (fns cliente-navegador: `colaPropuestas`, `buscarEnTienda`, `altaUtil`, `altaLibro`, `aprobarPropuesta`, `rechazarPropuesta`)

**Interfaces:** patrón exacto de `apps/admin/src/app/api/catalogo/productos/[sku]/reclasificar/route.ts`: `export const dynamic = "force-dynamic"`, `cuerpoJson`, `respuestaDeError`, `origenDeDatos().<metodo>()`. Precio validado > 0 también aquí.

- [ ] Cada handler: crear → `next build` (o `tsc --noEmit`) verde → smoke con `curl` contra la SPA en dev apuntando a un backend/simulado. Commit `feat(admin): route handlers de curaduria de catalogo`.

### Task D2: `EditorProducto` — atributos tipados + pre-población por concepto

**Files:**
- Modify: `apps/admin/src/components/EditorProducto.tsx` (L~125-129, el mapeo de atributos)
- Modify: `apps/admin/src/components/GestorCatalogo.tsx` y `apps/admin/src/app/catalogo/page.tsx` (pasar el concepto COMPLETO con `atributos_discriminantes`/`atributos_descriptivos`, no solo `{codigo, nombre}`)
- Test: si el paquete tiene runner de componentes, un test; si no, un test de la función pura de mapeo extraída.

**Interfaces:**
- Consumes: `serializarAtributos` (Task C5), `ConceptoCatalogo.atributos_discriminantes`/`atributos_descriptivos` (ya en el contrato).
- Comportamiento:
  1. Al guardar, pasar los pares por `serializarAtributos` en vez de `mapaAtributos[k] = valor` (arregla el bug de string).
  2. Pre-poblar TODAS las claves declaradas por el concepto del producto (discriminantes + descriptivos) como filas; las que el producto ya trae, con su valor; las que no, vacías. Fila vacía = clave no afirmada (no se guarda) — consistente con `serializarAtributos` que descarta `""`.
  3. Dos grupos etiquetados: "filtra la búsqueda" (discriminantes) / "solo informativo" (descriptivos); ocultar encabezado de grupo vacío.
  4. Botón "+ Atributo" para claves libres no declaradas (se tipa por inferencia).

- [ ] **Step 1: Failing test** — el caso del screenshot: producto C001 con solo `{materias: 3}`, concepto declara `["materias","hojas","rayado"]` → el editor monta filas `materias=3`, `hojas=""`, `rayado=""`; al guardar sólo `hojas=80`, el body enviado es `{materias: 3, hojas: 80}` (rayado vacío no se afirma) y tipado.
- [ ] **Step 2: Run → FAIL.** — [ ] **Step 3: Implement.** — [ ] **Step 4: Run → PASS.** — [ ] **Step 5: Commit** `fix(admin): editar todos los atributos del concepto, tipados`.

### Task D3: `ColaCuraduria`

**Files (Create):** `apps/admin/src/components/ColaCuraduria.tsx`; montar en `apps/admin/src/app/catalogo/page.tsx` (sección/pestaña).

**Interfaces:** `'use client'` leaf; llama `api-catalogo.colaPropuestas()`; cada fila con Aprobar (selector de nivel → `aprobarPropuesta`) / Rechazar (motivo + checkbox `no_surtir` → `rechazarPropuesta`). Muestra el mensaje de error del backend tal cual.

- [ ] Crear + montar → `next build` verde → smoke visual. Commit `feat(admin): cola de curaduria en /catalogo`.

### Task D4: `AltaUtil` (búsqueda en tienda) + `AltaLibro` (manual + Buscalibre)

**Files (Create):** `apps/admin/src/components/AltaUtil.tsx`, `apps/admin/src/components/AltaLibro.tsx`; montar en `/catalogo`.

**Interfaces:**
- `AltaUtil`: selector de tienda (Éxito / Panamericana / Gran Central) + caja de búsqueda → `buscarEnTienda(slug, consulta)` → lista de candidatos (foto, nombre, precio, marca) → elegir uno + concepto + nivel → `altaUtil({concepto, slug, sku, consulta, nivel})` → entra a la cola.
- `AltaLibro`: form manual (ISBN, título, precio pesos>0, tienda, concepto, nivel) → `altaLibro(...)`. **Link fijo** "Buscar en Buscalibre" → `https://www.buscalibre.com.co/libros/search?q=<encodeURIComponent(isbn||titulo)>` `target="_blank" rel="noopener"`. Precio validado en el form.

- [ ] Crear + montar → `next build` verde → smoke. Commit `feat(admin): alta de util (tiendas) y libro (manual + Buscalibre) en /catalogo`.

---

## Verificación final (todas las tracks)

- [ ] `cd servicios/catalogo && python -m pytest -q` verde
- [ ] `cd servicios/gateway && python -m pytest tests/test_ruteo.py -q` verde
- [ ] `make fronteras` verde (catálogo sigue importando solo `.` + `tukit_comun`)
- [ ] `make humo` verde
- [ ] Contrato: build + tests verde
- [ ] `apps/admin`: `next build` (o `tsc --noEmit` + lint) verde
- [ ] Revisión de rama por un revisor fresco
