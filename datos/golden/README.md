# Dorados OCR/RAG

Datos de prueba de la fase 4 de QA (NFR-PRE-01…05 y NFR-COS-01 de `Tukit-QA/trazabilidad/matriz-nfr.md`).
No son datos de producto: ningún servicio los lee en ejecución.

## Qué mide un dorado

No mide al modelo, porque para eso habría que llamarlo y estas pruebas no gastan un peso. Mide **al sistema
dada una respuesta del modelo**. La respuesta queda grabada en `fixtures-modelo/` y las pruebas la sirven en
lugar de Gemini. La buscan por el sha256 de la página que llega a `leer`.

## Qué hay

| Ruta | Qué es |
|---|---|
| `listas/` | Una entrada por variante de formato. Todas piden lo mismo: cambia la apariencia, el grado escrito y lo que el modelo alcanza a ver |
| `fixtures-modelo/Gnn-p1.json` | La respuesta HTTP que daría el proveedor para esa página, con el formato de `Tukit-QA/trazabilidad/acuerdos.md` §1.2 |
| `fixtures-modelo/indice.json` | `{sha256_pagina: ruta}`. Es lo que consulta el `leer` falso |
| `esperado/Gnn.json` | Lo que el sistema tiene que devolver, fila por fila: la salida de `percibir` y, por renglón, el parseo y el emparejamiento |
| `esperado/oracle.json` | Pares texto → concepto para el emparejamiento, con su nivel (`exacto`, `facil`, `dificil`, `hueco`, `informativo`) |
| `construir.py` | El script que genera todo lo anterior |

| Variante | Entrada | Qué cambia | Qué se espera |
|---|---|---|---|
| G01 | PNG, tabla limpia | — | Aceptada, renglones exactos |
| G02 | PDF de 41 páginas | Pasa el tope de 40 (`percepcion.TOPE_PAGINAS`) | `archivo_demasiado_largo` sin llamar al modelo |
| G03 | JPG, foto girada, borrosa y con grano | Grado «3°» | Aceptada |
| G04 | `.docx` | No es imagen ni PDF: el proveedor responde 400 | `percepcion_fallida` |
| G05 | JPG, manuscrito en hoja rayada | Grado «Grado tercero»; cuatro renglones con confianza 0,41…0,55 | Aceptada; esos renglones son la entrada de NFR-PRE-05 |
| G06 | PNG sin columna de cantidad | El número va dentro del texto; `cantidad` nula | El parseo saca la cantidad del texto |
| G07 | PNG con una descripción partida en dos renglones | El modelo deja un renglón en blanco | El renglón en blanco se descarta |
| G08 | PNG cortado | `completa: false`, solo los 9 primeros renglones | `pagina_incompleta` |
| G09 | PNG en mayúsculas y con tildes | Grado «TERCERO» | Aceptada, mismos conceptos |
| G10 | PNG con varios grados | Cuarto, 4°, Pre-Jardín y 3 A | `lista_de_varios_grados` con Cuarto, Prejardin y Tercero |

La lista base tiene 18 renglones:

- 12 que el catálogo surte;
- 3 huecos: un concepto que no existe, uno sin productos y uno con un atributo que ningún producto declara;
- 3 informativos: una licencia digital, un uniforme y uno «disponible en casa».

### Recalibración del oráculo (re-base a `d4ea7cb`)

`oracle.json` se mide contra el `datos/catalogo/` de hoy, y el catálogo de `44309fa` cambió tres renglones.
`construir.RECALIBRADO_CATALOGO` los recalibra solo en el oráculo:

- «Compás de precisión» deja de ser un hueco: el compás de precisión ya declara `tipo=precision`, así que se
  reconoce como C018 (nivel `facil`). El hueco por atributo ya no tiene caso en la lista base.
- «Plataforma de inglés…» se reconoce como C133 (Plan lector virtual) y «Uniforme de educación física» como
  C131 (Uniforme). Ninguno tiene producto, y los dos siguen siendo informativos.

`esperado/Gnn.json` no cambia, porque es la respuesta grabada que sirven las pruebas de inteligencia.

Las entradas son imágenes porque el stack no lee PDF sin el extra `pdf` de inteligencia (H-A-36 de QA). El
único PDF es G02, y su caso es justamente el tope de páginas.

## Datos ficticios

El colegio no existe, y ninguna lista lleva el nombre de un estudiante.

## Cómo se regenera

```bash
.venv/bin/python datos/golden/construir.py              # escribe todo
.venv/bin/python datos/golden/construir.py --comprobar  # no escribe: falla si algo difiere de lo versionado
```

Hace falta Pillow, que está en el entorno de desarrollo. Las imágenes usan la primera fuente de
`construir.FUENTES` que exista en la máquina; cada fixture anota cuál salió en `render`. Con la misma versión de
Pillow y la misma fuente, los bytes no cambian. En otra máquina pueden cambiar los sha256: se vuelve a correr el
script, que reescribe las listas, los fixtures y el índice juntos. El contenido de `esperado/` no depende de los
bytes.

## Quién los usa

- `servicios/inteligencia/tests/test_golden_percepcion.py`, `test_golden_parseo.py` y `test_golden_kits.py`.
- `servicios/catalogo/tests/test_golden_oro.py`.
- `ensayos/e2e/`, contra el stack vivo, con un inteligencia que sirve estos fixtures en lugar de Gemini.
