# Tukit-Benchmarks

Este repositorio consolida las comparaciones de alternativas de **Tukit** (trabajo de grado de
Ingeniería de Sistemas, Pontificia Universidad Javeriana). Tukit es una plataforma B2B2C que lee una
lista de útiles con un modelo multimodal, normaliza cada renglón contra un catálogo de conceptos con
búsqueda híbrida léxica y vectorial, y arma kits con optimización multiobjetivo (enumeración exacta si
el espacio tiene ≤ 4.096 combinaciones, NSGA-II si no).

Cada carpeta tiene un `README.md` con la pregunta, las alternativas, los datos, la métrica, los
resultados, la conclusión y la procedencia (repositorio@commit y archivo). También tiene `scripts/`
(los originales y los de verificación) y `resultados/`. Todas las cifras se **recalcularon desde los
datos crudos** guardados en los repositorios de origen o se **re-ejecutaron** fuera de línea. Lo que
no se reprodujo o estaba mal calculado se corrigió aquí y quedó registrado en
[CORRECCIONES.md](CORRECCIONES.md).

## Resumen

| # | Pregunta | Alternativas | Ganador | Métrica clave (corregida) | Detalle |
|---|---|---|---|---|---|
| 01 | ¿Qué motor lee mejor una lista en PDF? | OCR + regex, Google Vision, Baidu GOT-OCR2.0, Docling, Gemini 3.5 Flash-Lite | **Gemini 3.5 Flash-Lite** | F1 micro 0,948 (siguiente: Vision, 0,673); en documentos de ≤ 5 páginas, 0,987 contra 0,70–0,79. Mediana de 312 s por documento (cuota) y 0,0017 USD por documento | [01-percepcion](01-percepcion/README.md) |
| 02 | ¿Qué *embedding* representa mejor un renglón? | e5-large, jina-v2-base-es, mpnet, MiniLM-L12, MiniLM-L6, n-gramas | **n-gramas (léxico)** en datos reales; jina-v2-base-es entre los neuronales | *Gold* real (392 renglones): P@1 de 0,865 (léxico), 0,837 (jina) y 0,791 (e5-large). En el sintético, e5 empata con el léxico (MRR 0,994) | [02-embeddings](02-embeddings/README.md) |
| 03 | ¿Búsqueda vectorial exacta o índice aproximado? | numpy/pgvector exacto, FAISS Flat, IVF, HNSW | **Exacta** (por tamaño) | 0,88 ms por consulta con 6.122 vectores reales; HNSW con los valores de pgvector: recall@10 de 0,862 (0,952 con ef = 100) | [03-almacen-vectorial](03-almacen-vectorial/README.md) |
| 04 | ¿Recuperación léxica, vectorial o híbrida? | pg_trgm, sinónimos, vectorial HNSW, RRF + MAUT, solo vectorial, normalización del catálogo | **Léxica con guardas + canal semántico de apoyo** | NL2C: F1 de 0,916 (reglas + léxico) contra 0,732 (solo vectorial e5). AUC: RRF 0,739 < denso 0,805 | [04-recuperacion](04-recuperacion/README.md) |
| 05 | ¿Qué umbral τ, y hace falta δ? | τ de 0,85 / 0,58 / 0,630 / 0,716; δ = 0,05; familias H1/H2/H3; verificador LLM | **τ = 0,630 sin δ** + verificador LLM de selección | Cobertura de 65,3 % y precisión de 86,7 % (contra 21,0 % y 69,3 % con δ); con el verificador, 93,6 %. AUC del margen δ: 0,354 | [05-umbral](05-umbral/README.md) |
| 06 | ¿NSGA-II, DP, enumeración o regla para los kits? | enumeración, programación dinámica O(n⁴k), NSGA-II con y sin siembra, voraz; (B) Laya | **Programación dinámica** (con la formulación vigente) | Exacta en 174 de 174 listas; 0,64 ms contra 996 ms de NSGA-II (1.404× en mediana). NSGA-II: frente exacto en el 89,7 % y HV/HV* de 0,9998. Laya no compite | [06-optimizacion](06-optimizacion/README.md), [RESULTADOS](06-optimizacion/RESULTADOS.md) |
| 07 | ¿LLM, grafo o consulta estructurada para NL2C y preguntas? | reglas, Qwen2.5-1.5B local, RAG ± LLM, GraphRAG ± LLM, KAG, n8n | **Consulta estructurada** (GraphRAG o n8n) para datos; **reglas + léxico** para NL2C en línea | 16/16 en unos 20 ms (Cypher o SQL); RAG sin LLM 15/16 (también con puntaje estricto); KAG 1/16 corregido | [07-agentes-rag](07-agentes-rag/README.md) |

