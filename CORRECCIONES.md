# Correcciones

Este archivo registra todo lo que **no se reprodujo** o estaba **mal calculado** al recalcular las
cifras desde los datos crudos. Las correcciones viven solo en este repositorio; los repositorios de
origen no se tocaron. Cada entrada dice qué es, por qué, con qué evidencia y el valor viejo frente
al nuevo.

Leyenda de severidad: **A**, cambia una cifra o una conclusión que la tesis cita; **M**, cambia una cifra
secundaria o la lectura de un resultado; **B**, es de redacción o de consistencia.

## Resumen

| # | Área | Severidad | Qué | Antes | Después |
|---|---|:---:|---|---|---|
| 1 | Percepción | M | Latencia «p50» (se tomaba el 6.º de 10 valores) | Gemini 342,20 s; Docling 28,87; Baidu 216,94; Vision 6,38; OCR 0,20 | 312,46; 24,43; 213,04; 6,33; 0,18 |
| 2 | Percepción | M | Costo de Vision fijo por documento (lee hasta 5 páginas) | 0,0015 USD/doc (0,015 en total) | 0,0069 USD/doc (0,069 en total) |
| 3 | Percepción | B | Nombre del modelo en la tabla | «Gemini 3.5 Flash» | «Gemini 3.5 Flash-Lite» (el que se llamó) |
| 4 | Percepción | A | Ventana de páginas desigual y *gold* anclado en Gemini | F1 de OCR 0,298 y de Docling 0,364 | En documentos de ≤ 5 páginas: OCR 0,770, Docling 0,757 (Gemini 0,987); el 92,8 % del *gold* es texto idéntico al de Gemini |
| 5 | Umbral | B | Porcentaje de negativos | 52,4 % | 53,0 % (1.437/2.710) |
| 6 | Umbral | B | Renglones con al menos un SKU correcto, y SKUs correctos por renglón | 394; 3,29 | 392; 3,25 |
| 7 | Umbral | A | Barrido de δ y AUC del margen, calculados en el orden del RRF y no en el del *reranker* | δ de 0 a 0,05: precisión de 87,7 % a 89,0 %; AUC 0,713 | Precisión de 89,9 % a 86,0 % (baja); AUC 0,354 |
| 8 | Umbral / FINAL | M | AUC por canal en `05-resolucion.tex` | Denso 0,825; RRF 0,753; *reranker* 0,879 | 0,805; 0,739; 0,880 |
| 9 | Embeddings | B | «MRR@10» sin truncar en 10 | mpnet 0,8508; MiniLM-L12 0,8627; jina 0,9722 | 0,8477; 0,8621; 0,9713 |
| 10 | Embeddings | B | El README lista e5-small y e5-base como alternativas | e5-small/e5-base | Se evaluaron MiniLM-L12, mpnet y jina-v2-base-es |
| 11 | Almacén vectorial | M | Latencia de la búsqueda exacta citada en el texto | «~3 ms» | 0,46 ms (su propia tabla) |
| 12 | Almacén vectorial | A | Recall de IVF y HNSW medido solo con vectores aleatorios | IVF 0,211 (motivo para descartar ANN) | Con vectores reales: IVF 0,832, HNSW (ef = 40) 0,862 y (ef = 100) 0,952 |
| 13 | Almacén vectorial | A | Recall@10 de PoC-02 publicado frente al guardado | 1,0000 (FAISS HNSW y pgvector HNSW) | 0,1000 en el JSON; no hay script que lo calcule |
| 14 | Recuperación | A | «Relevancia MRR (aprox.)» de las estrategias A–D en PoC-02 | 0,25 / 0,10 / 0,85 / 0,95 | Sin evidencia (no hay juicios de relevancia); se retira |
| 15 | Optimización | M | Conclusión de Alternativas §2 frente a su propia tabla | «Se mantiene NSGA-II» | La enumeración exacta es más rápida que NSGA-II en las 9 instancias |
| 16 | Optimización / FINAL | B | Costo de la enumeración y estados de la DP en `07-optimizacion.tex` | «milisegundos» para \|E\| ≤ 4.096; «O(n⁴k) estados ≈ 10⁴» | Hasta 0,34 s; los estados son O(n³), el tiempo es O(n⁴k); se miden menos de 260 estados por etapa en listas reales |
| 17 | Agentes y RAG | A | Puntaje de precio con oro «$0» (6 de 16 preguntas) | Cualquier texto con un «0» acierta | RAG sin LLM se mantiene en 15/16 con puntaje estricto; los aciertos de respuesta con LLM no se pueden verificar |
| 18 | Agentes y RAG | M | Acierto de KAG | 3/16 = 0,1875 | 1/16 = 0,0625 (el REPORTE ya declaraba falsos positivos los 2 aciertos con oro «$0») |
| 19 | Agentes y RAG | B | Preguntas con oro «$0» en el texto de n8n | 8 | 6 (8 son de precio, 2 con precio real) |
| 20 | Agentes y RAG | B | Única falla de RAG sin LLM | «producto ausente del catálogo» | Es la pregunta de agregación «el más barato de la categoría Textos» |
| 21 | Agentes y RAG | B | Recomendación contradictoria en NL2C | §5.5 «LLM local primario» frente a §13 «reglas + léxico (mantener)» | Se señala; las cifras favorecen las reglas en línea |

