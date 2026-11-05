# 04 · Recuperación: ¿léxica, vectorial o híbrida?

## Pregunta

¿Qué estrategia empareja mejor un renglón de lista con el producto o el concepto del catálogo: la
léxica (pg_trgm, TF-IDF de n-gramas), la vectorial pura, la híbrida (RRF + MAUT) o la léxica con un
canal semántico de apoyo? ¿Mejora algo normalizar el texto del catálogo?

## Alternativas y datos

| Comparación | Alternativas | Datos | Fuente |
|---|---|---|---|
| A. Estrategias de búsqueda en Postgres | A léxica pura (pg_trgm), B léxica + sinónimos, C vectorial pura (HNSW), D híbrida RRF (k = 60) + MAUT (0,6 / 0,3 / 0,1) | 16 consultas sin juicios de relevancia, catálogo PoC-02 | PoC-02 |
| B. Lista en lenguaje natural a ítems (NL2C) | reglas + léxico (producción), reglas + e5-large, reglas + MiniLM-L12, solo vectorial e5-large, solo vectorial MiniLM-L12 (umbral de 0,30 a 0,50) | 30 casos (20 en prosa y 10 en lista), semillas 7 y 11, catálogo sintético de 29 productos | Alternativas §5.6 |
| C. Señales sobre el *gold* real | léxica, densa, RRF, max(vec, lex), *reranker* | 2.710 pares anotados | [05-umbral](../05-umbral/README.md) |
| D. Normalización del texto del catálogo | V0 (actual), V1 (marca canónica), V2 (sin precio ni proveedor en el embedding), V3 (categoría canónica), V3b (concepto fino), V4 (presentación normalizada) | 2.710 pares, *pool* fijo de 5 | tukit-mvp-pipeline |

## Resultados

**A. Estrategias en Postgres** (solo latencia; [`resultados/benchmark_retrieval.json`](resultados/benchmark_retrieval.json)):

| Estrategia | p50 (ms) | Media (ms) | Máx. (ms) | Resultados medios (de 20) |
|---|---:|---:|---:|---:|
| A léxica pura | 6,66 | 40,6 | 130,1 | 11,9 |
| B léxica expandida | 6,59 | 52,8 | 182,9 | 4,0 |
| C vectorial pura | 46,51 | 106,6 | 945,0 | 20,0 |
| D híbrida RRF + MAUT | 53,17 | 155,5 | 1.099,3 | 20,0 |