## Inventario de fuentes (Tukit-Col)

| Repositorio @ commit | Material de comparación | Carpeta |
|---|---|---|
| `Isis2610-G19-Tukit-Alternativas@2e03e38` | `benchmarks/*.py`, `scripts/*_bench.py`, `run_*.py`, `REPORTE.md`, `datos/*.json` (sin resultados crudos versionados) | 02, 03, 04, 06, 07 |
| `Tukit-Poc-Tesis@534c973` | PoC-01 (5 motores de percepción, CGS-10 y κ), PoC-02 (MTEB, backends vectoriales, estrategias A–D), PoC-03 (motor HITL, sin comparación) y el documento maestro (LaTeX) | 01, 02, 03, 04, 05 |
| `FINAL@30cf1b5` (clon local) | `ensayos/bench_laya/`, `docs/informes/benchmark-laya/`, `docs/informes/reporte-benchmark-laya-nsga.md`, `docs/algoritmos/` (secciones 03, 04, 05, 07 y 08) y el optimizador de producción | 05, 06 |
| `tukit-mvp-pipeline@3ef9c2e` | `calibration/`: *gold* de 2.710 pares, calibración isotónica, δ, equivalencias H1/H2/H3, verificador LLM y normalización V0–V4 | 04, 05 |
| `Isis2610-G19-Tukit-Poc@d1f7225` | `services/api-gateway/retrieval/` (pgvector + pg_trgm + RRF + MAUT y *reranker*); sus pruebas son unitarias, sin comparación | 04 |
| `MS-Busqueda@cd48507` | `data/e2e/e2e_f3_resultados.json` (2.176 renglones con τ = 0,85 y δ = 0,05) y `scripts/calibracion_resolucion.py` (catálogo sintético) | 05 |
| `Tukit-QA@4d4c23b` | Pruebas de calidad (carga con Locust, caos, presupuesto de Gemini): miden el sistema, no comparan alternativas | — |
| `tukit-mvp-front`, `Tukit-Frontend`, `Tukit-Auth`, `Tukit-Auditoria`, `Tukit-DevSetup`, `MS-*` (APIGateway, BFFAdmin, Comercio, Cuentas, Instituciones, Plataforma) | Revisados: solo tienen métricas operativas (`app/core/metricas.py`) y pruebas, sin comparaciones de alternativas | — |

## Reproducción y entorno

- Re-ejecutado en Apple M4 con macOS 26.7.1 y Python 3.12.12. Para el repositorio de Alternativas se
  usó un entorno aparte con sus versiones fijadas (numpy 2.5.1, fastembed 0.8.0, faiss-cpu 1.15.0,
  scikit-learn 1.9.0 y pymoo 0.6.2); para la comparación de optimizadores, numpy 2.5.3 y pymoo 0.6.2,
  con el optimizador de FINAL importado en solo lectura.
- **No se usaron APIs pagas**: no se gastó Gemini, Google Vision, Baidu ni OpenAI. Las cifras de esos
  motores salen de las predicciones guardadas.
- Lo que necesita servicios (Postgres de PoC-02, Neo4j, OpenSPG, n8n o llama.cpp) no se re-ejecutó; está
  listado en [CORRECCIONES.md § No reproducido](CORRECCIONES.md#no-reproducido-informe-interno).
- No se copiaron credenciales: `n8n/creds/` y los `.env` quedan fuera.
