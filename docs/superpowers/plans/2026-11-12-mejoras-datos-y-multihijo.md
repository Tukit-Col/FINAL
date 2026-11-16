# Datos del catálogo y bugs multi-hijo: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar el catálogo completo para el NSGA-II, enriquecer los kits de los colegios con fuentes reales, y arreglar que con dos hijos se pierdan el apodo y el personaje del segundo (y que con un hijo las 4 anclas de personaje salgan a veces incompletas).

**Architecture:** (1) Un auditor de campos puro sobre `productos_canonicos.csv` cuyo contrato es lo que consume `Candidato`; (2) extender `descubrir.py` con dos tiendas de libros; (3) en inteligencia, pasar de un solo `personaje` por pedido a swaps indexados por hijo, y hacer determinista la elección del producto de personaje; (4) en web, el apodo viaja desde `HijoSolicitud` hasta el kit.

**Tech Stack:** Python 3 (uv, pytest, pymoo), FastAPI, SQLAlchemy; Next.js/TypeScript en `apps/web` (tests con el runner de la app); Firecrawl.

**Spec:** `/Users/mariapaula.rodriguez/.claude/plans/te-acordas-donde-tenemos-wild-book.md` (Fases 1 y 2). Fases 3 a 5 (UX, admin, asistente) son planes aparte.

## Global Constraints

- Sin seeds falsos: `bd-sembrar` solo siembra productos; colegios, listas y casos salen del pipeline real.
- Todo campo enriquecido se registra en `datos/catalogo/procedencia_campos.csv`.
- El CSV es espejo de la base: cambios de datos van por `make bd-volcar ARGS=--escribir`, nunca editando a mano el volcado.
- Firecrawl tiene ~1000 créditos por ciclo: siempre conteo y `--solo-validar` antes de scrapear.
- NSGA-II sigue siendo obligatorio (pymoo); no reintroducir el fallback.
- Commits como MapaRuiz (`git config --local`), sin atribución de IA.
- Tests: TDD en el auditor y en el pipeline de personaje (la rotura silenciosa cuesta); el resto, código y luego un test enfocado. Sin tests de config/copy.

## Review Focus

- Dos hijos con el mismo colegio y grado pero apodos distintos: cada uno debe mostrar su apodo, no "Hijo N".
- Dos hijos con personajes distintos: cada uno recibe el suyo en sus anclas, y "lo que juntamos" no une productos de personajes diferentes.
- Dos hijos con el mismo personaje: sigue consolidando el mismo producto en una compra.
- Un hijo con un personaje que el catálogo surte en solo 3 de las 4 anclas: el kit sale con 3, y el faltante queda registrado (no silencioso).
- Mismo input dos veces: mismas 4 anclas y mismo producto (sin dependencia de orden de página).
- Personaje escrito con mayúsculas o tildes ("Spider-Man", "SPIDERMAN"): encuentra el producto.
- Catálogo con producto sin precio o sin imagen: el auditor lo reporta y el test de contrato falla.

---

## Mapa de archivos

- Crear `servicios/catalogo/tukit_catalogo/auditar_campos.py`: auditor puro (CSV a reporte).
- Crear `servicios/catalogo/tests/test_auditar_campos.py`.
- Modificar `Makefile`: target `bd-auditar` (y añadirlo a `.PHONY`, línea 10).
- Modificar `servicios/catalogo/tukit_catalogo/descubrir.py` y `datos/catalogo/tiendas.csv`: buscalibre y Librería Nacional.
- Modificar `servicios/catalogo/tukit_catalogo/repositorios/catalogo.py:~313`: match de personaje sin tildes ni mayúsculas.
- Modificar `servicios/inteligencia/tukit_inteligencia/dominio/pipeline.py:103-215`: swaps por hijo.
- Modificar `servicios/inteligencia/tukit_inteligencia/trabajos.py` (~L729, 1006, 1219, 2688, 3208): construir y pasar los swaps por hijo.
- Modificar `servicios/inteligencia/tukit_inteligencia/remoto.py:182`: elección determinista del producto de personaje.
- Tests: `servicios/inteligencia/tests/test_dominio_pipeline.py`, `test_fastroute.py`.
- Modificar `apps/web/src/app/empezar/FormularioEmpezar.tsx` (~L790 `HijoSolicitud`), `apps/web/src/lib/kit-vista.ts:28-45` y su test.

