# Revisión de arquitectura de Tukit

> Documento de **solo diagnóstico**. No cambia código de ningún servicio. Propone un
> patrón objetivo y un orden de migración para pagar la única deuda estructural real. El
> único cambio que sí sale en esta pasada —el middleware de correlation-ID— se implementa
> **aparte, en curso**, y aquí solo se describe (§7).
>
> Documentos que gobiernan y contra los que se contrasta esto: `arquitectura/manifiesto.toml`
> (fuente de verdad de las fronteras de datos, la leen las pruebas) y
> `arquitectura/CONTRATO_API.md` (fronteras de conversación). No existe un
> `arquitectura/ARQUITECTURA.md`: el LOCK de fronteras es el manifiesto, verificado por
> `arquitectura/test_fronteras.py`.
>
> Nota de alcance: el manifiesto declara **siete** componentes (`identidad`, `catalogo`,
> `inteligencia`, `comercio`, `operacion`, `ingesta`, `gateway`), pero `servicios/` tiene
> hoy código para **seis**. `ingesta` está declarado con `base_datos = ""` y `tablas = []`
> (`manifiesto.toml:178-190`) y todavía no tiene directorio de código: la prueba de
> lenguaje lo salta a propósito (`test_fronteras.py:400`, `pytest.skip("... todavia no tiene
> codigo")`). Es un desplegable planeado, no un desplegable presente. Todo lo que sigue se
> refiere a los seis que existen.

---

## 1. Resumen ejecutivo

La arquitectura de Tukit está **sana para su escala**. Las fronteras entre servicios —una
base por servicio, ningún import cruzado, referencias entre dominios declaradas— no son una
aspiración escrita en un diagrama: están codificadas en `manifiesto.toml` y verificadas en
continuo por cinco funciones de aptitud (`test_fronteras.py`) que, además, tienen su propia
prueba de que de verdad detectan (`test_fronteras_se_activan.py`). La comunicación entre
servicios ya trae lo caro de hacer bien: timeouts por llamador, patrón *outbox* con
`FOR UPDATE SKIP LOCKED`, degradación honesta (devolver `None` o un rechazo de negocio en
vez de un 500), y una puerta que rutea por prefijo declarado con disciplina 404/501/503.

La deuda real es **una sola y está contenida**: los archivos de rutas están gordos. Un
único manejador de FastAPI mezcla las tres capas —HTTP/validación, reglas de dominio y
persistencia (SQL crudo)— en la misma función. No es un problema de fronteras entre
servicios (esas están bien); es un problema de fronteras **dentro** de cada servicio. Se ve
en el tamaño: `catalogo/admin_http.py` tiene 1.984 líneas, `inteligencia/trabajos.py` 1.826,
`catalogo/admin.py` 1.656.

**Qué sale ahora:** el correlation-ID (un `contextvar` en `tukit_comun/http.py`, un archivo
compartido, que beneficia a los seis servicios de golpe; §7). **Qué se paga después y
oportunistamente:** el adelgazamiento de los archivos de rutas hacia `dominio/` +
`repositorios/`, empezando por los peores, y solo el archivo que ya se está editando (§5).
No se justifica una reescritura grande: para un MVP de ~4 personas a ~0.001 escrituras/s,
sería trabajo especulativo.

---

## 2. Los tests — la premisa refutada

La premisa a refutar fue: *"un chorrero de tests inútiles"*. La evidencia dice lo contrario.

**Cuántos hay.** `pytest --collect-only` recoge **994 pruebas** de Python en el monorepo.
Repartidas así por directorio de tests:

| Ubicación | Archivos `test_*.py` | Qué asegura |
|---|---|---|
| `arquitectura/` | 2 | Funciones de aptitud (fronteras entre servicios) + su meta-prueba |
| `servicios/catalogo/tests` | 20 | Catálogo, curaduría, cargadores, emparejamiento, embeddings, sustituibilidad |
| `servicios/inteligencia/tests` | 11 | Optimizador, trabajos, parseo, percepción, poller, onboarding |
| `servicios/identidad/tests` | 8 | Autorización, privacidad/derecho al olvido, sesiones, poller |
| `servicios/comercio/tests` | 4 | Checkout, precio congelado, estado de pedido, pasarela |
| `servicios/operacion/tests` | 3 | Repartidor (outbox), notificación sin contacto, API |
| `servicios/gateway/tests` | 1 | Ruteo por prefijo |
| **Total** | **54 archivos** | |

