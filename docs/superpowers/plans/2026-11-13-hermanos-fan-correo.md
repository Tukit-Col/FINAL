# Hermanos: kit Fan por hijo, variedad sin personajes ajenos, consolidación clara y correo con todos los grados

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un hogar con dos o más hijos vea, para cada hijo, su personaje en todos los útiles donde el catálogo lo surte y la lista lo permite, que el chat de variedad no meta personajes ajenos, que "Lo que juntamos" explique por qué, y que el correo nombre todas las listas.

**Architecture:** Cuatro arreglos independientes en el pipeline de Inteligencia (anclas por hijo con varias variantes), NL2C (`elegir_variante`), la web (`VistaKits`, `kit-vista.ts`, `linea.ts` del contrato) y el aviso `kits_publicados` (Inteligencia → Operación). No hay endpoints nuevos ni migraciones. Solo se agrega un campo a la lectura del trabajo.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy (servicios), pytest; Next.js 16 + TypeScript (web), `node --test`.

**Spec:** este documento. Caso real: trabajo `febe34cf-3511-4ca7-b28e-cf11ca07d13d` (hijo-1 Séptimo · Spiderman, hijo-2 Jardín · Minnie, mismo colegio).

## Qué está pasando hoy (diagnóstico con datos del caso)

1. **Spiderman solo en 1 producto.** `RemotoCatalogo.producto_de_personaje` trae **un** producto por (concepto, personaje). El único cuaderno Spiderman (`TK-C001-CON-SPIDERMAN`) es `argollado · cuadriculado · materias: multiple`, y los 8 cuadernos de hijo-1 piden `materias: 1`. `puntaje_de_encaje` lo descarta en todos, con razón. La lista de Séptimo no pide carpeta (C011) ni maleta (C086), así que solo queda la cartuchera. Minnie tampoco entra a cuadernos: el único (`TK-C001-ECO-MINNIE`) es de 50 hojas rayado y hijo-2 pide 100 hojas. Al padre nadie le explica nada de esto.
2. **El chat "más variedad" mete Bluey, Stitch, Toy Story y Disney.** `nl2c_lote.elegir_variante` prefiere "un personaje que todavía no se use". En un kit Fan, eso trae franquicias que ningún hijo pidió. La franja (`productosDelPersonaje`) cuenta cualquier línea con `personaje`, así que esas líneas suben a "Tu kit con personajes" (4 → 8). Algunas opciones no tienen `imagen_url`.
3. **"Lo que juntamos" no dice por qué.** La consolidación ya trae `explicacion` ("Un empaque de 50 sale más barato que 2 por separado"), pero `VistaKits` no la muestra. Tampoco dice qué hijo usa cuántas.
4. **El correo solo nombra el primer hijo.** `RepoTrabajos.emitir_evento` pone en la carga solo `hijos[0].colegio_id/grado`.
5. **El texto está en singular.** Dice "el personaje que pidió tu hijo" aunque haya dos hijos con dos personajes.

## Global Constraints
- Ley 1581: ni el apodo ni el nombre del menor viajan en eventos, correos ni vistas de admin. En la web del padre se usa "Hijo N" o el apodo que el padre dio (ya existe `nombresHijos`).
- NSGA-II sigue siendo obligatorio y los totales del Fan se recomputan con `consolidar` (`dominio/pipeline.inyectar_personaje_fan`). No se cambia la aritmética de unidades.
- El asistente solo propone. El padre aplica.
- Un producto de personaje nunca entra en un renglón cuyo atributo exigido contradice (`puntaje_de_encaje is None`). Antes que inventar encaje, se avisa al padre.
- Tests: solo los de lo que cambia. Commits como MapaRuiz, sin atribución de IA.

