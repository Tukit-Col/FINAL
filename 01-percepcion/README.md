# 01 · Percepción: ¿qué motor lee mejor una lista de útiles?

## Pregunta

¿Qué enfoque extrae mejor los renglones (descripción, cantidad y tipo) de una lista de útiles escolares
en PDF, si se tienen en cuenta la calidad, la latencia, el costo y la privacidad?

## Alternativas

| Enfoque | Cómo funciona | Dónde corre | Páginas que lee |
|---|---|---|---|
| OCR tipográfico + Tesseract | PyMuPDF (texto incrustado) o Tesseract, y luego reglas regex | local | todas |
| Google Cloud Vision | `document_text_detection`, y luego las mismas reglas regex | nube | las 5 primeras |
| Baidu GOT-OCR2.0 (*format*) | modelo fundacional de OCR en GPU CUDA, y luego regex | local (GPU) | las 5 primeras |
| Docling (IBM / LF AI) | análisis de *layout* a Markdown, y luego regex | local | todas |
| Gemini 3.5 Flash-Lite (LMM) | imágenes de página a JSON estructurado, sin regex | nube | las 5 primeras |

El límite de 5 páginas lo pone `pdf_a_imagenes_base64(max_paginas=5)`, que usan Vision, Baidu y Gemini.

## Datos

El **CGS-10** son 10 listas reales de colegios de Teusaquillo y Fontibón. Suman 1.293 ítems *gold* y
entre 2 y 39 páginas por documento. Las predicciones guardadas de cada enfoque están en
[`datos/resultados_benchmark_10.json.gz`](datos/resultados_benchmark_10.json.gz). Las páginas de cada documento
están en [`datos/paginas_por_documento.json`](datos/paginas_por_documento.json).

## Métrica

Precisión, *recall* y F1, en sus versiones micro (por ítem) y macro (por documento). Un ítem predicho
empareja con uno del *gold* si coinciden tras normalizar el texto o, si no, si su `SequenceMatcher` es
mayor o igual a 0,75. Se mide además la latencia por documento y el costo en USD.

## Resultados

Las cifras se recalcularon desde las predicciones crudas con la misma función de emparejamiento
(`06_comparar_enfoques.calcular_prf1`): **P, R y F1 se reproducen exactamente**. Las columnas de
latencia y de costo de Vision están corregidas; ver [CORRECCIONES](../CORRECCIONES.md#01-percepción).

| Enfoque | P (micro) | R (micro) | F1 (micro) | F1 (macro) | Latencia mediana (s) | Costo por documento (USD) | Privacidad |
|---|---:|---:|---:|---:|---:|---:|---|
| OCR tipográfico + Tesseract | 0,180 | 0,861 | 0,298 | 0,419 | 0,18 | 0 | local |
| Google Cloud Vision | 0,561 | 0,842 | 0,673 | 0,672 | 6,33 | 0,0069 | nube |
| Baidu GOT-OCR2.0 | 0,559 | 0,640 | 0,597 | 0,569 | 213,0 | 0 (GPU) | local |
| Docling | 0,241 | 0,739 | 0,364 | 0,424 | 24,4 | 0 | local |
| **Gemini 3.5 Flash-Lite** | **0,966** | **0,930** | **0,948** | **0,944** | 312,5 | 0,0017 | nube |

**Subconjunto justo.** En los documentos de 5 páginas o menos (2 documentos, 232 ítems), todos los
enfoques leen el documento completo:

| Enfoque | P | R | F1 |
|---|---:|---:|---:|
| OCR tipográfico + Tesseract | 0,689 | 0,871 | 0,770 |
| Google Cloud Vision | 0,701 | 0,901 | 0,789 |
| Baidu GOT-OCR2.0 | 0,650 | 0,746 | 0,695 |
| Docling | 0,677 | 0,858 | 0,757 |
| Gemini 3.5 Flash-Lite | 0,987 | 0,987 | 0,987 |

**Qué tan literal es el *gold* frente a cada predicción** (fracción de los ítems *gold* cuyo texto
normalizado aparece tal cual entre las predicciones): Gemini 92,8 %, OCR 71,5 %, Vision 70,8 %,
Baidu 50,1 %, Docling 48,9 %.

**Acuerdo entre anotadores** (corpus 2026, clasificador frente al LLM como segundo anotador): el
κ de Cohen global es 0,733 con n = 200. Se reproduce con `14_calcular_kappa.py`.

## Conclusión

Gemini gana con claridad, también en el subconjunto justo (F1 de 0,99 contra 0,70–0,79). Es el enfoque
que adoptó el sistema. Hay tres matices para la tesis:

1. Los F1 de OCR (0,30) y de Docling (0,36) **exageran la diferencia**. Esos dos enfoques leen todas las
   páginas, y el *gold* cubre en la práctica solo las primeras. Por eso, en el documento de 27 páginas,
   OCR predice 1.232 ítems y Docling 747, contra 173 del *gold*. En documentos cortos quedan en F1 de 0,76 a 0,77.
2. El *gold* se construyó **editando una de las extracciones** (`test_alternatives_app.py`, botón «Elegir esta
   extracción»), y el 92,8 % de sus ítems es texto idéntico al de Gemini. Eso favorece a Gemini. Para
   publicar el margen exacto hace falta un *gold* anotado de forma independiente.
3. La latencia de Gemini (de 54 a 806 s por documento) la domina la espera por la cuota gratuita
   de la API, no el modelo.

## Reproducir

```bash
python scripts/verificar_percepcion.py   # -> resultados/verificacion_percepcion.json
```

Los benchmarks originales (`scripts/05_bench_*.py` y `07_run_full_benchmark.py`) necesitan los PDF,
que no están versionados, una GPU con CUDA (Baidu) y claves de Google Cloud y Gemini. No se
re-ejecutaron.

## Procedencia

- `Tukit-Col/Tukit-Poc-Tesis@534c973` (main): `poc_01_percepcion/scripts/05_bench_*.py`, `06_comparar_enfoques.py`,
  `07_run_full_benchmark.py`, `08_generar_tabla_latex.py`, `14_calcular_kappa.py`,
  `corpus/resultados_benchmark_10.json`, `corpus/gold_standard_construido.json` (CGS-10),
  `corpus/predicciones_llm_2026.json` y `documento_maestro/seccion_percepcion.tex` (la tabla publicada).
- Copiados aquí: los scripts en [`scripts/`](scripts/) y los datos en [`datos/`](datos/) (comprimidos).
  El *gold* se incluye en su versión anonimizada (`gold_standard_anon.json.gz`).