Que no son "inútiles" se ve en **qué afirman**, no en cuántos son. Las de `arquitectura/`
son pruebas de invariantes estructurales que atrapan exactamente el defecto que originó el
rediseño (dos servicios declarando el maestro del mismo catálogo, `test_fronteras.py:156`).
Y las de dominio por servicio afirman reglas del contrato, no líneas de cobertura: que el
subtotal de una línea es `precio × unidades_a_comprar` y no `× cantidad_pedida`
(`test_precio_congelado.py`), que un `422 precio_cambiado` frena la orden antes de cobrar
(`test_checkout.py`), que el derecho al olvido alcanza `kit.perfil`/`pesos_usados`
(`test_privacidad.py`), que el emparejamiento se **abstiene** en vez de inventar
(`test_descubrir.py`). Cada una defiende una invariante escrita en `CONTRATO_API.md`.

**Higiene de la suite.** El escaneo de todo el repo da **0 `xfail`** y solo **2 `skip`**,
los dos legítimos y ambos en `test_fronteras.py`:

- `:284` — `pytest.skip("No hay otras bases declaradas.")`: la regla 3 no aplica a `gateway`
  ni a `ingesta`, que no tienen base propia (`base_datos = ""`).
- `:400` — `pytest.skip("... todavia no tiene codigo")`: la prueba de lenguaje se salta
  `ingesta`, que aún no tiene directorio de código.

No son deuda escondida: son dos ramas de guarda que se apagan solas cuando el componente
exista.

### 2.1 El único test que falla, y es PRE-EXISTENTE

Corriendo `arquitectura/`:

```
1 failed, 54 passed, 1 skipped
FAILED test_fronteras.py::test_ningun_servicio_nombra_la_base_de_otro[inteligencia]
```

Qué comprueba esa prueba (`test_fronteras.py:277-297`): la **regla 3**, "una base por
servicio". Para cada servicio, arma el conjunto de nombres de las bases *ajenas* y recorre
cada línea de cada `.py`; si el nombre de una base ajena aparece como subcadena en una
línea, lo marca como infracción (`if base in linea`).

Por qué `inteligencia` la dispara:

```
servicios/inteligencia/tukit_inteligencia/trabajos.py:1008
    menciona la base `tukit_operacion` (de operacion)
```

La línea 1008 es un **docstring**, no una conexión a una base:

```
El repartidor de Operacion (`tukit_operacion.repartidor`) lo drena y avisa al
```

El detector es un `substring match` sin distinguir código de comentario, y la cadena
`tukit_operacion` es a la vez el nombre del **paquete** de Operación (`tukit_operacion`, del
manifiesto) y el nombre de su **base de datos** (`base_datos = "tukit_operacion"`,
`manifiesto.toml:161`). El docstring nombra el paquete —una referencia correcta y deseable a
quién drena la bandeja de salida— y la prueba lo confunde con la base. Es un **falso
positivo**, no una infracción real: `inteligencia` no se conecta a la base de `operacion`;
la comunicación va por la bandeja de salida (§6).

**Esto es PRE-EXISTENTE.** No lo introdujo el trabajo reciente: es un choque estructural
entre la convención de nombres (`tukit_<servicio>` sirve de nombre de paquete y de base) y
un detector que mira líneas crudas. Existe desde que ese docstring nombra el paquete
hermano.

**Dirección del arreglo (una línea, no ahora):** en `test_ningun_servicio_nombra_la_base_de_otro`,
saltar comentarios y docstrings antes del `if base in linea` —lo natural es reusar el árbol
`ast` que ya usan las otras cuatro reglas y buscar la cadena solo en literales que no sean
docstrings, o exigir que aparezca en contexto de cadena de conexión (`postgresql://.../base`)
en vez de como subcadena suelta. Con eso el falso positivo desaparece sin relajar la regla.

### 2.2 Higiene: los tests de TypeScript no corren en CI

Hay dos pruebas de TS en el repo:

- `libs/ts/tukit-contrato/test/atributos.test.ts` — su `package.json` **sí** define
  `"test": "node --test \"test/**/*.test.ts\""`.
- `apps/admin/test/atributos-editor.test.ts` — el `package.json` de `apps/admin`
  **no** tiene script `test` (solo `dev`, `build`, `start`, `lint`, `typecheck`).

