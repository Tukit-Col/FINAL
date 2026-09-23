# Curaduría del catálogo en la SPA: cola de propuestas + alta de útiles/libros + atributos tipados

Fecha: 2026-09-23
Estado: propuesto (pendiente de aprobación)

## Intención

Portar a la SPA `/catalogo` (apps/admin) la mitad de la vieja herramienta
`tukit_catalogo.admin` (la de `http.server`, previa a la SPA) que todavía no
existe en la SPA, y arreglar el editor de productos para que se puedan editar
**todos** los atributos de un producto sin perder su tipo.

En una frase: que una persona pueda, desde la SPA, curar el catálogo *proactivamente*
—añadir útiles y libros, verlos entrar a una cola de revisión, aprobarlos o
rechazarlos, y editar cada atributo de un producto— igual que hoy solo puede
hacerse por CLI/`admin.py`.

### Quién y para qué

El personal interno de Tukit que prepara el catálogo **antes** de que un
acudiente pregunte (curaduría proactiva, no la revisión de una lista concreta
de colegio). Éxito = pueden llenar huecos del catálogo y corregir productos sin
tocar la terminal ni el `admin.py` local.

### Qué NO es

- No es la revisión de listas de colegio (esa es la cola de `/` en apps/admin,
  servida por inteligencia). Esto es curaduría de catálogo, servida por catálogo.
- No toca la promesa de que `api.py` de catálogo es de **solo lectura**: la
  escritura nueva vive en `admin_http.py`, que ya es la superficie de escritura.

## Contexto verificado (estado real del código, 2026-09-23)

- La SPA `/catalogo` (apps/admin) **ya existe** y su CRUD de productos funciona
  contra el backend vivo: editar nombre/marca/nivel/personaje/imagen/unidad/
  empaque/quality/es_propio/atributos, reclasificar y baja suave devuelven 200.
- El editor (`EditorProducto.tsx`) **ya tiene** un editor clave-valor de
  atributos, PERO manda cada valor como **texto** (línea ~128:
  `mapaAtributos[k] = valor`). La base guarda valores **tipados**
  (`hojas: 80` int, `deposito: true` bool, `rayado: "cuadriculado"` str).
  Cada guardado degrada `80` → `"80"`. **Este es el bug de "no puedo editar
  todos los atributos".**
- El concepto parte sus atributos en dos (`test_atributos_contrato.py`):
  `atributos_discriminantes` (filtran la búsqueda) vs `atributos_descriptivos`
  (solo se le muestran al acudiente). El editor plano no refleja esa
  distinción ni pre-puebla las claves que el concepto declara.
- La **etiqueta de personalización** es el campo `personaje` (eje ortogonal al
  nivel). Ya se edita; falta poder asignarla en el alta.
- **Añadir útil / añadir libro** existen solo como funciones en `admin.py`
  (`agregar_util`, `agregar_libro`) que hacen `_encolar` → `resolver`. **No hay
  endpoint HTTP.**
- La **cola de propuestas** existe solo como `descubrir.listar_pendientes`
  (CLI). **No hay endpoint HTTP de listado.** Sí existe
  `POST /v1/admin/propuestas/{id}/rechazar` en `admin_http.py`.
- `POST /v1/admin/productos` (que el contrato `altaProducto` y el componente
  `AltaProducto.tsx` ya llaman, en el flujo de revisión de listas) **devuelve
  404: nadie lo sirve.** El gateway manda `/v1/admin` a inteligencia, que no lo
  implementa. Es un bug preexistente, fuera de alcance salvo que lo crucemos.
- `tiendas.buscar(slug, consulta)` ya hace búsqueda **en vivo**: VTEX para
  `exito` y `panamericana`, Shopify para `grancentral`. Verificado vivo hoy
  (Panamericana 206, Éxito 308, Shopify OK).
- `buscalibre` está registrada como tienda pero **NO es VTEX** (probado:
  `/api/catalog_system/...` → 404). Sus libros vinieron de Firecrawl
  (`libros_firecrawl.csv`). No hay búsqueda en vivo de libros.
- Gateway (`servicios/gateway/tukit_gateway/api.py`): ruteo por prefijo más
  largo. `/v1/admin/{listas,propuestas,sugerencias}` → catálogo; `/v1/admin` →
  inteligencia. `/v1/catalogo`, `/v1/listas` → catálogo.

## Decisión de arquitectura

**Enfoque A (aprobado):** endpoints nuevos en `catalogo/admin_http.py` bajo el
prefijo `/v1/admin/catalogo/*`, reusando `_encolar` / `resolver` /
`tiendas.buscar` sin reimplementar dominio. Se agrega el prefijo
`/v1/admin/catalogo` al gateway → catálogo. `api.py` sigue read-only.