## Review Focus
1. **Mismo personaje para los dos hijos** (los dos Spiderman): tienen que seguir consolidándose en una sola compra cuando el sku coincide (`consolidar`). Test en Task 1.
2. **Hijo sin personaje junto a hermano con personaje**: el hijo neutral no recibe nada de personaje y la franja no lo nombra. Test en Task 1 y Task 3.
3. **Variedad en un kit que no es Fan**: en Ahorrador o Premium no hay personaje pedido, así que la regla nueva no debe dejar el lote vacío. Se sigue eligiendo una opción neutra. Test en Task 2.
4. **Hogar con dos colegios distintos**: el correo dice "Colegio A, grado Séptimo y Colegio B, grado Jardín", sin repetir ni truncar. Test en Task 4.
5. **Un evento viejo en la bandeja, con solo `colegio_id`/`grado` y sin `listas`**: el correo tiene que salir igual que hoy. Test en Task 4.

---

### Task 1: Anclas de personaje por hijo con varias variantes, y aviso de lo que no cupo

**Files:**
- Modify: `servicios/inteligencia/tukit_inteligencia/remoto.py` (`RemotoCatalogo.producto_de_personaje` ~L182)
- Modify: `servicios/inteligencia/tukit_inteligencia/trabajos.py` (`anclas_por_hijo` ~L2707, `_anclas_de_personaje`)
- Modify: `servicios/inteligencia/tukit_inteligencia/dominio/pipeline.py` (`inyectar_personaje_fan`, `_lineas_con_swap`, `_candidato_de_swap`)
- Modify: `servicios/inteligencia/tukit_inteligencia/optimizador.py` (`renglones_con_personaje` ~L1336)
- Test: `servicios/inteligencia/tests/test_dominio_pipeline.py`, `servicios/inteligencia/tests/test_trabajos.py`

**Interfaces:**
- Produces: `RemotoCatalogo.productos_de_personaje(concepto: str, personaje: str, *, limite: int = 8) -> list[dict]`. Son los productos activos de ese concepto y personaje, ordenados por precio y luego por sku. `producto_de_personaje` queda como envoltorio que toma el primero, para no romper a quien ya lo llama.
- Produces: `anclas_por_hijo(...) -> dict[str, dict[str, list[dict]]]`, ahora con **lista** de variantes por concepto. `_anclas_de_personaje` devuelve `dict[str, list[dict]]`.
- Produces: `renglones_con_personaje(renglones, variantes: list[dict[str, Any]]) -> dict[Any, int]`. Devuelve `{clave_renglon: índice_de_variante}`. Por hijo elige el par (renglón, variante) de mayor `puntaje_de_encaje`. El desempate es primero el renglón del kit y luego la variante más barata. Se mantiene la regla de "surtido".
- Produces: en cada kit Fan, `personaje_sin_encaje: list[{"hijo": str, "concepto": str, "personaje": str}]`. Se guarda como parte de `consolidaciones`/metadatos del kit (sin migración: va dentro del JSON `objetivos` con la clave `personaje_sin_encaje`) y se expone en la lectura pública del kit como `kit.personaje_sin_encaje`. Lleva cada (hijo, concepto ancla) con renglones en la lista y variantes en el catálogo, pero sin ningún encaje.

- [ ] **Step 1: Write the failing tests** en `test_dominio_pipeline.py`:
  - `test_hermanos_cada_uno_su_personaje_con_variantes`: hijo-1 con dos variantes C001 Spiderman, `{materias: multiple, encuadernacion: argollado}` y `{materias: 1, encuadernacion: cosido, hojas: 100}`, y renglones de hijo-1 que piden `{materias: 1, encuadernacion: cosido, hojas: 100}`. Assert: un renglón de hijo-1 lleva la variante cosida, no la multimaterias. Hijo-2 con Minnie C009 recibe `TK-C009-...-MINNIE`. Ninguna línea de hijo-2 tiene Spiderman.
  - `test_mismo_personaje_dos_hijos_sigue_consolidando`: los dos con Spiderman C009 y el mismo sku. Assert: `consolidaciones` tiene el sku con `hijos == ["hijo-1","hijo-2"]`.
  - `test_hijo_sin_personaje_queda_neutral`: hijo-2 sin entrada. Assert: ninguna línea de hijo-2 tiene `personaje`.
  - `test_ancla_sin_encaje_queda_registrada`: el único Spiderman C001 contradice todos los renglones. Assert: `kit.objetivos["personaje_sin_encaje"] == [{"hijo": "hijo-1", "concepto": "C001", "personaje": "spiderman"}]`.