---

## Fase 1: Datos

### Task 1: Auditor de campos del catálogo

**Files:**
- Create: `servicios/catalogo/tukit_catalogo/auditar_campos.py`
- Create: `servicios/catalogo/tests/test_auditar_campos.py`
- Modify: `Makefile` (target `bd-auditar` junto a `bd-datos`, línea ~268; `.PHONY` línea 10)

**Interfaces:**
- Produces:
  - `CAMPOS_OBLIGATORIOS: tuple[str, ...]` = `("nombre", "marca", "nivel", "imagen_url", "unidad_base", "unidades_por_empaque", "concepto_id", "descripcion", "texto_embedding", "embedding_model")`.
  - `@dataclass(frozen=True) Hallazgo(producto_id: str, campo: str, motivo: str)`.
  - `auditar(productos: list[dict[str, str]], precios_por_producto: set[str], activos_solo: bool = True) -> list[Hallazgo]`: un hallazgo por campo vacío de un producto activo, más `campo="precio"` si el producto no tiene oferta con precio, más `campo="personaje"` si `nivel` o la ruta indican producto de personaje y está vacío no aplica (no se exige a los neutros).
  - `resumir(hallazgos: list[Hallazgo]) -> dict[str, int]`: conteo por campo.
  - `main(argv: list[str] | None = None) -> int`: lee `--datos` (dir), imprime el resumen, escribe `docs/informes/auditoria-campos-catalogo.md`, devuelve 1 si hay hallazgos en `--estricto`.

- [ ] **Step 1: Test que falla.** En `test_auditar_campos.py`: `test_producto_completo_sin_hallazgos` (producto con todos los campos y precio, `auditar(...) == []`); `test_campo_vacio_se_reporta` (imagen_url `""` produce `Hallazgo("p1", "imagen_url", "vacio")`); `test_sin_precio_se_reporta` (id fuera de `precios_por_producto` produce `campo == "precio"`); `test_inactivos_se_ignoran` (activo `"false"` con campos vacíos devuelve `[]`); `test_resumir_cuenta_por_campo`.
- [ ] **Step 2:** `cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" ../../.venv/bin/python -m pytest tests/test_auditar_campos.py -v` (usar la misma ruta de python que `$(PY)` en el Makefile). Esperado: FAIL, módulo no existe.
- [ ] **Step 3:** Implementar el módulo con `csv.DictReader` sobre `productos_canonicos.csv` y `precios_oferta.csv` + `ofertas_tienda.csv` (producto con al menos una oferta con precio > 0). Tratar `""`, espacios y `"nan"` como vacío.
- [ ] **Step 4:** Correr los tests; esperado PASS.
- [ ] **Step 5:** Target `bd-auditar` (`python -m tukit_catalogo.auditar_campos --datos ../../datos/catalogo $(ARGS)`), correrlo sobre el catálogo real y guardar el informe. Anotar el conteo por campo en el commit.
- [ ] **Step 6: Commit** `feat(catalogo): auditor de campos para el NSGA`.

### Task 2: Rellenar los vacíos del catálogo

**Files:**
- Modify: `datos/catalogo/*.csv` (vía `make`), `datos/catalogo/procedencia_campos.csv`

**Interfaces:**
- Consumes: informe de Task 1; `enriquecer.py` (`bd-enriquecer`), `completar.py` (`bd-completar`), `nivelar` (`bd-nivelar`).