Y el `package.json` **raíz** agrega `lint` y `typecheck` sobre los workspaces, pero **no
tiene un script `test` agregado**. Consecuencia: la prueba de `apps/admin` no tiene ni
runner propio, y la de `tukit-contrato` solo corre si alguien entra al workspace a mano. En
la práctica **las 2 pruebas de TS nunca se ejecutan en un pipeline**. Es higiene barata:
añadir al raíz un `"test"` que recorra los workspaces con script `test`, y dar a `apps/admin`
su propio script. No es un problema de arquitectura; es una tubería incompleta.

---

## 3. "Archivos sueltos" — confirmado, con matices

La queja es **cierta**, pero el diagnóstico simple ("no hay capas") es falso. Los servicios
**ya tienen** parte de la separación por capas hecha, y hecha bien:

- **`modelos/` en todos.** El ORM no está suelto: cada servicio tiene un paquete `modelos/`
  partido por sub-dominio. `catalogo/modelos/` = `catalogo.py`, `editorial.py`, `listas.py`,
  `oferta.py`, `propuesta.py`, `base.py`. `comercio/modelos/` = `pedidos.py`,
  `inventario.py`, `pagos.py`, `entrega.py`, `proveedores.py`, `eventos.py`. Igual en
  `identidad`, `inteligencia`, `operacion`. La capa de persistencia declarativa ya está
  separada del transporte.
