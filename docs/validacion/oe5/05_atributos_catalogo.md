# 05. Atributos del catálogo: completitud, organización y plan

Fecha: 2026-10-17. Fuente: `origin/main` (dfc4fd3) y `origin/feature/afinar-kits-agustiniano` (39 commits por delante, 0 por detrás: es un avance directo de main). Solo lectura (`git show`/`git grep`); CSV volcados a `/tmp/attr_audit/{main,afinar}/` y analizados con `python3 -I`. Etiquetas: **[V]** verificado en código o datos, **[S]** simulado con el extractor real de cada rama, **[P]** propuesto.

Contexto: el selector del acudiente solo es fiable si cada cuaderno real declara rayado, tamaño, hojas y encuadernación con un vocabulario único.

## 1. Modelo de atributos tal como está implementado

- **[V] Dos niveles por concepto.** `Concepto.atributos_discriminantes` filtra y `atributos_descriptivos` solo describe (`servicios/catalogo/tukit_catalogo/modelos/catalogo.py`). Un CHECK de Postgres y un `@validates` impiden que una clave esté en las dos. Se derivan midiendo la demanda de las listas (`demanda_atributos.py`).
- **[V] Atributos del producto:** columna `producto_canonico.atributos`, un JSON plano con una clave por atributo y valores escalares. Viaja por git en `datos/catalogo/productos_canonicos.csv`. Hay 30 claves distintas en main y 36 en afinar.
- **[V] Vocabulario:** no hay un archivo máquina-legible. Vive en tres sitios que pueden desincronizarse: (a) las tablas regex de `enriquecer.py` (`RAYADOS`, `TAMANOS`, `TAMANOS_RELATIVOS`, `ENCUADERNACIONES`, `COLORES`...), (b) la tabla de `docs/guias/GUIA_CONCEPTOS_Y_PRODUCTOS.md` §5.2, (c) `apps/admin/src/lib/vocabulario-conceptos.ts`, que solo sugiere nombres de clave, no valores.
- **[V] Cómo se llena un producto:** `enriquecer.extraer_atributos(nombre, requeridos)` lee el nombre con regex y solo devuelve las claves que el concepto declara. `atributos_de_ficha` mapea la ficha de tienda (`DE_LA_FICHA`: Tamaño, Tipo de línea, Número de hojas...), pero **no se persiste**: `descripcion` está vacía en el 100 % de los productos. La cola de aprobación (`descubrir.py`) y el editor del admin (`atributos-editor.ts`) son los otros dos caminos.
- **[V] Cómo se usa un renglón de lista:** `listas_revisadas.atributos` es solo una curaduría que manda sobre lo leído (`*` quita un atributo). Lo normal es que esté vacía, porque en el emparejamiento se llama `extraer_atributos(texto_original, discriminantes)` y el producto debe declarar el mismo valor (`consulta._cumple`). **Lo que el producto no declara no cumple** (ADR 0040): un atributo vacío es un hueco silencioso, no un aviso.
- **[V] Atributos de C001 Cuaderno:** discriminantes `hojas|rayado|materias|encuadernacion`, descriptivo `tamano`. Es decir, "grande" vs "pequeño" **no filtra** en main.
- **[V] Reglas del valor** (guía §5.1): minúsculas, sin tildes, un valor escalar, número como número, medidas `N unidad`, "ausente antes que inventado". Ningún test las exige sobre los CSV: `test_catalogo_curado.py` no verifica atributos y `test_enriquecer.py` prueba el extractor, no los datos.

## 2. Completitud medida

### 2.1 Global **[V]**

| Métrica | main | afinar |
|---|---:|---:|
| Productos activos | 666 (667) | 1.040 (1.050) |
| Conceptos activos | 145 | 145 |
| Productos con `atributos` = `{}` | 231 (35 %) | 202 (19 %) |
| Discriminantes declarados que el producto llena | 74,8 % (577/771) | 75,4 % (1.397/1.852) |
| Renglones de lista con `atributos` vacío | 1.205/1.205 (100 %) | 1.134/1.215 (93 %; 81 curados) |
| Renglones con `tipo_item=no_comprar` | 2 | 23 |
| Marcas distintas / tras normalizar mayúsculas | n/d | 248 / 220 (28 duplicadas: `Norma`/`NORMA`, `Primavera`/`PRIMAVERA`) |
| Productos sin marca | n/d | 44 |
| Personaje con mayúscula o tilde | 24 de 76 | 17 de 77 |