- [ ] **Step 1:** `make bd-auditar` y ordenar los vacíos por campo. Decidir por campo el relleno: empaque/atributos/personaje salen del nombre (`make bd-enriquecer ARGS=--solo-validar`, luego sin flag); niveles con `make bd-nivelar`; imágenes con `make bd-enriquecer ARGS=--imagenes` (va a la red; contar productos sin imagen antes).
- [ ] **Step 2:** Lo que no se pueda inferir (descripcion, marca) se corrige en la base y se vuelca; no se inventa. Lo irresoluble queda en `revision_manual.csv`.
- [ ] **Step 3:** `make bd-volcar ARGS=--escribir`, luego `make bd-datos`. Esperado: sin errores de validación.
- [ ] **Step 4:** `make bd-auditar ARGS=--estricto` debe pasar para los campos que consume `Candidato` (nombre, marca, nivel, imagen_url, unidad_base, unidades_por_empaque, precio). Pytest: `servicios/catalogo/tests/test_catalogo_curado.py test_enriquecer.py test_atributos_contrato.py`.
- [ ] **Step 5: Commit** `data(catalogo): completa campos para el optimizador`.

### Task 3: Libros de los kits con buscalibre y Librería Nacional

**Files:**
- Modify: `servicios/catalogo/tukit_catalogo/descubrir.py`, `datos/catalogo/tiendas.csv`
- Test: `servicios/catalogo/tests/test_descubrir.py`

**Interfaces:**
- Produces: `TIENDAS_LIBROS: dict[str, str]` con claves `buscalibre` y `libreria_nacional` y su URL base; `def consulta_libro(titulo: str, isbn13: str | None) -> str` que arma la URL de búsqueda de cada tienda; `def fila_libro(tienda: str, bruto: dict) -> dict[str, str]` con las columnas de `libros_firecrawl.csv` (titulo, isbn13, editorial, precio, imagen_url, url_origen).

- [ ] **Step 1: Test que falla** en `test_descubrir.py`: `test_fila_libro_normaliza_precio_colombiano` (`"$ 54.900"` produce `"54900"`); `test_fila_libro_sin_imagen_se_marca` (imagen vacía queda `""`, no `None`).
- [ ] **Step 2:** Correr; esperado FAIL.
- [ ] **Step 3:** Implementar las dos funciones; agregar ambas tiendas a `tiendas.csv` con el mismo formato que las existentes.
- [ ] **Step 4:** PASS. Luego, sin gastar créditos: contar las líneas de libro de los kits canónicos sin imagen o sin ISBN (consulta a `linea_kit` de inteligencia) y registrar el número en el informe.
- [ ] **Step 5:** Corrida real con la skill `firecrawl-search` por lotes pequeños (primero el colegio de `docs/informes/auditoria-kits-agustiniano-septimo.md`); cada fila nueva con su procedencia. Cargar con `make bd-cargar`.
- [ ] **Step 6: Commit** `feat(catalogo): descubre libros en buscalibre y libreria nacional`.

---

## Fase 2: Multi-hijo y personaje

### Task 4: El producto de personaje se elige de forma determinista

**Files:**
- Modify: `servicios/catalogo/tukit_catalogo/repositorios/catalogo.py:~313-326`, `servicios/inteligencia/tukit_inteligencia/remoto.py:182`
- Test: `servicios/catalogo/tests/test_api_productos.py`, `servicios/inteligencia/tests/test_fastroute.py`

**Interfaces:**
- Produces: `RemotoCatalogo.producto_de_personaje(concepto: str, personaje: str) -> dict | None` sin cambio de firma, pero pide `por_pagina=20` y devuelve el candidato con (1) precio presente, (2) nivel `confiable` antes que `economico` antes que `premium`, (3) menor `precio_desde`, (4) `sku` ascendente como desempate. Función pura `elegir_producto_de_personaje(productos: list[dict]) -> dict | None` en `remoto.py`.
- Catálogo: el filtro `personaje` compara sin tildes ni mayúsculas ni guiones (`"Spider-Man"` encuentra `"spiderman"`).