- **`remoto.py` — el adaptador de salida HTTP.** `catalogo`, `comercio`, `inteligencia` y
  `operacion` aíslan sus llamadas salientes en un `remoto.py` limpio: una clase por
  servicio-destino, sustituible en pruebas, con el manejo de error propio de cada llamada.
  `comercio/remoto.py` son 69 líneas dedicadas a una sola pregunta ("re-verifica el precio
  con Catálogo"); `inteligencia/remoto.py` (292 líneas) tiene los clientes a Identidad,
  Catálogo y Comercio.
- **Los *workers* están limpios y aparte.** `comercio/pasarela.py` (adaptador de pasarela),
  `operacion/repartidor.py` y los `poller.py` de `identidad` e `inteligencia`
  (drenadores de la bandeja de salida), `operacion/notificador.py`. Ninguno mezcla HTTP con
  su trabajo.

El **matiz** es dónde queda la deuda: **dentro de los archivos de rutas**. La capa que
falta no es "modelos" ni "adaptadores de salida" —esas existen— sino la de **dominio** y la
de **repositorio de lectura/escritura de la propia base**. Hoy un solo manejador de FastAPI
hace las tres cosas.

### 3.1 Un caso concreto: `comercio.crear_orden` (`api.py:357-457`)

El endpoint `POST /v1/ordenes` es el ejemplo limpio del problema, porque en 100 líneas se
ven las tres capas trenzadas en una sola función:

```python
@app.post("/v1/ordenes", ...)                                    # (a) HTTP
async def crear_orden(solicitud: SolicitudOrden) -> dict[str, Any]:
    usuario_id = _uuid_o_422(solicitud.usuario_id, "usuario_id")            # (a) validación
    ...
    for linea in solicitud.lineas:                                          # (b) DOMINIO:
        try:                                                                #     re-verificar
            resuelto = await app.state.catalogo.resolver(linea.sku)         #     precio y
        except CatalogoCaido:                                               #     congelar
            raise ErrorDominio("catalogo_no_disponible", ..., estado=503)
        precio_actual = resuelto[1] if resuelto else None
        if resuelto is None or precio_actual is None or precio_actual != linea.precio_unitario:
            cambios.append({...})                                           #     invariante §9.1
    if cambios:
        raise ErrorDominio("precio_cambiado", ..., estado=422, campo="lineas")
    ...
    async with app.state.motor.sesion() as db:                             # (c) PERSISTENCIA:
        conexion = await db.connection()                                    #     SQL crudo
        await conexion.execute(insert(PEDIDO).values(...))                  #     4 inserts
        for linea in solicitud.lineas:
            await conexion.execute(insert(LINEA_PEDIDO).values(...))        #     (pedido,
            await conexion.execute(insert(RESERVA).values(...))             #      línea,
        await conexion.execute(insert(ENVIO).values(...))                   #      reserva,
        fila = (await conexion.execute(select(PEDIDO)...)).one()            #      envío)
        return await _pedido_completo(conexion, fila)                       # (a) serializar
```

Las tres capas identificadas por color:

- **(a) HTTP/validación:** el decorador, la firma `SolicitudOrden`, los `_uuid_o_422`, la
  traducción de errores a códigos del contrato, la serialización de salida.
- **(b) Dominio:** la invariante del §9 —"re-verifica el precio contra Catálogo, y solo si
  coincide congela"— vive dentro del handler. Es la regla más importante del cobro
  (`FU-08`, no cobrar a un precio que cambió) y está atada al framework HTTP: no se puede
  probar sin levantar FastAPI y montar `app.state`.
- **(c) Persistencia:** cuatro `insert()` + un `select()` de SQLAlchemy Core, con la
  estructura de tablas (`PEDIDO`, `LINEA_PEDIDO`, `RESERVA`, `ENVIO`) desplegada en el mismo
  cuerpo.

El resultado es una función que solo se puede probar *end to end* (la prueba tiene que
falsear el cliente de Catálogo, montar el motor y ejercer HTTP), cuando la invariante que
importa —"si el precio cambió, no cierres"— es una regla pura que debería probarse con una
lista de líneas y un diccionario de precios, sin red ni base. Ese es el costo de la mezcla,
y es el mismo en `catalogo/admin_http.py` (rutas como `importar_lista`, `api.py:569-780`) y
en `inteligencia/trabajos.py`.

---

## 4. El objetivo: por capas (puertos y adaptadores), NO MVC

**Por qué no MVC.** MVC tiene sentido cuando hay una **Vista** que el backend renderiza. La
API de Tukit es *headless*: devuelve JSON y el frontend (Next.js) es quien pinta. No hay
View que separar; forzar "Modelo-Vista-Controlador" sobre un servicio JSON deja el patrón
sin su tercera pata y no explica dónde van las reglas de negocio. Lo que falta no es una
Vista, es una capa de **dominio** libre de HTTP.

**El objetivo.** Puertos y adaptadores (arquitectura hexagonal) *ligero*, apoyado en lo que
ya existe:

- **`routers/` (controlador delgado)** — adaptador de entrada. Parsea la petición, llama al
  dominio, traduce el resultado a HTTP y al sobre de error del contrato. Sin reglas de
  negocio, sin SQL.
- **`dominio/` (el núcleo)** — reglas e invariantes, **sin FastAPI, sin SQLAlchemy**.
  Funciones puras y objetos de dominio que se prueban con `assert`, sin red ni base.
- **`repositorios/` (adaptador de salida a la propia base)** — el SQL de lectura/escritura,
  detrás de una interfaz que el dominio pide. Envuelve lo que hoy es `insert()`/`select()`
  suelto dentro del handler.
- **`modelos/`** (ya existe) — el mapeo ORM declarativo.
- **`remoto.py`** (ya existe) — adaptador de salida HTTP a otros servicios.

Árbol objetivo (ejemplo con `comercio`; el resto igual):

```
servicios/comercio/tukit_comercio/
├── api.py                # app FastAPI + monta routers  (queda delgado)
├── routers/
│   ├── ordenes.py        # POST /v1/ordenes, /pago, GET /{id}  → llama a dominio
│   ├── pedidos.py        # tablero de logística
│   └── webhooks.py       # /v1/webhooks/wompi
├── dominio/
│   ├── ordenes.py        # reverificar_precios(...), congelar(...): PURO, sin HTTP ni SQL
│   └── pagos.py          # idempotencia del webhook: PURO
├── repositorios/
│   └── pedidos.py        # crear_pedido(conexion, ...), pedido_completo(...)
├── modelos/              # (ya existe) ORM
├── remoto.py             # (ya existe) cliente HTTP a Catálogo
└── pasarela.py           # (ya existe) adaptador de pasarela
```

### 4.1 El mismo `crear_orden`, refactorizado

**Dominio (`dominio/ordenes.py`) — puro, probable con `assert`:**

```python
@dataclass(frozen=True)
class CambioPrecio:
    sku: str
    precio_aprobado: int
    precio_actual: int | None

def reverificar_precios(
    lineas: list[LineaSolicitada],
    precio_vigente: Callable[[str], tuple[uuid.UUID, int | None] | None],
) -> tuple[dict[str, uuid.UUID], list[CambioPrecio]]:
    """La invariante del §9: qué líneas cambiaron de precio y cuáles quedan congelables.
    No sabe de HTTP ni de base: recibe una función que le dice el precio vigente."""
    ids: dict[str, uuid.UUID] = {}
    cambios: list[CambioPrecio] = []
    for linea in lineas:
        resuelto = precio_vigente(linea.sku)
        actual = resuelto[1] if resuelto else None
        if resuelto is None or actual is None or actual != linea.precio_unitario:
            cambios.append(CambioPrecio(linea.sku, linea.precio_unitario, actual))
        else:
            ids[linea.sku] = resuelto[0]
    return ids, cambios
```

**Router (`routers/ordenes.py`) — delgado, traduce a HTTP:**

```python
@router.post("/v1/ordenes", status_code=201)
async def crear_orden(solicitud: SolicitudOrden) -> dict[str, Any]:
    usuario_id = _uuid_o_422(solicitud.usuario_id, "usuario_id")
    try:
        precio = lambda sku: _sincronico(app.state.catalogo.resolver(sku))
        ids, cambios = reverificar_precios(solicitud.lineas, precio)   # ← dominio
    except CatalogoCaido:
        raise ErrorDominio("catalogo_no_disponible", "...", estado=503)
    if cambios:
        raise ErrorDominio("precio_cambiado", "...", estado=422, campo="lineas")
    async with app.state.motor.sesion() as db:
        pedido_id = await repositorios.crear_pedido(db, solicitud, usuario_id, ids)  # ← repo
        return await repositorios.pedido_completo(db, pedido_id)
```

**Repositorio (`repositorios/pedidos.py`) — el SQL, aislado:**

```python
async def crear_pedido(db, solicitud, usuario_id, ids) -> uuid.UUID:
    """Los 4 inserts (pedido, línea, reserva, envío) en una transacción. Nada más."""
    ...
```

Ganancia concreta: la invariante del §9 (`reverificar_precios`) se prueba con una lista y un
diccionario, sin levantar FastAPI ni Postgres. El router queda como lo que debe ser —traducción
HTTP— y el SQL deja de estar embebido en la lógica de negocio. Ninguna frontera *entre*
servicios cambia; esto es todo interno a `comercio`.

---

## 5. Orden de migración (peor primero, oportunista)

**Marco, antes de la tabla:** esto **no** es una reescritura de golpe. Es *boy-scouting*:
cuando toques un archivo de esta lista por otra razón, adelgazas la ruta que estás editando
y solo esa. Para un MVP de ~4 personas a ~0.001 escrituras/s, refactorizar 12.000 líneas de
una sentada es trabajo especulativo (YAGNI): el código gordo no falla ni es lento, solo es
incómodo de probar. Se paga cuando la incomodidad aparece, no antes.

LOC verificadas con `wc -l`, worst-first:

| # | Archivo | LOC | Por qué primero | Extraer a |
|---|---|---:|---|---|
| 1 | `catalogo/admin_http.py` | 1.984 | El más gordo; muchas rutas de curaduría con SQL crudo | `dominio/curaduria.py`, `repositorios/listas.py` |
| 1 | `catalogo/admin.py` | 1.656 | Lógica de curaduría del catálogo | `dominio/curaduria.py` |
| 1 | `catalogo/descubrir.py` | 1.338 | Emparejamiento (léxico+vector); reglas mezcladas con acceso | `dominio/emparejar.py` |
| 2 | `inteligencia/trabajos.py` | 1.826 | El pipeline entero (percepción→optimización) en un archivo | `dominio/pipeline.py`, `repositorios/trabajos.py` |
| 2 | `inteligencia/optimizador.py` | 979 | NSGA-II / heurística; ya casi puro, falta aislar el I/O | `dominio/optimizar.py` |
| 3 | `comercio/api.py` | 682 | El caso claro de §3.1; invariante §9 dentro del handler | `dominio/ordenes.py`, `repositorios/pedidos.py` |
| 4 | `inteligencia/api.py` | 1.076 | Lector del acudiente + admin | `routers/`, `repositorios/` |
| 4 | `identidad/api.py` | (resto) | Autorización ya está aparte en `autorizacion.py`; el resto es rutas | `routers/` |
| 4 | `operacion/api.py` | 197 | Ya delgado; el trabajo real está en `repartidor.py`/`notificador.py` | — (poco que hacer) |

- **`gateway/api.py` (255 LOC) se queda como un solo archivo plano, y es correcto.** El
  manifiesto lo declara "sin dominio y sin base" (`manifiesto.toml:192-202`) y el código lo
  cumple al pie de la letra: no hay una consulta, ni un modelo, ni una decisión de negocio,
  solo mira el prefijo y reenvía. Meterle carpetas `dominio/`/`repositorios/` sería inventar
  capas para un componente que a propósito no tiene ninguna.
- **`ingesta`** no tiene código todavía; nace directamente con la forma objetivo.

Regla práctica: prioridad 1 y 2 son los archivos que más se tocan y peor se prueban; 3 es el
ejemplo pedagógico ya trazado en §3.1/§4.1; 4 es de baja prioridad. Nada de esto bloquea
funcionalidad; todo mejora la *probabilidad* de las invariantes.

---

## 6. Comunicación entre servicios

### 6.1 Lo que YA está (verificado en código)

- **Timeouts por llamador.** Cada adaptador fija su propio `ESPERA_SEGUNDOS`, no un valor
  global: `gateway/api.py:49` = 300 s (detrás hay un pipeline de minutos),
  `inteligencia/remoto.py:45` = 60 s, `comercio/remoto.py:24` = 30 s,
  `comercio/pasarela.py:49` = 30 s, `operacion/remoto.py:23` = 30 s. El ayudante
  `cliente_efimero(cliente, espera)` (`tukit_comun/http.py:82-105`) centraliza solo el
  **ciclo de vida** del cliente httpx (tomar el inyectado en pruebas o abrir uno efímero y
  cerrarlo); el manejo de error se queda en cada llamador a propósito.
- **Patrón *outbox* con `FOR UPDATE SKIP LOCKED`.** Cada servicio tiene su `bandeja_salida`
  local (única tabla replicada, `manifiesto.toml:36`) y el evento se escribe en la MISMA
  transacción que el cambio que lo origina (`inteligencia/trabajos.py:1005`,
  `_publicar_evento`). Los drenadores usan bloqueo sin espera:
  `operacion/repartidor.py:125`, `identidad/poller.py:112`, `inteligencia/poller.py:96` —
  todos `.with_for_update(skip_locked=True)`. Así dos réplicas del poller no pelean por la
  misma fila.
- **Degradación honesta.** Los `remoto.py` devuelven `None` cuando la dependencia opcional
  no responde (`inteligencia/remoto.py:226-227,241-242`: caída de Identidad degrada el
  trabajo, no lo tumba; quien llama anota la degradación). El cliente de Comercio pasa los
  rechazos de negocio como `(estado, cuerpo)` y solo levanta `RemotoCaido` en 5xx o red
  (`inteligencia/remoto.py:266-279`). En el cobro, Catálogo caído es `503`, nunca un cobro a
  ciegas (`comercio/api.py:380-385`).
- **Sondas.** `GET /salud` en cada servicio (`tukit_comun/http.py:172-174`) y, en la puerta,
  `GET /v1/servicios` (`gateway/api.py:155-170`) que pega al `/salud` de los de atrás y dice
  la verdad sobre los tres, porque `/salud` de la puerta contestaría `ok` con todo caído.
- **Puerta con disciplina de códigos.** Ruteo por prefijo *declarado*, no comodín
  (`gateway/api.py:132-136`): ruta desconocida → `404 ruta_desconocida` con la lista de las
  que sí existen (`:196-203`); ruta del contrato sin servicio → `501 no_implementado` con la
  sección (`:181-192`); servicio caído → `503 servicio_no_disponible` (no 502: "no falló, no
  está", `:221-231`).

### 6.2 Lo que NO está

- **Correlation-ID** — se implementa ahora, aparte (§7).
- **Reintentos / *backoff*** — no hay reintento automático de ninguna llamada saliente.
- **Circuit breakers** — no hay.
- **Métricas / *tracing* distribuido** — no hay instrumentación de trazas ni exportador.

### 6.3 Roadmap y lo que es YAGNI

- **Circuit breakers y *tracing* distribuido: YAGNI ahora.** A ~0.001 escrituras/s y con seis
  procesos en una máquina, no hay tormenta de reintentos que cortar ni una topología que
  trazar que el log y `/v1/servicios` no cubran. Entran cuando haya volumen y despliegue
  distribuido, no antes.
- **Reintentos: solo para GET idempotentes.** Un reintento ciego sobre un `POST /v1/ordenes`
  o `POST /v1/contactos` es un doble cobro / un efecto lateral duplicado —justo el modo de
  falla más caro del negocio (`CONTRATO_API.md §9`). Si algún día se añade *backoff*, va
  únicamente en las lecturas idempotentes; las escrituras se protegen por idempotencia de
  aplicación (el webhook de Wompi ya es idempotente contra
  `comercio.evento_pasarela_procesado`), no por reintento de transporte.

---

## 7. Lo que se implementa ahora: correlation-ID (decisión C)

> Se describe, no se implementa aquí. El cambio sale **en una PR aparte, en curso**.

**Qué es.** Un middleware de alcance por petición en `tukit_comun/http.py`, dentro de
`crear_app` (hoy `:115-176`). Al entrar una petición, lee la cabecera `x-correlation-id`; si
viene, la respeta; si no, acuña una nueva (un `uuid4`). El identificador se guarda en un
`contextvar` de módulo, de modo que cualquier código dentro de esa petición (incluidos los
`remoto.py`) lo puede leer sin pasarlo por parámetro. En la respuesta —y en el sobre de
error de `ErrorDominio` y de `RequestValidationError`— se **eco** de vuelta el
`x-correlation-id`.

**Propagación saliente.** `cliente_efimero` (`:82-105`) —o el punto donde cada `remoto.py`
arma sus cabeceras— añade `x-correlation-id` de forma **aditiva** a las llamadas salientes,
tomándolo del `contextvar`. Así una petición del acudiente que atraviesa
gateway → inteligencia → catálogo/identidad/comercio arrastra el mismo id por toda la
cadena.

**Punto de acuñado de entrada.** El manejador `reenviar` de la puerta
(`gateway/api.py:178`, el único punto por el que pasa todo el tráfico) es donde nace el id
para el tráfico que entra sin uno. La puerta ya reenvía las cabeceras del cliente salvo las
de `CABECERAS_SALTADAS` (`:54,206`); `x-correlation-id` no está en esa lista, así que viaja
intacto hacia atrás sin cambios adicionales.

**Por qué este cambio y no otro.** Es la única mejora de comunicación de **alto valor y bajo
esfuerzo** que toca **un solo archivo compartido** (`tukit_comun/http.py`) y beneficia a los
seis servicios de golpe: hoy, si algo falla en la cadena, no hay forma de amarrar la entrada
del gateway con la línea de log del servicio de atrás. Con un id compartido, un fallo se
sigue de punta a punta. No añade dependencias, no cambia el contrato (es una cabecera
aditiva), y no toca la lógica de dominio de nadie. Los circuit breakers y el *tracing*
completo son la versión pesada de esto y quedan para cuando haya volumen; el correlation-ID
es el 20% que da el 80% de la trazabilidad hoy.

---

## 8. Veredicto

La arquitectura es **sólida para su escala**. Las fronteras que de verdad importan —las que
separan seis desplegables sobre cinco bases— están declaradas en `manifiesto.toml` y
verificadas en continuo por funciones de aptitud que reproducen defectos reales del sistema
anterior. La comunicación entre servicios ya trae lo caro de hacer bien: timeouts por
llamador, outbox transaccional con `SKIP LOCKED`, degradación honesta y una puerta
disciplinada.

La deuda está **contenida a una sola cosa**: los archivos de rutas están gordos porque
mezclan HTTP, dominio y persistencia en la misma función. No es un fallo de fronteras entre
servicios (esas están bien) sino de fronteras dentro de cada uno, y se paga **adelgazando
oportunistamente** el archivo que ya se está tocando —peor primero (`catalogo/admin_http.py`,
`inteligencia/trabajos.py`, `comercio/api.py`)— hacia `dominio/` + `repositorios/`, junto a
los `modelos/` y `remoto.py` que ya existen. La gateway se queda plana, y con razón.

**No hay ninguna reescritura grande justificada.** El único cambio que sale ahora es el
correlation-ID —un `contextvar` en un archivo compartido— y es exactamente la clase de mejora
que un sistema de esta escala debe hacer: alto valor, bajo esfuerzo, cero dependencias
nuevas.