Los conceptos con más productos sin ningún atributo son C044 Libro (40/40 en main, 39/44 en afinar; es esperable porque el libro se identifica por ISBN), Carpeta (11/29 en afinar), Cartuchera (11/19), Resaltador (8/21) y Témpera (5/14).

### 2.2 C001 Cuaderno (demanda: 153 renglones en main, 149 en afinar) **[V]/[S]**

| Atributo | main (39 prod.) | afinar (69 prod.) |
|---|---:|---:|
| `hojas` (disc.) | 82 % | 89 % |
| `rayado` (disc.) | 97 % | 98 % |
| `materias` (disc.) | 100 % | 100 % |
| `encuadernacion` (disc.) | 97 % | 98 % |
| `tamano` (descriptivo) | **48 %** | **37 %** |
| Los cuatro que pide el selector (hojas, rayado, encuadernación, tamaño) | 15/39 (38 %) | 22/69 (32 %) |
| Representantes (los que ve el kit hoy) | 16 | 19 |

- **El hueco para el selector es `tamano`.** En afinar solo 11 cuadernos dicen `grande`, 7 `mediano`, 6 `pequeno`, 2 un formato de papel y 43 no dicen nada. Pero 100 de los 141 renglones comprables de C001 piden "grande". Una muestra de los nombres sin tamaño ("Cuaderno Cosido 100 Hojas Norma Cuadros") confirma que la tienda no lo escribe: el regex no lo puede sacar, hay que ir a la ficha.
- **`tamano` mezcla dos escalas** bajo una clave: formato de papel (`media carta`, `oficio`, `carta`) y relativo (`grande`/`mediano`/`pequeno`, solo pensado para morral y cartuchera).
- **Vocabulario de `rayado` en afinar:** `cuadriculado` 37, `rayado` 13, `ferrocarril` 11, `cuadriculado 1 cm` 3, `mixto` 2, `blanco` 1, `pentagramado` 1, vacío 1. Dos valores no están en la guía (`cuadriculado 1 cm`, `mixto`). El extractor unifica bien `cuadros`/`cuadricula`/`cuadriculada` a `cuadriculado` (reextraje los 69 nombres: solo 5 difieren y son curaduría deliberada). No encontré el problema "cuadricul vs cuadros" en los datos guardados.
- **`rayado=rayado` es ambiguo para el selector:** significa "una línea/renglón", y `ferrocarril` y `doble linea` se confunden. Afinar tiene un producto llamado "doble línea / ferrocarril" guardado como `ferrocarril`, y `doble linea` desapareció (main tenía uno).
- **`hojas`:** 100 → 32, 80 → 11, 50 → 9, 160 → 8, 40 y 150 → 1 cada uno, vacío → 7 (cuadernos de pasta dura con tema y libretas). El selector pide 50 y 100: hay 9 y 32 productos.
- **`materias`:** 59 con `1`, 9 con `5`, 1 con `multiple`. `multiple` y `5` no se pueden comparar entre sí.
- **Demanda por renglón en afinar (141 comprables):** `rayado` cuadriculado 124 y ferrocarril 9; `hojas` 100 → 99 y 50 → 31; encuadernación cosido 51, argollado 26 y sin decir 64; `tamano` grande 100 (el extractor no lo lee en C001 porque es descriptivo).
- **Renglones sin producto que cumpla (simulación con igualdad exacta):** 17/153 (11 %) en main y 11/149 (7 %) en afinar. La ruta real de afinar es más tolerante con `hojas` (ADR 0040), así que los de afinar están sobreestimados. Casos típicos: "cuadriculado 50 hojas argollado".

### 2.3 Los 15 conceptos más frecuentes en las listas **[S]**

Se excluyen C131 Uniforme y C133 Plan lector virtual (no se venden). C134 Libro (75-78 renglones) no tiene productos por diseño. Las columnas son el % de productos que llenan cada discriminante (`*`) y el % de renglones sin producto que cumpla (igualdad exacta).

