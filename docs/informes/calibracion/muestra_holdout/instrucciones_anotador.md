# Instrucciones para el anotador

Gracias por ayudar. Tu trabajo es decir, para cada renglón de una lista de útiles escolares, a qué concepto del catálogo corresponde. Tu respuesta se compara con la del sistema y con la de otra persona, y es la medida que usamos para saber qué tan bien funciona. No hay respuestas "esperadas": si dudas, responde lo que tú entiendes.

## Qué es cada cosa

- **Renglón**: una línea de la lista de un colegio, tal como la escribió el colegio. Ejemplo: `Cuadriculado de 50 hojas argollado`.
- **Concepto canónico**: el artículo "en abstracto" al que se refiere el renglón, sin marca, tamaño ni cantidad. El renglón anterior corresponde al concepto "Cuaderno" (o el que el catálogo llame así), no a un cuaderno de una marca.
- **Catálogo** (`conceptos.csv`): 146 conceptos con código (por ejemplo `C016`), nombre y de 3 a 5 sinónimos o ejemplos. Los ejemplos están escritos sin tildes y son solo una guía, no una lista cerrada.

## Cómo anotar

1. Abre `muestra.csv` (renglones) y tu hoja (`anotador_A.csv` o `anotador_B.csv`, según te hayan asignado). Puedes pegarlas en Google Sheets.
2. Para cada `id`, lee `texto_original`, busca el concepto en `conceptos.csv` (con Ctrl+F sobre nombre y ejemplos) y escribe **solo el código** en `concepto_codigo`.
3. Si ningún concepto describe el renglón (por ejemplo un libro específico, un uniforme, una lista de varias cosas sin concepto propio), escribe `NINGUNO`.
4. No dejes ninguna casilla vacía: o un código, o `NINGUNO`.

## Cuando hay duda

- Si el renglón nombra varias cosas, elige el artículo principal (el primero o el más claro) y anota la duda en `comentario`.
- Si dos conceptos parecen servir, elige el más específico y escribe el otro código en `comentario`.
- Si el renglón es ilegible o no lo entiendes, escribe `NINGUNO` y dilo en `comentario`.
- Ignora marca, color, tamaño y cantidad al decidir. Cuentan solo si el catálogo separa conceptos por eso.
- No inventes códigos nuevos.

## Reglas

- **No consultes el sistema** (ni la plataforma ni ningún archivo de resultados) **y no hables con la otra persona** sobre sus respuestas hasta que ambas terminen. Si alguien ve respuestas ajenas, el acuerdo deja de medir lo que queremos.
- Usa solo `muestra.csv`, `conceptos.csv` y tu criterio.

## Cuánto toma

240 renglones. Cuenta unos 20 a 25 segundos por renglón: **entre 80 y 100 minutos**, mejor en dos sesiones con una pausa. Al principio es más lento porque hay que conocer el catálogo. Al terminar, guarda tu hoja como CSV (UTF-8) y envíala a quien coordina.