- [ ] **Step 1: Tests que fallan:** `test_elegir_producto_de_personaje_es_determinista` (misma lista en dos órdenes devuelve el mismo sku); `test_prefiere_con_precio_y_confiable`; `test_filtro_personaje_ignora_tildes_y_guiones` (repositorio con producto `personaje="spiderman"`, consulta `"Spider-Man"` lo devuelve).
- [ ] **Step 2:** Correr ambos archivos; esperado FAIL.
- [ ] **Step 3:** Implementar `elegir_producto_de_personaje` y usarlo en `producto_de_personaje`; normalizar con `unicodedata` + quitar `-` y espacios en el filtro del repositorio.
- [ ] **Step 4:** PASS en ambos servicios.
- [ ] **Step 5: Commit** `fix(personaje): eleccion determinista y match normalizado`.

### Task 5: Swaps de personaje por hijo

**Files:**
- Modify: `servicios/inteligencia/tukit_inteligencia/dominio/pipeline.py:103-215`, `trabajos.py` (~L729, 1006, 1219, 2688, 3208)
- Test: `servicios/inteligencia/tests/test_dominio_pipeline.py`, `test_fastroute.py`

**Interfaces:**
- Produces:
  - `personajes_por_hijo(preferencias: dict) -> dict[str, str]`: hijo a su primer personaje (omite hijos sin personaje). Reemplaza a `_personaje_pedido` (que queda como alias del primer valor solo para `_anclar_kits`, ver Step 4).
  - `async def anclas_por_hijo(catalogo, personajes: dict[str, str]) -> dict[str, dict[str, dict]]` en `trabajos.py`: `{hijo: {concepto: producto}}`; consulta una vez por personaje distinto (cachea por nombre) y **registra con `logger.warning`** cada ancla no surtida (personaje, concepto).
  - `inyectar_personaje_fan(kits, swaps_por_hijo: dict[str, dict[str, dict]], preferencias) -> list` (la antigua `swaps` plana pasa a ser el caso de un solo hijo: se envuelve con la clave de ese hijo).
  - `_lineas_con_swap(lineas, swaps_por_hijo) -> set[int]`: agrupa por `(concepto, hijo)` y usa los swaps de **ese** hijo.
- Verificar primero (Step 1): que las claves de `personaje_por_hijo` (`"hijo-1"`) casan con `linea.hijo` (`"hijo-0"`/`"canonico"`). Si no casan, la tarea incluye una función `clave_de_hijo(preferencias, linea_hijo) -> str | None` documentada que los une por orden.

- [ ] **Step 1:** Leer `Renglon.hijo`/`LineaKit.hijo` en `optimizador.py` y cómo `nl2c.py:370` y el router (`routers/inteligencia.py:197`) nombran al hijo; escribir la correspondencia en el docstring de `personajes_por_hijo`.
- [ ] **Step 2: Tests que fallan** en `test_dominio_pipeline.py`: `test_dos_hijos_cada_uno_recibe_su_personaje` (hijo-1 spiderman, hijo-2 frozen: los skus del cuaderno ancla difieren por hijo); `test_mismo_personaje_consolida_una_compra` (ambos spiderman: una sola línea consolidada); `test_personajes_distintos_no_se_consolidan`; `test_hijo_sin_personaje_queda_neutro`.
- [ ] **Step 3:** Correr `pytest servicios/inteligencia/tests/test_dominio_pipeline.py -k personaje -v`; esperado FAIL.
- [ ] **Step 4:** Implementar. Mantener `_anclar_kits` funcionando: `anclar_personaje` sigue recibiendo un personaje, así que se aplica por hijo sobre las líneas de ese hijo, o se deja con el primer personaje solo para el reordenamiento visual (decisión: dejar el reordenamiento con el primero, documentado, porque no cambia qué producto se eligió). Actualizar los cuatro puntos de llamada en `trabajos.py` para usar `anclas_por_hijo`.
- [ ] **Step 5:** Tests de `test_fastroute.py` (`CatalogoRealista`) deben seguir en verde; añadir `test_un_hijo_cuatro_anclas_estables` (dos corridas idénticas devuelven los mismos 4 skus) y `test_ancla_no_surtida_se_registra` (caplog contiene el concepto).
- [ ] **Step 6:** `pytest servicios/inteligencia/tests/test_dominio_pipeline.py test_fastroute.py test_optimizador.py test_api_inteligencia.py -q`; esperado todo PASS.
- [ ] **Step 7: Commit** `fix(inteligencia): swap de personaje por hijo y anclas deterministas`.