| Concepto (renglones main/afinar) | Discriminantes: llenado afinar | Sin producto, main | Sin producto, afinar |
|---|---|---:|---:|
| C001 Cuaderno (153/149) | hojas 89, rayado 98, materias 100, encuad. 98 | 11 % | 7 % |
| C027 Pintura (56/36) | tipo 100, color 98 | 67 % | 0 % |
| C006 Marcador (37/37) | punta 88, tipo 74, color 68, unidades 71 | 35 % | 8 % |
| C010 Cartulina (36/36) | color 88, tamano 100, **acabado 25** | 2 % | 0 % |
| C003 Block (26/30) | tipo 100, tamano 93 (hojas desc. 56) | 42 % | 26 % |
| C004 Colores (24/24) | unidades 79, **forma 34**, grosor 100 | 0 % | 0 % |
| C002 Lápiz (23/21) | dureza 42, **forma 0**, color 92, grosor 100 | 30 % | 0 % |
| C013 Tijeras (23/23) | **punta 38**, longitud 61 | 0 % | 0 % |
| C024 Bata laboratorio (22/18) | color 60, material 60, manga 60 | 0 % | 0 % |
| C008 Regla (22/22) | longitud 92, material 85 | 22 % | 0 % |
| C011 Carpeta (20/n.d.) | main: tamano 0, tipo 8; afinar: color 34 | 95 % | n.d. |
| C015 Cinta adhesiva (19/n.d.) | tipo 100 | 0 % | n.d. |
| C034 Diccionario (18/28) | idioma 100 | 0 % | 10 % |
| C020 Vinilo (n.d./24) | presentación 100, color 100, **colores 0** | n.d. | 0 % |
| C021 Pincel (n.d./19) | **grosor 47, unidades 52**, forma 84 | n.d. | 26 % |

Peores discriminantes por demanda en afinar (n ≥ 5 productos, < 60 % llenos): Cartulina `acabado` 9/35, Vinilo `colores` 0/27 (declarado discriminante pero sin dato), Colores `forma` 10/29, Tijeras `punta` 5/13, Lápiz `forma` 0/14 y `dureza` 6/14, Pincel `unidades` 10/19 y `grosor` 9/19, Cartuchera `tamano` 0/19 (en afinar `forma` del lápiz y `colores` del vinilo nunca se llenan, así que declararlos discriminantes es un error de contrato; la guía §3.6 lo prohíbe).

### 2.4 Valores sospechosos y renglones con el problema de Agustiniano Tercero **[V]**

- **Líneas 9, 33, 40, 42 (y todas):** el `atributos` vacío **no es un hueco del renglón**; el emparejador lee `hojas/rayado/materias/encuadernacion` del texto en tiempo de ejecución. Lo que sí falta es que "grande" no se exige (C001 `tamano` es descriptivo). Afinar lo parchea con `_BLANDOS = {"C001": ("tamano",)}` en `routers/admin.py` (se exige solo si algún candidato lo declara), un parche fijo en código para un solo concepto.
- **Línea 70 "del año anterior":** `modo_adquisicion=mercado_abierto` es correcto por diseño (el 100 % de los 1.205/1.215 renglones lo tiene; el enum describe quién vende). La palanca real es `tipo_item=no_comprar` (guía §5.6). En main lo tienen 1 de 8 renglones "del año anterior" de C001 y 0 de 5 "disponible en casa" del diccionario; en afinar, 8/8 y 5/5. Quedan por revisar 2 renglones de C139 y 1 de C036 que coinciden con el patrón.
- **Valores fuera de formato:** main tiene `deposito: "True"` (texto); afinar tiene `edad: "8 a 10 años"` (tilde, 2 productos); `rayado` `cuadriculado 1 cm` (3) y `mixto` (2).

## 3. Diferencias main vs `feature/afinar-kits-agustiniano` **[V]**

| Área | main | afinar |
|---|---|---|
| Datos | 667 prod., 148 conc., 1.205 renglones | 1.050 prod. (+383), 149 conc., 1.215 renglones; ofertas 673 → 1.057 |
| C001 | 39 prod. | 69 prod.; añade ferrocarril cosido (11) y 5 materias (9) |
| Comparación | igualdad exacta (`str(v).lower()`) | ADR 0040: `hojas` ≥ pedido y ≤ 2×; `unidades/colores/piezas/gramaje` ≥ pedido; `longitud` ±; medidas `a x b cm` con 25 % estricto; `carta ≈ a4`; `idioma` bilingüe |
| Curaduría de renglón | solo CSV | editor "Atributos que se exigen" en el admin (`AtributosRenglon.tsx`), `*` = no exigir, backend rechaza claves no filtrables (`atributo_no_exigible`) |
| Empaque/personaje/atributos | la base manda | el CSV manda; el cargador no pisa un empaque > 1 |
| Vocabulario | tabla §5.2 | añade electrónica (valor, calibre, interruptor, motor), `grosor`, `doble punta`, §5.5 (cómo se compara) y §5.6 (curaduría de lista) |
| Medición | n/d | `ensayos/kits_offline.py` + 4 auditorías (`docs/informes/auditoria-huecos-agustiniano/`): v4 = 758 de 885 comprables cumplen (85,6 %), 69 huecos A, 55 "mal elegidos" |
| Tests nuevos | n/d | `test_afinamiento_kits.py`, `test_kits_offline.py`, `atributos-renglon*.test.ts` |
| Quitado | `docs/informes/reporte-huecos-catalogo.{md,json}` | reemplazado por las auditorías |