---

## 01 Percepción

Fuente: `Tukit-Poc-Tesis@534c973`, `poc_01_percepcion/` y `documento_maestro/seccion_percepcion.tex`.
Evidencia: [`01-percepcion/resultados/verificacion_percepcion.json`](01-percepcion/resultados/verificacion_percepcion.json).

**P, R y F1 se reproducen exactamente** (micro y macro, los 5 enfoques) desde
`corpus/resultados_benchmark_10.json`, con la misma función de emparejamiento.

1. **Latencia p50.** `06_comparar_enfoques.evaluar_enfoque` usa `sorted(lat)[len(lat)//2]`. Con 10
   documentos eso es el **6.º** valor, no la mediana (que es el promedio del 5.º y el 6.º; por rango
   más cercano sería el 5.º). Se corrige a la mediana estadística. Gemini pasa de 342,20 s a 312,46 s,
   Docling de 28,87 a 24,43, Baidu de 216,94 a 213,04, Vision de 6,38 a 6,33 y OCR de 0,20 a 0,18. No
   cambia el orden.
2. **Costo de Google Vision.** `07_run_full_benchmark.py` asigna 0,0015 USD fijos por documento, pero
   `run_google_vision` hace una llamada `document_text_detection` por página, hasta 5 páginas. Los 10
   documentos suman 46 páginas leídas, así que a precio de lista (1,50 USD por 1.000 páginas) son
   0,069 USD y no 0,015 (0,0069 USD por documento).
3. **Modelo.** La tabla dice «Gemini 3.5 Flash (LMM)», pero el *script* llama a `gemini-3.5-flash-lite`,
   y el texto de metodología de la misma sección dice «Flash Lite». El costo se estimó con 0,075 y
   0,30 USD por millón de tokens.
4. **Sesgos del montaje (metodológico; las cifras originales se conservan y se agrega el subconjunto
   justo).**
   - *Ventana de páginas.* Vision, Baidu y Gemini usan `pdf_a_imagenes_base64(max_paginas=5)`, mientras
     que OCR y Docling leen el documento entero. El *gold* cubre en la práctica las primeras páginas: en
     el documento de 27 páginas tiene 173 ítems, mientras OCR predice 1.232 y Docling 747. Lo que
     OCR y Docling leen después de la página 5 se cuenta como falso positivo. En los 2 documentos de
     5 páginas o menos (232 ítems), el F1 es: OCR 0,770, Vision 0,789, Baidu 0,695, Docling 0,757 y
     Gemini 0,987.
   - *Anclaje del gold.* El *gold* (`gold_standard_construido.json`) se construyó en
     `test_alternatives_app.py` eligiendo **una de las extracciones** («Elegir esta extracción») y
     corrigiéndola a mano. El 92,8 % de los ítems *gold* es texto idéntico (normalizado) a una
     predicción de Gemini, contra un 71,5 % de OCR y un 48,9 % de Docling. La ventaja de Gemini es real
     (también gana en el subconjunto justo), pero su magnitud está sesgada a su favor. Hace falta un
     *gold* anotado de forma independiente para publicar el margen.