Motivo: `admin_http.py` ya es la superficie de escritura de catálogo por HTTP
y ya reusa `descubrir`. La cola queda como recurso propio y la frontera
documentada (ADR 0008/0012; catálogo solo importa `.` y `tukit_comun`) se
mantiene, verificable por las pruebas de fronteras.

## Diseño por piezas

### Pieza 1 — Backend: cola + alta (catálogo, `admin_http.py`)

Router nuevo (o extensión del existente) bajo `/v1/admin/catalogo`:

- `GET /v1/admin/catalogo/propuestas` — la cola de pendientes.
  Misma consulta que `descubrir.listar_pendientes`, pero devuelve JSON (no
  imprime): `id` (corto y completo), `texto_origen`, `nombre`, `marca`,
  `precio_centavos`, `nivel_sugerido`, `concepto` (código + nombre canónico o
  `concepto_sugerido` si es nuevo), `tienda`, `origen`, `propuesta_en`.
  Filtrable por concepto (opcional).

- `GET /v1/admin/catalogo/tiendas/{slug}/buscar?consulta=&cuantos=` —
  candidatos para el alta de útil. Envuelve `tiendas.buscar`. Solo lectura
  externa; NO escribe. Slugs válidos: `exito`, `panamericana`, `grancentral`.

- `POST /v1/admin/catalogo/propuestas/util` — encola un útil elegido.
  Cuerpo: `{ concepto, tienda, sku_externo, nombre, marca, ean, url,
  imagen_url, precio, especificaciones, nivel_sugerido, personaje }`.
  Reusa la lógica de `admin.agregar_util` PERO **solo hasta `_encolar`**
  (no aprueba en el acto): la propuesta cae en la cola visible. Devuelve la
  propuesta encolada (con su `id`).

- `POST /v1/admin/catalogo/propuestas/libro` — encola un libro por ISBN.
  Cuerpo: `{ concepto, isbn, titulo, precio, tienda, nivel_sugerido,
  personaje }`. Reusa `admin.agregar_libro` hasta `_encolar`. Valida el ISBN
  con `cargador.isbn13_valido`. Devuelve la propuesta encolada.

- `POST /v1/admin/catalogo/propuestas/{id}/aprobar` — `resolver(aprobar=True,
  nivel=…)`. Nace el producto + oferta + precio.

- **Rechazar:** NO se crea ruta nueva. El SPA reusa la existente
  `POST /v1/admin/propuestas/{id}/rechazar` de `admin_http.py`
  (que ya llama a `resolver(aprobar=False, motivo, no_surtir)`). Así solo
  `aprobar`, `propuestas`, `alta` (útil/libro) y `buscar` son rutas nuevas bajo
  `/v1/admin/catalogo`, y `rechazar` queda donde ya está.

Regla clave: **encolar y aprobar son dos pasos separados** (a diferencia de
`admin.agregar_util`, que los encadenaba), para que la cola sea visible y la
persona decida el nivel al aprobar. Refactor: extraer de `agregar_util` /
`agregar_libro` la parte de "construir el dict y `_encolar`" como función
reutilizable, dejando a `admin.py` (CLI) encadenando encolar+aprobar como hoy.

### Pieza 2 — Backend: atributos tipados en el PATCH (catálogo, `api.py`)

- En `_validar_edicion`: si viene `atributos`, validar que sea un objeto de
  valores **escalares** (str, int, float, bool, o null) — no listas ni dicts
  anidados. Error `atributos_invalido` que nombra la clave ofensora.
- No se cambia el almacenamiento (ya es dict JSON). El fix real del tipo es en
  el cliente (Pieza 4): el backend solo endurece la guarda.

### Pieza 3 — Gateway

- Agregar `"/v1/admin/catalogo": "catalogo"` a `RUTAS`. Como el ruteo elige el
  prefijo más largo, gana sobre `/v1/admin` → inteligencia. Añadir prueba en
  `test_ruteo.py`.

### Pieza 4 — Contrato (libs/ts/tukit-contrato)

- Tipos nuevos: `PropuestaCola` (fila de la cola), `AltaUtil`, `AltaLibro`,
  `CandidatoTienda`, `AprobarPropuesta` (`{ nivel }`), `RechazarPropuesta`
  (`{ motivo?, no_surtir? }`).
- Métodos en `origen.ts` (interfaz) + `cliente-http.ts` (impl API) + el
  origen **simulado**: `colaPropuestas()`, `buscarEnTienda(slug, consulta)`,
  `altaUtil(cuerpo)`, `altaLibro(cuerpo)`, `aprobarPropuesta(id, nivel)`,
  `rechazarPropuesta(id, cuerpo)`.
