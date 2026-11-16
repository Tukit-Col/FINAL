# Muestra ciega del colegio nuevo (Agustiniano Norte)

- `muestra.csv`: 200 renglones leidos por el modelo de lectura, estratificados por grado (cuota proporcional a los
  renglones unicos de cada grado, minimo 1), semilla 20261115, orden barajado. Columnas: `id, colegio, grado, texto_original`.
  No trae concepto del sistema, puntaje ni estado.
- `conceptos.csv` e `instrucciones_anotador.md`: copias de `../muestra_ciega/`.
- `anotador_A_llm.csv` y `anotador_B_llm.csv`: vacios, solo con los ids.

## Las anotaciones seran de LLM
Ambos anotadores son LLM, no personas. Todo acuerdo o desacuerdo que se calcule con estos archivos es acuerdo entre
LLM y se debe presentar asi.

## Error de lectura (40 renglones revisados contra el PDF con pdftotext)
Se revisaron 40 renglones (1 de cada 5 del orden de la muestra). 2 de 40 (5 %) traen un error de lectura evidente:
N011 ("Vinilos fluorescente" es un fragmento mal cortado de la frase del PDF) y N111 (se perdieron letras:
"Andrs Felipe Pelez" por "Andres Felipe Pelaez"). Un tercero (N016) tiene un "by" que no aparece en el texto del PDF
(dudoso). Rango: 5 % a 7,5 %. Aparte, el modelo de lectura quita tildes y cambia la enie por n ("tamano", "acrilicos",
"educacion"): lo vimos en 8 de los 40 y se trata como normalizacion, no como error de contenido. La muestra es de 40 y el
intervalo es ancho. Los errores de resolucion de la muestra deben separarse de estos antes de contarlos.
