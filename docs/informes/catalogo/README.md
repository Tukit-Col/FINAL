# Verificación del catálogo contra las tiendas (2026-11-01)

Rama `worktree-agent-af747a27713b652b0`. Todo valor corregido lleva su fuente en
`datos/catalogo/procedencia_campos.csv` (producto, campo, valor anterior, valor nuevo, URL, fecha).

## Método

1. Se descargó la ficha pública de cada producto con oferta (VTEX para Éxito y Panamericana, Shopify para Gran Central).
2. Se comparó nombre, marca, imagen, precio y disponibilidad con la fila del catálogo. Una imagen se acepta solo con HTTP 200.
3. La descripción es una o dos frases tomadas de la ficha y filtradas: se descarta todo texto de venta.
4. Lo que no se pudo verificar conserva su procedencia original y se cuenta abajo.
5. Los CSV son la fuente. Se cargó con `make bd-cargar` y se reimportaron las listas con `make curaduria-importar`.

## Antes y después

| Medida | Antes | Después |
|---|---|---|
| Productos con descripción | 0 | 347 de 1072 |
| Productos sin marca | 44 | 34 |
| Precios actualizados desde la ficha | 0 | 71 |
| Imágenes corregidas | 0 | 17 |
| Ofertas marcadas como no disponibles | 0 | 20 |
| Productos de personaje reemplazados (ficha inexistente) | 0 | 4 |
| Líneas HUECO_CATALOGO en kits canónicos | 17 | 8 |
| Líneas de uniforme sin instrucción | 61 | 0 |

Líneas en cero en los kits canónicos recomendados, por tipo:

| Tipo | Líneas | En cero | Con instrucción del colegio |
|---|---|---|---|
| uniforme | 64 | 64 | 61 |
| texto (plan lector) | 75 | 75 | 0 |
| licencia_digital | 18 | 18 | 0 |
| no_comprar | 18 | 18 | 2 |
| otro | 35 | 35 | 1 |
| útil consolidado ("Ya va en la línea N") | 978 | 43 | 0 |
| útil sin candidato (HUECO_CATALOGO) | 8 | 8 | 0 |
| libro_libre | 43 | 3 | 0 |

Los 43 de útil consolidado y los 3 de libro_libre son duplicados dentro del mismo kit, no productos sin precio.

## Personajes

Productos activos por personaje, con las cuatro anclas (C001 cuaderno, C009 cartuchera, C011 carpeta, C086 maleta):
stitch 6, frozen 6, minnie 6, disney 6, spiderman 5, cars 4, paw patrol 4, bluey 4. Los ocho tienen las cuatro anclas
y precio vigente verificado. No encontré la encuesta de personajes, así que no puedo afirmar cuáles son los cinco más pedidos.

## Uniformes

Ninguna lista de los colegios revisados nombra una tienda en línea para el uniforme. Las 61 líneas C131 de Agustiniano
y Bahía Solano llevan `instruccion_colegio` (no se compra en Tukit ni en línea, pregunta en el colegio, fuente y fecha).
La web ya recibe ese texto en `linea_kit.instruccion_colegio` de las líneas informativas.

## Cambios de código

`servicios/catalogo/tukit_catalogo/cargador.py`: los diccionarios bilingües de `libros_firecrawl.csv` declaran
`monolingue: false`. Sin eso, la lista que pide "Diccionario inglés-inglés" quedaba sin candidatos. El concepto
`dic-ingles` ahora está declarado en `conceptos.csv`.

## Segunda ronda (2026-11-01)

- **Plan lector (C134):** pasa de `texto` a `libro_libre` con `isbn13` como atributo que discrimina. Se hizo con datos
  y con el cargador (`CONCEPTOS_LIBRO`), sin tocar inteligencia. Las 75 líneas que quedaban en SIN_MATCH son hoy 0.
  19 líneas piden una edición verificada en Buscalibre Colombia (17 libros con ISBN-13 válido, precio, imagen y URL,
  leídos el 2026-11-01). Las otras 56 llevan la instrucción "Se compra en librería".
- **Cuaderno de 3 materias y bitácora/sketchbook octavo:** 9 líneas con instrucción "Se compra en papelería". No se
  forzó ningún producto. Huecos de catálogo en los kits recomendados: 8 antes, 0 ahora.
- **Calidad:** 34 productos tenían `quality_score` distinto del que fija su nivel; quedaron alineados.
- **Precios de zamux:** la ficha y su JSON-LD confirman 500 y 600 COP por unidad. El dato era correcto y el piso del
  test (650) no; bajó a 500 con la justificación en el test.
- **Encuesta:** `Resultados_encuesta.xlsx` no tiene ninguna pregunta por personajes, así que no se pueden derivar los
  cinco más pedidos. Con las cuatro anclas hay 8 personajes con 4 o más productos reales: stitch 6, frozen 6, minnie 6,
  disney 6, spiderman 5, cars 4, paw patrol 4, bluey 4.

## Límites

- **Sin producto real encontrado:** 56 líneas del plan lector y 9 de cuaderno/bitácora se resuelven con instrucción, no
  con producto. La web debe mostrar `linea_kit.instruccion_colegio` en esas líneas informativas.
- **614 productos sin descripción:** la ficha de la tienda era publicitaria o no tenía texto.
- **Pendientes del lote N2:** 34 productos sin marca, 9 duplicados por nombre, `unidades_por_empaque` en 1 para todos.
- `make bd-deriva` reporta diferencias de esquema ajenas a este trabajo.