- [ ] **Step 2:** `.venv/bin/python -m pytest servicios/inteligencia/tests/test_dominio_pipeline.py -q -k "hermanos or personaje"`. Debe fallar.
- [ ] **Step 3: Implement.** `productos_de_personaje` usa el mismo endpoint de catálogo que hoy, con `por_pagina=limite`. `anclas_por_hijo` cachea por personaje la lista completa. `_lineas_con_swap` devuelve `{indice: variante}` y `producto_de` usa esa variante. `inyectar_personaje_fan` calcula `personaje_sin_encaje` al agrupar. Actualiza los llamadores de `_anclas_de_personaje`: `aplicar_canonico` y la vista `parent_apply` toman la variante 0 cuando el renglón es del canónico.
- [ ] **Step 4:** Corre el Step 2 y `servicios/inteligencia/tests/test_trabajos.py -q`. Todo debe pasar.
- [ ] **Step 5: Commit** `git commit -m "Fan por hijo: varias variantes de personaje por ancla y aviso de lo que no cupo"`

### Task 2: La variedad del chat no trae personajes que nadie pidió

**Files:**
- Modify: `servicios/inteligencia/tukit_inteligencia/nl2c_lote.py` (`elegir_variante` ~L280)
- Modify: `servicios/inteligencia/tukit_inteligencia/nl2c_kit.py` (`completar_variar` ~L414: pasar los personajes pedidos por hijo)
- Test: `servicios/inteligencia/tests/test_nl2c_lote.py`

**Interfaces:**
- Produces: `elegir_variante(linea, clave, opciones, usados_skus, usados_personajes, *, personajes_del_hijo: frozenset[str] = frozenset()) -> dict | None`. La regla nueva descarta toda opción con `personaje` que no esté en `personajes_del_hijo`. Entre las que quedan, ordena así: (1) sin repetir sku; (2) con `imagen_url`; (3) neutra o del personaje del hijo todavía no usada; (4) menor cambio de precio; (5) sku.
- Consumes: los personajes pedidos por hijo de `ContextoKit`. Si el contexto no los trae, se cargan de `preferencias.personaje_por_hijo` del trabajo, normalizados con `normalizar_personaje`.

- [ ] **Step 1: Tests:**
  - `test_variedad_fan_no_mete_otro_personaje`: opciones Bluey, Stitch y una neutra con foto, y `personajes_del_hijo={"spiderman"}`. Assert: elige la neutra.
  - `test_variedad_prefiere_con_foto`: dos neutras con el mismo precio, una sin `imagen_url`. Assert: elige la que tiene foto.
  - `test_variedad_sin_personaje_pedido_sigue_eligiendo`: kit Ahorrador, `personajes_del_hijo` vacío, una sola opción neutra. Assert: no devuelve None.
- [ ] **Step 2:** `.venv/bin/python -m pytest servicios/inteligencia/tests/test_nl2c_lote.py -q`. Debe fallar.
- [ ] **Step 3:** Implementa en `elegir_variante` y pasa `personajes_del_hijo` desde `completar_variar`, según `linea["hijo"]`.
- [ ] **Step 4:** Repite el Step 2 más `servicios/inteligencia/tests/test_nl2c_adversarial.py -q`, sin regresiones (los 7 xfail se mantienen).
- [ ] **Step 5: Commit** `git commit -m "NL2C variedad: sin personajes ajenos y con foto primero"`

### Task 3: La web cuenta la historia por hijo (franja Fan y "Lo que juntamos")