El 85,6 % de la auditoría v4 mide **kits del Agustiniano**, no completitud de atributos: el 75 % de discriminantes llenos de la tabla 2.1 es independiente de ese número. El pendiente de afinar mismo lo dice: "C001 no exige `tamano`", 23 renglones "cuaderno grande" salían con un cuaderno que no dice serlo.

Recomendación: **integrar afinar a main antes de normalizar** (es avance directo, sin divergencia), porque trae +383 productos, el comparador por atributo y el editor de curaduría, y cualquier trabajo sobre `productos_canonicos.csv` en main lo haría chocar.

## 4. Plan de reorganización y llenado **[P]**

### 4.1 Normalización del vocabulario (previa a llenar)

1. **Vocabulario como dato:** `datos/catalogo/vocabulario_atributos.csv` (clave, valor canónico, sinónimos, ámbito de concepto). Las tablas regex de `enriquecer.py` y la guía §5.2 se generan o validan contra ese archivo.
2. **Partir `tamano`** en `formato` (carta, oficio, media carta, a4, pliego...) y `tamano_relativo` (pequeno/mediano/grande), o fijar un mapa por concepto. Para C001, declararlo con una definición operativa ("grande" = formato carta/universitario, por ejemplo). Esa definición **la debe fijar una persona**.
3. **`rayado`:** fijar `rayado ∈ {cuadriculado, una_linea (hoy "rayado"), doble_linea, ferrocarril, blanco, pentagramado, milimetrado}`; `cuadriculado 1 cm` pasa a `cuadriculado` + `cuadricula=1 cm` (o se descarta); `mixto` se parte en dos atributos o se deja como curaduría. Renombrar `rayado` a `una_linea` solo si el selector lo necesita, porque la comparación del emparejador es textual.
4. **`materias`:** entero siempre (`multiple` pasa a un número o se deja vacío).
5. **Marca** a una forma canónica (`Norma`, `Primavera`), **personaje** en minúscula sin tilde, `deposito` booleano, `edad` sin tilde.

### 4.2 Qué extraer automáticamente

| Atributo | Método | Validación |
|---|---|---|
| `hojas`, `materias`, `encuadernacion`, `rayado`, `unidades`, `color`, `idioma`, `dureza` | **Regex ya existente** (`extraer_atributos`), reaplicado a nombres de productos vacíos | Reextraer todo el CSV y comparar con lo guardado. Hoy discrepan 5/69 en C001; cada discrepancia se lee a mano |
| `tamano` de cuaderno, `punta` de tijera, `forma` de lápiz/colores, `acabado` de cartulina, `grosor` de pincel, `dureza` | **Ficha de tienda** (`atributos_de_ficha`, mapa `DE_LA_FICHA`) guardada en un campo nuevo `ficha_json`, o en `productos_procedencia`. Sin necesidad de LLM | Solo valores que están en el vocabulario; si no, a la cola de curaduría |
| Lo que no está ni en nombre ni en ficha (p. ej. "grande" de un Norma cosido de 100 hojas) | **LLM con foto + nombre + ficha** (extracción con salida cerrada: solo valores del vocabulario o `null`), tratado como *sugerencia* | Revisión humana del 100 % en C001 (69 filas) y de una muestra del 20 % en el resto; precisión objetivo ≥ 95 % antes de aceptar en bloque |
| Renglones "del año anterior", "disponible en casa", "misma bata" | **Regla regex** que propone `tipo_item=no_comprar` en la revisión de la lista | Se muestra como aviso, nunca se aplica sola |

Regla de oro (guía §5.1.7): un valor no resuelto se queda **vacío**, nunca inventado.

### 4.3 Qué requiere curaduría humana

