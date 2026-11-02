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

## Límites

- **Textos del plan lector (C134, 75 líneas):** el tipo `texto` no está en `BUSCA_EN_CATALOGO`, así que cargar ediciones
  reales no cambia su estado. Hace falta decidir si se reclasifican como `libro_libre` (código de inteligencia, no mío).
- **Sin producto real encontrado:** cuaderno de 3 materias cuadriculado grande (Éxito solo lo tiene sin stock; Panamericana
  no lo vende) y bitácora o sketchbook octavo argollada. Siguen como hueco y no se inventó ningún dato.
- **614 productos sin descripción:** la ficha de la tienda era publicitaria o no tenía texto.
- **Pendientes del lote N2:** 34 productos sin marca, 9 duplicados por nombre, `unidades_por_empaque` en 1 para todos.
- **Tests:** `test_la_puntuacion_de_calidad_se_deriva_del_nivel` y `test_todo_precio_es_entero_de_centavos_y_esta_en_rango`
  fallan desde el volcar base (3 precios de zamux fuera de rango y puntaje 0.4 frente a 0.7), no por estos cambios.
- `make bd-deriva` reporta diferencias de esquema ajenas a este trabajo.