**Files:**
- Modify: `libs/ts/tukit-contrato/src/linea.ts` (`productosDelPersonaje`, `personajesDelKit`)
- Modify: `libs/ts/tukit-contrato/src/contrato.ts` (tipo `Kit`: `personaje_sin_encaje?: {hijo: string; concepto: string; personaje: string}[]`; tipo del trabajo público: `personajes_por_hijo?: Record<string, string[]>`)
- Modify: `servicios/inteligencia/tukit_inteligencia/trabajos.py` (lectura pública del trabajo: exponer `personajes_por_hijo` desde las preferencias; solo nombres de franquicia, nunca el apodo)
- Modify: `apps/web/src/app/kits/[trabajo_id]/VistaKits.tsx` (`FranjaFan` ~L576 y la sección de consolidaciones ~L246)
- Modify: `apps/web/src/lib/kit-vista.ts` (`textoDeConsolidacion` ~L95)
- Test: `apps/web/test/kit-vista.test.ts`, `libs/ts/tukit-contrato/test/linea.test.ts`

**Interfaces:**
- Produces: `productosDelPersonaje(lineas, pedidos?: Record<string, string[]>): LineaKit[]`. Con `pedidos`, solo cuenta las líneas cuyo `personaje` normalizado está en los pedidos de **su** hijo.
- Produces: `personajesPorHijo(lineas, pedidos?) : {hijo: string; personaje: string; lineas: LineaKit[]}[]`.
- Produces: `textoDeConsolidacion(c & {explicacion?: string|null}, nombres, ahorro) -> {paraQuienes, cantidad, ahorro, porque: string|null}`. `porque` es `c.explicacion` tal cual.

- [ ] **Step 1: Tests:**
  - `linea.test.ts` › `productosDelPersonaje ignora personajes no pedidos`: líneas con Spiderman (hijo-1), Minnie (hijo-2) y Bluey (hijo-1), y `pedidos={"hijo-1":["spiderman"],"hijo-2":["minnie"]}`. Assert: 2 líneas y ninguna es Bluey.
  - `kit-vista.test.ts` › `consolidacion explica el porque`: `explicacion: "Un empaque de 50 sale mas barato que 2 por separado."`. Assert: `porque` es esa cadena.
- [ ] **Step 2:** `cd libs/ts/tukit-contrato && node --test` y `cd apps/web && node --test test/kit-vista.test.ts`. Deben fallar.
- [ ] **Step 3: Implement.**
  - **`FranjaFan` con 1 hijo:** recibe `pedidos` y `nombresHijos` y queda igual que hoy, con el texto "Tu kit de Spiderman".
  - **`FranjaFan` con 2 o más hijos:** una fila por hijo con su encabezado, por ejemplo "Hijo 1 · Spiderman · 1 producto". El texto general queda "N productos con los personajes que pidieron tus hijos".
  - **Anclas sin encaje:** si hay `personaje_sin_encaje` del hijo, va una nota bajo su fila con este texto exacto: "No encontramos {concepto legible} de {Personaje} que cumpla lo que pide la lista; dejamos uno sin personaje." El concepto legible sale del mapa C001→"cuaderno", C009→"cartuchera", C011→"carpeta", C086→"maleta".
  - **Sin foto:** la tarjeta muestra el icono de categoría que ya existe en la vista, no el texto "sin foto".
  - **Consolidación:** agrega una línea `porque` y el grado de cada hijo junto a su nombre si `nombresHijos` lo tiene, por ejemplo "Hijo 1 (Séptimo) y Hijo 2 (Jardín)".
- [ ] **Step 4:** Repite el Step 2. Corre `npx tsc --noEmit -p apps/web` y `npx eslint apps/web/src/app/kits`, que deben salir limpios. Después corre pytest de `test_trabajos.py -q -k publico` para verificar el campo nuevo.
- [ ] **Step 5: Commit** `git commit -m "Kit: franja Fan por hijo, personajes no pedidos fuera y por que de lo que juntamos"`

### Task 4: El correo "Tu kit está listo" nombra todas las listas del hogar