- Definición operativa de "grande/mediano/pequeño" por concepto y qué marca/línea es cuál.
- Los 7 cuadernos sin `hojas` y los de pasta dura con tema (y decidir si son cuaderno o libreta).
- `tipo_item=no_comprar` de los renglones nuevos y de los 3 renglones sospechosos (C139/C036).
- Discriminantes mal declarados: pasar a descriptivo los que ningún producto llena (Vinilo `colores`, Lápiz `forma`) o llenarlos.
- Decidir si un producto sirve para el selector (foto, precio, oferta vigente) y si el representante es razonable.

### 4.4 Prioridad por impacto en cumplimiento de kits y esfuerzo estimado

| # | Trabajo | Impacto | Días |
|---|---|---|---:|
| 0 | Integrar afinar a main y rehacer esta medición como línea base | evita trabajo doble | 0,5 |
| 1 | C001 Cuaderno: `tamano` desde ficha, definición de tamaño, `hojas` faltantes, vocabulario `rayado`/`materias` (69 productos) | el selector; 100 de 141 renglones piden "grande" | 2 |
| 2 | Quitar el parche `_BLANDOS` y volver `tamano` discriminante de C001 una vez lleno | los 23 "cuaderno grande" mal elegidos | 0,5 |
| 3 | Vocabulario como dato + guardia de datos (4.5) | evita la regresión de todo lo demás | 1,5 |
| 4 | Persistir la ficha de tienda para los ~1.040 productos y reextraer | alimenta casi todo lo de abajo | 1,5 |
| 5 | Conceptos 2-15 de la tabla 2.3: llenar discriminantes < 60 % (Cartulina `acabado`, Tijeras `punta`, Pincel `grosor/unidades`, Marcador `color/tipo`, Lápiz `dureza`, Carpeta, Cartuchera `tamano`) | huecos falsos y "mal elegidos" | 3 |
| 6 | Normalizar marca/personaje/`edad`, y revisar el resto de claves | consistencia del selector y de la nivelación | 0,5 |
| 7 | Regla de `no_comprar` en la revisión de listas + curaduría de los renglones | no cobrar lo que el colegio no pide | 1 |
| 8 | Selector: facetas derivadas del catálogo (conteo por valor), con "sin dato" explícito | UI | según `04_diseno_personalizacion.md` |

Total ≈ 10,5 días de una persona, sin contar el selector. Mínimo viable para el selector de cuadernos: pasos 0, 1 y 3 (≈ 4 días).

### 4.5 Guardias para que no se pudra **[P]**

1. **Test de contrato de datos** (`servicios/catalogo/tests/test_atributos_datos.py`) sobre `datos/catalogo/*.csv`: toda clave de `atributos` está declarada por el concepto; todo valor de claves con vocabulario cerrado (`rayado`, `encuadernacion`, `tamano`, `color`, `idioma`, `materias`) pertenece al vocabulario; tipos (entero, booleano, medida `N unidad`); minúsculas y sin tildes; marca y personaje normalizados.
2. **Test de completitud con umbral que solo sube:** por concepto, ≥ X % de los discriminantes declarados llenos, con una línea base guardada (`metricas_atributos.json`, patrón de `metricas_catalogo.json`). El CI falla si baja.
3. **Test de coherencia nombre/atributos:** `extraer_atributos(nombre)` no contradice lo guardado salvo curaduría marcada (como hoy `cuadriculado 1 cm`).
4. **Guardia de la cola:** al aprobar un producto, el editor exige los discriminantes del concepto (o "sin dato" explícito) y normaliza marca y personaje (el fallo de mayúsculas del §5.4 de la guía viene de aquí).
5. **Aviso de renglón:** si el texto de una lista contiene un patrón de "ya lo tiene" y `tipo_item` está vacío, la revisión lo señala; `demanda_atributos.py` se re-corre al entrar un colegio nuevo para detectar discriminantes sin datos.
6. **Un solo origen:** que la guía §5.2, el editor TS y `enriquecer.py` lean el mismo `vocabulario_atributos.csv`, con un test que falle si divergen.

## 5. Limitaciones

- La simulación usa igualdad exacta en ambas ramas y no reproduce el filtro completo de afinar (tolerancias, "más de uno", `_BLANDOS`); sirve para comparar ramas y detectar atributos vacíos, no para medir el cumplimiento real (eso es la auditoría v4).
- Se analizaron solo 3 colegios (Bahía Solano, San Pedro, Agustiniano); el Agustiniano concentra casi todos los renglones.
- No leí los PDF originales ni abrí fichas de tienda: lo dicho sobre qué trae la ficha de cada producto es **[P]** hasta probarlo con 10 URLs de `ofertas_tienda.csv`.