- (B, menor) El *docstring* de `06_comparar_enfoques.py` dice «ratio > 0.85», y el código usa 0,75.

## 02 Embeddings

Fuente: `Isis2610-G19-Tukit-Alternativas@2e03e38`, `benchmarks/embeddings.py` y `REPORTE.md` §1.
Evidencia: [`02-embeddings/resultados/`](02-embeddings/resultados/).

MRR, Recall@5 y Recall@10 se reproducen exactamente con las versiones fijadas (fastembed 0.8.0).

9. `metricas_retrieval` suma `1/pos` para **cualquier** posición: es MRR, no MRR@10. Truncado en 10,
   mpnet queda en 0,8477 (antes 0,8508), MiniLM-L12 en 0,8621 (antes 0,8627) y jina en 0,9713 (antes
   0,9722). El orden no cambia.
10. El README y el *docstring* listan e5-small y e5-base, que nunca se evaluaron. `MODELOS` (y el
    REPORTE) evalúan MiniLM-L12, mpnet, jina-v2-base-es, e5-large, MiniLM-L6 y n-gramas.

Además (no es una corrección, sino evidencia nueva): el arnés de 29 productos satura (e5-large empata
con n-gramas). En el *gold* real de 392 renglones, la señal léxica gana (P@1 de 0,865) a e5-large
(0,791) y a jina (0,837).

## 03 Almacén vectorial

Fuente: `Isis2610-G19-Tukit-Alternativas@2e03e38` (`REPORTE.md` §3) y `Tukit-Poc-Tesis@534c973`
(`seccion_poc02_base_datos.tex` y `results/benchmark_backends_*.json`).
Evidencia: [`03-almacen-vectorial/resultados/indices_vectoriales.json`](03-almacen-vectorial/resultados/indices_vectoriales.json).

11. El texto dice que la búsqueda exacta «mantiene recall 1.0 a ~3 ms», pero su propia tabla dice
    0,46 ms por consulta. Re-ejecutado en otra máquina con carga: 0,50 ms.
12. El recall de IVF de 0,211 se reproduce, pero es un artefacto del dato: 10.000 vectores gaussianos
    isotrópicos de 1.024 dimensiones son el peor caso para cualquier índice aproximado. Con los 6.122
    productos reales embebidos con e5-large y 381 consultas reales, IVF con nprobe = 8 da 0,832, HNSW
    con los valores de pgvector (ef = 40) da 0,862 y con ef = 100 da 0,952. La conclusión «exacta» se
    sostiene por tamaño (menos de 1 ms con 6 mil vectores), no por el recall.
13. `seccion_poc02_base_datos.tex` (`tab:backends_vectoriales_ext`) publica Recall@10 = 1,0000 para
    FAISS HNSW y pgvector HNSW. `benchmark_backends_2026-09-02_1501.json` guarda
    `mean_recall_at_10 = 0.09999999999999998` para los dos. Ningún *script* versionado calcula ese
    valor (`rg` no encuentra `faiss_hnswflat` en el código). Que dos motores distintos den exactamente
    0,1 sugiere un error de cálculo (por ejemplo, una sola coincidencia dividida entre 10). Ninguno de
    los dos valores es verificable; se reporta como **no reproducible**.

## 04 Recuperación

Fuente: `Tukit-Poc-Tesis@534c973`, `seccion_poc02_base_datos.tex` (`tab:poc02_latencias`).

14. La columna «Relevancia MRR (Aprox.)» (léxica 0,25, expandida 0,10, vectorial 0,85, híbrida 0,95)
    no tiene respaldo. `results/benchmark_retrieval.json` solo guarda latencias y número de resultados,
    `data/queries_evaluacion.json` son 16 consultas **sin juicios de relevancia**, y ningún *script*
    calcula MRR para esas estrategias. Se retira de la tabla. La evidencia medible sobre señales está
    en el *gold* de 2.710 pares (05-umbral), donde la fusión RRF mide **peor** que su canal denso.