### Task 6: El apodo llega al kit

**Files:**
- Modify: `apps/web/src/app/empezar/FormularioEmpezar.tsx` (`HijoSolicitud` ~L790 y el armado del cuerpo ~L605-700), `servicios/inteligencia/tukit_inteligencia/routers/inteligencia.py` (modelo de hijo ~L197), `apps/web/src/lib/kit-vista.ts:28-45`
- Test: `apps/web/src/lib/kit-vista.test.ts` (el existente o uno junto al módulo), `servicios/inteligencia/tests/test_api_inteligencia.py`

**Interfaces:**
- Produces: `HijoDelTrabajo` gana `apodo?: string`; `etiquetasDeHijos(referencias, hijosDelTrabajo, matriculas)` usa primero `hijo.apodo` (si existe y no vacío) y solo cae a las matrículas cuando no hay; sin cambio de firma. Backend: el hijo del trabajo guarda y devuelve `apodo: str | None` en `GET /v1/trabajos/{id}`.

- [ ] **Step 1: Test que falla** (TS): `dos hijos mismo colegio y grado con apodos distintos` espera `Map { "hijo-0" => "Sofía", "hijo-1" => "Lucía" }`; `un solo apodo en matrículas ya no se aplica a ambos hermanos`.
- [ ] **Step 2:** Correr el test de la web (comando del `package.json` de `apps/web`); esperado FAIL.
- [ ] **Step 3:** Enviar `apodo` en cada hijo del cuerpo de la solicitud; aceptarlo y devolverlo en el router de inteligencia (campo opcional, `extra` según el patrón del modelo existente, longitud máx. 40); `etiquetasDeHijos` prioriza `hijo.apodo`.
- [ ] **Step 4:** Test del router: crear trabajo con dos hijos con apodo y comprobar que el `GET` los devuelve. PASS en ambos.
- [ ] **Step 5: Commit** `fix(web): el apodo de cada hijo viaja hasta el kit`.

### Task 7: Explicar "lo que juntamos entre tus hijos"

**Files:**
- Modify: `apps/web/src/app/kits/[trabajo_id]/VistaKits.tsx:~235` (y su CSS module)
- Test: sin test (UI/copy); verificación manual.

**Interfaces:**
- Consumes: `kit.consolidaciones` y `nombresHijos` ya existentes; Task 6 da los apodos correctos.

- [ ] **Step 1:** Cada grupo muestra: producto, cantidad total, "para {apodo1} y {apodo2}", y el ahorro frente a comprar por separado, con texto en lenguaje del padre (nada de "consolidación" ni "concepto"). Pasar por `impeccable`/`design-taste-frontend`.
- [ ] **Step 2:** Verificar con `make reanudar` y un trabajo de dos hijos con personajes distintos (flujo real, 4 paneles de cola): cada hijo ve su apodo y su personaje, y solo se juntan productos idénticos.
- [ ] **Step 3: Commit** `feat(web): explica que se junta entre hermanos y por que`.

---

## Self-review

- Cobertura: Fase 1 (auditoría Task 1, relleno Task 2, Firecrawl Task 3); Fase 2 (determinismo Task 4, personaje por hijo Task 5, apodo Task 6, visual Task 7). El re-sembrado de kits (spec Fase 1.4) queda dentro de Task 3 Step 5 y la verificación de Task 7; no hay tarea de seeds falsos a propósito.
- Riesgo abierto: la correspondencia de claves de hijo (Task 5 Step 1) se resuelve leyendo código antes de implementar; si no casan, el plan lo contempla.
- Fases 3 a 5 requieren su propio plan; la Fase 3 (anclas por categoría) debe ir antes de la Fase 5.