- El simulado lee del corpus (`datos/catalogo/*.csv`, `libros_firecrawl.csv`)
  para que la SPA en modo `simulado` muestre una cola con datos reales.
- **Atributos tipados:** helper de contrato `inferirTipoAtributo(texto)` +
  `serializarAtributos(pares)` que convierte `"80"`→`80`, `"true"`→`true`,
  decimales, y deja texto lo demás. Usado por el editor.

### Pieza 5 — SPA (apps/admin)

- **Editor (`EditorProducto.tsx`):**
  - Al guardar, pasar los atributos por `serializarAtributos` (tipos correctos).
  - Recibir del padre los `atributos_discriminantes` / `atributos_descriptivos`
    del concepto del producto; renderizar dos grupos etiquetados
    ("filtra la búsqueda" / "solo informativo") y pre-poblar las claves que el
    concepto declara y el producto no tiene (valor vacío = no afirmar).
    Las claves libres siguen permitidas.
  - `personaje` ya está; sin cambios salvo dejar claro que es la etiqueta de
    personalización.
- **Cola de revisión:** sección/pestaña nueva en `/catalogo` (o componente
  `ColaCuraduria`) que lista `colaPropuestas()` con Aprobar (elige nivel) /
  Rechazar (motivo + checkbox no_surtir).
- **Añadir útil:** buscador contra `buscarEnTienda` (selector de tienda:
  Éxito / Panamericana / Gran Central), lista de candidatos con foto y precio,
  elegir uno → concepto + nivel + personaje → `altaUtil` → entra a la cola.
- **Añadir libro:** formulario manual (ISBN + título + precio + tienda +
  concepto + nivel + personaje) con **link "Buscar en Buscalibre"**
  (`https://www.buscalibre.com.co/libros/search?q=<isbn|titulo>`) porque
  Buscalibre no expone búsqueda en vivo. `altaLibro` → entra a la cola.
- **Route Handlers** nuevos en `apps/admin/src/app/api/catalogo/propuestas/**`
  y `.../tiendas/[slug]/buscar/route.ts`, que delegan a `origenDeDatos()`.
  El navegador nunca ve la URL del backend (patrón existente).

## Manejo de errores

- Backend: `ErrorDominio` con código nombrando el campo (patrón existente:
  `nivel_invalido`, `empaque_invalido`, `concepto_no_existe`, `isbn_invalido`,
  `tienda_desconocida`, `atributos_invalido`).
- SPA: muestra el mensaje del backend tal cual (nunca inventa uno), como ya
  hace `EditorProducto`.
- Precio: entero en centavos/pesos, validado en el form, en el Route Handler y
  en el origen (patrón de `AltaProducto.tsx`: tres veces a propósito, §1.4).

## Testing

- **Backend (pytest, estilo `test_api_admin.py`):**
  - Encolar útil y libro → aparecen en `GET .../propuestas`.
  - Aprobar → nace producto+oferta+precio; rechazar → descarta; no_surtir →
    concepto `no_comprar`.
  - `buscar` de tienda devuelve candidatos (mockear `tiendas.buscar`, no salir
    a la red en el test).
  - PATCH con atributos no escalares → `atributos_invalido`.
  - ISBN inválido → `isbn_invalido`.
- **Gateway:** `test_ruteo.py` — `/v1/admin/catalogo/...` → catálogo.
- **Contrato:** el simulado devuelve cola no vacía; `serializarAtributos`
  tiene pruebas unitarias (int/bool/decimal/texto).
- **Fronteras:** `make fronteras` sigue verde (catálogo solo `.` + `tukit_comun`).
- **Humo:** `make humo` sigue pasando.

## Fuera de alcance

- Arreglar el 404 de `POST /v1/admin/productos` del flujo de revisión de listas
  (bug preexistente, otro flujo). Se documenta, no se toca aquí.
- Subida de archivos de imagen (el backend es URL-only, sin cambios).
- Búsqueda en vivo de libros (Buscalibre no la expone; queda link-out + manual).

## Riesgos y decisiones abiertas

- **Persistencia al corpus:** el alta y la aprobación escriben en la base viva.
  Para que el corpus versionado (CSV) refleje el estado, hay que correr
  `make bd-volcar` como hoy. La SPA no lo dispara; se documenta en el LEEME.
  (Decisión: mantener el flujo actual, no automatizar el volcado desde la SPA.)
- **Ruteo de `rechazar` (resuelto):** el SPA usa la ruta existente
  `/v1/admin/propuestas/{id}/rechazar` (prefijo `/v1/admin/propuestas` → catálogo,
  ya en el gateway). Solo `aprobar`/`propuestas`/`alta`/`buscar` estrenan el
  prefijo `/v1/admin/catalogo`.