## 05 Umbral

Fuente: `tukit-mvp-pipeline@3ef9c2e` (`calibration/`) y `Tukit-Poc-Tesis@534c973` (`seccion_pipeline_mvp.tex`).
Evidencia: [`05-umbral/resultados/verificacion_calibracion.json`](05-umbral/resultados/verificacion_calibracion.json).

Se reproducen exactamente: AUC y PR-AUC por señal, percentiles, umbrales de Youden (0,582) y de F1
(0,520), Brier y ECE *out-of-fold*, la probabilidad en 0,58 (46,6 %), la simulación de 4
configuraciones (21,0/69,3, 71,2/83,2, 65,3/86,7 y 30,8/91,6), la descomposición del error
(307/20/27) y el verificador LLM (309/9/4 y 6/12; 93,6 % y 97,1 %).

5. 1.437/2.710 = **53,0 %** de negativos, no 52,4 %.
6. De los 394 renglones con `sin_match = 0`, 2 no tienen ningún SKU marcado correcto. Con al menos un
   correcto hay 392, y el promedio de SKUs correctos es 1.273/392 = **3,25**, no 3,29. Las P@1
   publicadas (79,4 / 84,3 / 89,8 %) dividen por 394; sobre 392 serían 79,8 / 84,7 / 90,3 %.
7. **Barrido de δ.** La tabla `tab:pipeline_mvp_delta_barrido` (de 59,9 %/87,7 % a 25,4 %/89,0 %) y el
   AUC del margen (0,713) se reproducen **solo** ordenando los candidatos por `rank_rrf`. El mismo
   documento explica más adelante que producción ordena por el *reranker* y que el *top-1* cambia en
   315 de 542 renglones. En el orden de producción: δ = 0,005 da 62,4 %/86,2 %, 0,01 da 48,2 %/84,7 %,
   0,02 da 38,6 %/86,8 % y 0,05 da 23,6 %/86,0 %, con AUC del margen = **0,354** (un margen grande
   predice error). El margen medio publicado para los incorrectos (−0,0029) no sale de ninguno de los
   dos órdenes (−0,0352 con RRF, +0,0512 con el *reranker*). La decisión de eliminar δ se **refuerza**.
8. **FINAL** `docs/algoritmos/secciones/05-resolucion.tex`, `tab:auc-prototipo` (y los specs y el plan
   `2026-09-22-resolucion-hibrida-grafo*`): el canal denso tiene AUC 0,805 y no 0,825; el RRF 0,739 y no
   0,753; el *reranker* 0,880 y no 0,879 (redondeo de 0,8798). Sobre los mismos 2.710 pares, la
   conclusión «el RRF mide peor que su canal denso» se mantiene.

## 06 Optimización

Fuente: `Isis2610-G19-Tukit-Alternativas@2e03e38` (`REPORTE.md` §2) y `FINAL@30cf1b5`
(`ensayos/bench_laya/`, `docs/informes/benchmark-laya/` y `docs/algoritmos/secciones/07-optimizacion.tex`).

Se reproducen exactamente: los 36 *gaps* de Alternativas §2 (re-ejecución) y todas las métricas
agregadas del benchmark Laya contra NSGA-II (`resumen.json`, recalculado desde las 6.285 filas de
`resultados.json.gz`, sin diferencias), incluidos el 94,5 % de reproducibilidad, el 99,4 % de Ahorrador
con 5 semillas, el 68,5 % de frentes con puntos dominados por la escalera y los 137 frente a 37 de
NSGA-II y enumeración.

15. Alternativas §2 concluye «se mantiene NSGA-II», pero en su propia tabla la **enumeración exacta es
    más rápida que NSGA-II en las 9 instancias** (de 0,0001 a 0,034 s contra 0,07 a 0,29 s), con
    espacios de 16 a 6.561 combinaciones y objetivos aleatorios. Esa evidencia no respalda elegir
    NSGA-II; la comparación propia de [`06-optimizacion/`](06-optimizacion/RESULTADOS.md) la reemplaza.