La tabla publicada agrega una columna «Relevancia MRR (aprox.)» con 0,25, 0,10, 0,85 y 0,95. **No hay
datos que la respalden**: las 16 consultas no tienen juicios de relevancia y el JSON solo guarda
latencias. Se retira; ver [CORRECCIONES](../CORRECCIONES.md#04-recuperación).

**B. NL2C** (re-ejecutado; las cifras coinciden con el REPORTE de Alternativas al cuarto decimal; F1 es
el promedio del F1 por caso):

| Enfoque | F1 | Precisión | Recall | Cantidades correctas |
|---|---:|---:|---:|---:|
| **Reglas + léxico (producción)** | **0,9159** | 0,8861 | 0,9556 | 0,8389 |
| Reglas + e5-large | 0,7260 | 0,6889 | 0,7778 | 0,7333 |
| Solo vectorial e5-large (umbral de 0,30 a 0,50) | 0,7324 | 0,6833 | 0,8000 | 0,7556 |
| Reglas + MiniLM-L12 | 0,5927 | 0,5556 | 0,6445 | 0,8095 |
| Solo vectorial MiniLM-L12, umbral 0,30 | 0,5463 | 0,5278 | 0,5778 | 0,8571 |
| Solo vectorial MiniLM-L12, umbral 0,40 | 0,5724 | 0,5750 | 0,5778 | 0,8571 |
| Solo vectorial MiniLM-L12, umbral 0,50 | 0,5622 | 0,5972 | 0,5444 | 0,9198 |

**C. Señales sobre el *gold* real** (ROC-AUC): léxica 0,728; densa 0,805; RRF 0,739;
max(vec, lex) 0,843; *reranker* 0,880. Reordenando solo por el nombre del producto, la línea base de
n-gramas logra P@1 = 0,865, por encima de todos los *embeddings* ([02-embeddings](../02-embeddings/README.md)).

**D. Normalización del catálogo** (recalculado desde
[`datos/normalizacion_scores.csv.gz`](datos/normalizacion_scores.csv.gz); idéntico al resumen publicado):

| Variante | AUC del *reranker* | AUC denso | Acierto@1 | Cobertura a τ = 0,63 | Precisión a τ = 0,63 | Veredicto (IC 95 %, *bootstrap* pareado) |
|---|---:|---:|---:|---:|---:|---|
| V0 actual | 0,879 | 0,803 | 65,3 % | 64,8 % | 86,3 % | línea base |
| V1 marca canónica | 0,878 | 0,801 | 65,1 % | 64,0 % | 86,2 % | se rechaza (pierde en ambos ejes) |
| V2 V1 + embedding sin precio ni proveedor | 0,878 | 0,793 | 65,1 % | 64,0 % | 86,2 % | se rechaza |
| V3 V2 + categoría canónica | 0,877 | 0,798 | 65,1 % | 63,8 % | 86,4 % | no mejora |
| V3b V2 + concepto fino | 0,874 | 0,797 | 65,3 % | 64,8 % | 84,9 % | neutra |
| V4 V3 + presentación normalizada | 0,880 | 0,802 | 64,9 % | 63,8 % | 86,7 % | neutra |

## Conclusión

- Para mapear renglones, **la estructura léxica es la señal más confiable y barata**. El pipeline solo
  vectorial no alcanza a las reglas con léxico (F1 de 0,73 contra 0,92), y con *embeddings* la
  extracción deja de importar porque el cuello de botella pasa a ser el ranking semántico.
- La fusión RRF **mide peor que su propio canal denso** (0,739 contra 0,805), así que no sirve como
  puntaje de confianza; solo sirve para ordenar.
- Normalizar el texto del catálogo no mejora nada medible con el *pool* fijo.
- Esto respalda la fusión con guardas de FINAL: la cabeza anclada decide los conceptos admisibles y
  el coseno solo desempata o rescata sinónimos (κ ≥ 0,86), con la garantía de que el canal semántico
  nunca resta (Proposición «El canal semántico nunca resta», `05-resolucion.tex`).

## Reproducir

```bash
# B (desde la raíz de Isis2610-G19-Tukit-Alternativas; fastembed descarga e5-large y MiniLM-L12)
python scripts/run_agentes.py --sin-agente
for u in 0.30 0.40 0.50; do python scripts/run_vectorial.py --umbral $u; done
# D (desde la raíz de tukit-mvp-pipeline)
python calibration/medir_normalizacion.py --desde-scores
```

A necesita el Postgres de PoC-02 con el catálogo y los embeddings cargados, y no se re-ejecutó.

## Procedencia

- `Tukit-Col/Tukit-Poc-Tesis@534c973` (main): `poc_02_base_de_datos/tests/benchmark_strategies.py`,
  `services/search_api.py`, `results/benchmark_retrieval.json`, `data/queries_evaluacion.json` y
  `documento_maestro/seccion_poc02_base_datos.tex` (`tab:poc02_latencias`).
- `Tukit-Col/Isis2610-G19-Tukit-Alternativas@2e03e38` (main): `benchmarks/retrieval.py`, `vectorial_only.py`,
  `baseline_actual.py`, `nl2c_data.py`, `data.py`, `scripts/run_vectorial.py` y `REPORTE.md` §5.4–5.6.
- `Tukit-Col/tukit-mvp-pipeline@3ef9c2e` (master): `calibration/medir_normalizacion.py`,
  `normalizacion_scores.csv` y `normalizacion_resumen.csv`.
- `Tukit-Col/Isis2610-G19-Tukit-Poc@d1f7225` (main): `services/api-gateway/retrieval/` (`pipeline.py`,
  `reranker.py`) implementa la estrategia D con pgvector, pg_trgm, RRF y MAUT. Sus pruebas
  (`tests/test_retrieval_pipeline.py`) son unitarias de los filtros SQL y no comparan alternativas.