**Files:**
- Modify: `servicios/inteligencia/tukit_inteligencia/repositorios/trabajos.py` (`emitir_evento` ~L203)
- Modify: `servicios/operacion/tukit_operacion/repartidor.py` (~L158: resolver el nombre de cada `colegio_id` distinto)
- Modify: `servicios/operacion/tukit_operacion/dominio/reparto.py` (`lugar_de`, `datos_plantilla`)
- Modify: `servicios/operacion/tukit_operacion/notificador.py` (`_VISTAS["kits_publicados"]`: fila "Listas" con una línea por lista; texto "Armamos los kits de {lugar}")
- Test: `servicios/inteligencia/tests/test_trabajos.py`, `servicios/operacion/tests/test_correo_kit_listo.py`, `servicios/operacion/tests/test_dominio_reparto.py`

**Interfaces:**
- Produces: la carga de `kits_publicados` agrega `listas: [{"colegio_id": str, "grado": str}]`, deduplicada por par y en el orden de los hijos. Conserva `colegio_id`/`grado` del primer hijo por compatibilidad con eventos ya encolados.
- Produces: `lugares_de(listas: list[dict], nombres: dict[str, str|None]) -> str`. Agrupa por colegio, por ejemplo: "Colegio San Agustín, grados Séptimo y Jardín" o "Colegio A, grado 3 y Colegio B, grado 5". Si no hay listas, devuelve `lugar_de(...)` de hoy.
- Produces: `datos_plantilla(..., colegios: dict[str, str|None] | None = None)`. El repartidor pasa el mapa `{colegio_id: nombre}`, y `colegio_nombre` sigue aceptándose para la ruta vieja.

- [ ] **Step 1: Tests:**
  - `test_trabajos.py` › `test_evento_kits_publicados_lleva_todas_las_listas`: un trabajo con hijos (Séptimo y Jardín, mismo colegio). Assert: `carga["listas"] == [{"colegio_id": X, "grado": "Septimo"}, {"colegio_id": X, "grado": "Jardin"}]`, y no aparecen `referencia` ni `apodo`.
  - `test_dominio_reparto.py` › `test_lugares_de_mismo_colegio_dos_grados`: assert `"Colegio X, grados Septimo y Jardin"`.
  - `test_dominio_reparto.py` › `test_lugares_de_dos_colegios`.
  - `test_dominio_reparto.py` › `test_evento_viejo_sin_listas_sigue_igual`: la carga solo trae `colegio_id`/`grado`. Assert: el mismo `lugar` de hoy.
- [ ] **Step 2:** Corre pytest de los tres archivos. Debe fallar.
- [ ] **Step 3:** Implementa. El repartidor llama `identidad.nombre_colegio` una vez por `colegio_id` distinto.
- [ ] **Step 4:** Repite el Step 2. Después: `make reanudar`, un envío de prueba con `/tmp/enviar_plantillas.py` adaptado a `listas` a `crackmaps.mini@gmail.com`, y revisar que el render no muestre apodos.
- [ ] **Step 5: Commit** `git commit -m "Correo kit listo: todas las listas del hogar"`

---

## Verificación de punta a punta
- `make reanudar`, luego un hogar nuevo en `/empezar` con 2 hijos (Séptimo · Spiderman y Jardín · Minnie) y aprobar en `:3001/cola`.
- **Franja:** dos filas, Hijo 1 · Spiderman e Hijo 2 · Minnie. Hijo 1 lleva el aviso de cuaderno si el catálogo sigue sin un Spiderman de 1 materia.
- **Chat:** "más variedad en cuadernos" no propone Bluey, Stitch ni Toy Story y prefiere opciones con foto.
- **"Lo que juntamos":** muestra el porqué.
- **Correo:** dice "grados Séptimo y Jardín".
- **Dato de catálogo (no es código):** si se quiere Spiderman en cuadernos de 1 materia, hay que curar un `C001` Spiderman cosido de 100 hojas (`make bd-*` y procedencia). Queda listado como hueco en la nota de la franja, no se inventa.