16. `07-optimizacion.tex`. (a) La enumeración con \|E\| ≤ 4.096 tarda «milisegundos» o «menos que una
    llamada de red»: en las listas reales, el `_frente_exacto` de producción tarda hasta 0,34 s. Es despreciable, pero no son milisegundos. (b) «Compárese con los O(n⁴k) estados de
    la programación dinámica [...] unos 10⁴ estados»: O(n⁴k) es el **tiempo**; los estados son
    O(n³), como máximo 11.340 para n = 17. En las listas reales se alcanzan **menos de 260 ternas por
    etapa**, porque todas las líneas tienen precio y pocas tienen personaje.

## 07 Agentes y RAG

Fuente: `Isis2610-G19-Tukit-Alternativas@2e03e38`, `REPORTE.md` §5 y §8–§13, y `scripts/rag_bench.py`.
Evidencia: [`07-agentes-rag/resultados/rag_sin_llm.json`](07-agentes-rag/resultados/rag_sin_llm.json).

17. `_puntua` compara **dígitos contenidos**: `gd in _digitos(answer)`. Para las 6 preguntas con oro
    «$0» (precio no publicado), cualquier texto con un «0» acierta, y el contexto de 5 chunks siempre
    lo tiene. Re-ejecutado con un criterio estricto (el chunk del producto preguntado debe estar entre
    los recuperados), RAG sin LLM **se mantiene en 15/16**, porque las preguntas nombran el producto.
    Los aciertos de *respuesta* con LLM (RAG 12/16, GraphRAG 9/16, KAG 3/16) pueden estar inflados
    hasta en 6 preguntas. No se pueden recalcular porque las respuestas no se versionaron.
18. KAG: el REPORTE declara que «los 2 hits de preguntas con gold $0 son falsos positivos del scorer»,
    pero publica 3/16 = 0,1875. El valor sin esos falsos positivos es **1/16 = 0,0625**.
19. §11 (n8n) habla de «el gold de esas 8 preguntas» con oro «$0». Son 6; las 8 son las preguntas de
    precio, y 2 de ellas tienen precio real (22.500 y 24.900).
20. §8 atribuye la única falla de RAG a «una pregunta con producto ausente del catálogo». La pregunta
    que falla es la de agregación («¿cuál es el producto más barato de la categoría Textos?»), que una
    búsqueda por similitud no puede resolver.
21. §5.5 dice «Recomendación adoptada: LLM local primario» y §13 dice «Extracción NL2C: reglas + léxico
    (mantener)». Las cifras del mismo REPORTE (2,1 s por caso, ±0,01 de F1) favorecen las reglas para
    uso en línea.

## No reproducido (informe interno)

| Qué | Por qué | Estado |
|---|---|---|
| Benchmarks de percepción (los 5 motores) | Los PDF no están versionados; Baidu necesita GPU CUDA; Vision y Gemini, claves | Se recalcularon las métricas desde las predicciones guardadas |
| Estrategias A–D de PoC-02 (latencias) y backends pgvector | Requieren el Postgres de PoC-02 con datos | Se tomaron del JSON; el recall publicado contradice el guardado (#13) |
| MTEB e5-large frente a mpnet | Descarga los conjuntos de MTEB y se midió en GPU | Se tomaron del JSON |
| Agente NL2C con Qwen2.5-1.5B (llama.cpp) | GGUF de 1 GB y compilación de llama-cpp-python; no es determinista (±0,01) | Se re-ejecutó solo la rama de reglas |
| RAG con LLM, GraphRAG (Neo4j), KAG (OpenSPG), n8n | Requieren contenedores o servicios (no se arrancó Docker) | Cifras del REPORTE; puntaje con defecto (#17–#19) |
| H1/H2/H3 de la simulación de δ | `similarity()` de pg_trgm contra Postgres | Se recalcularon las configuraciones sin base de datos |
| Laya (modelo de 421 M) | GPU y su entorno aparte | Se recalcularon los agregados desde las respuestas guardadas |
| Tiempos del benchmark Laya (5,3 s por lista) | Hardware distinto (Windows, 16 núcleos); el optimizador cambió después (v4–v7) | La comparación propia mide el optimizador vigente en Apple M4 |
