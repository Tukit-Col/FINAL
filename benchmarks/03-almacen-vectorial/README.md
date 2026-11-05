# 03 · Almacén vectorial: ¿búsqueda exacta o índice aproximado?

## Pregunta

Para el tamaño del catálogo de Tukit, ¿conviene la búsqueda vectorial exacta (pgvector sin índice o
recorrido exhaustivo) o un índice aproximado (IVF, HNSW, en FAISS o en pgvector)?

## Alternativas

numpy exacto, que equivale a `ORDER BY embedding <=> q` sin índice; FAISS `IndexFlatIP`, exacto;
FAISS `IndexIVFFlat` (nlist = 64, nprobe = 8 y 16); FAISS `IndexHNSWFlat` con los valores por omisión de
pgvector (m = 16, ef_construction = 64, ef_search = 40) y con ef_search = 100. Las mediciones previas de
PoC-02 incluyen además pgvector exacto y pgvector HNSW.

## Datos

- **Sintético** (el del repositorio de Alternativas): 10.000 vectores gaussianos isotrópicos de 1.024
  dimensiones y 100 consultas.
- **Catálogo real** (nuevo): los 6.122 productos del catálogo limpio de PoC-02, embebidos con
  multilingual-e5-large (1.024 d), con los 381 textos de renglones reales del *gold* como consultas.

## Métrica

Recall@10 frente a la búsqueda exacta, latencia por consulta (una a la vez, un hilo), tiempo de
construcción y memoria del índice.

## Resultados

| Índice | Recall@10 sintético | Recall@10 catálogo real | ms por consulta (real) | Construcción (real) |
|---|---:|---:|---:|---:|
| numpy exacto | 1,000 | 1,000 | 0,88 | — |
| FAISS FlatIP (exacto) | 1,000 | 1,000* | 1,18 | 0,006 s |
| FAISS IVFFlat, nprobe = 8 | **0,211** | 0,832 | 0,15 | 0,08 s |
| FAISS IVFFlat, nprobe = 16 | 0,386 | 0,918 | 0,39 | 0,07 s |
| FAISS HNSW, m = 16, ef = 40 (valores de pgvector) | 0,228 | 0,862 | 0,15 | 1,1 s |
| FAISS HNSW, m = 16, ef = 100 | 0,423 | 0,952 | 0,19 | 0,9 s |

\* 0,9997: empates de coseno resueltos en otro orden.

El recall de IVF en el sintético (0,211) **reproduce** el del REPORTE de Alternativas. Las latencias
absolutas difieren porque la máquina tenía otras cargas. Con vectores reales, el mismo índice recupera
el 83 % del top-10. El sintético isotrópico es el peor caso posible para un índice aproximado y no
representa a un catálogo con vecindades semánticas.

**Mediciones de PoC-02** (Postgres + pgvector, 50 consultas; no re-ejecutables sin la base):

| Motor | Latencia media | p50 | p95 | Recall@10 publicado | Recall@10 en el JSON guardado |
|---|---:|---:|---:|---:|---:|
| pgvector exacto (verdad de referencia) | 363,7 ms | 337,2 ms | 541,9 ms | — | — |
| FAISS HNSWFlat | 0,10 ms | 0,02 ms | 0,15 ms | 1,0000 | **0,1000** |
| pgvector HNSW | 5,06 ms | 4,92 ms | 6,22 ms | 1,0000 | **0,1000** |

El *recall* publicado no coincide con el guardado, y ningún script versionado lo calcula. Ver
[CORRECCIONES](../CORRECCIONES.md#03-almacén-vectorial).

## Conclusión

Con catálogos de cientos a pocos miles de productos, **la búsqueda exacta cuesta menos de 1 ms por
consulta** y no pierde vecinos, así que se mantiene: pgvector sin depender del índice HNSW o, como
hace FINAL, el recorrido exhaustivo sobre unos cientos de centroides de concepto. Un índice HNSW con
los valores por omisión de pgvector (ef_search = 40) perdería cerca del 14 % del top-10 en el catálogo
real. Si algún día se usa, ef_search debe subir a 100 o más (95 % de recall). La conclusión del
repositorio de Alternativas («exacta, mantener pgvector») se sostiene, pero no por la razón que daba
(recall de 0,21): esa cifra es un artefacto del dato sintético.

## Reproducir

```bash
python scripts/origen_alternativas/run_vectorstore.py          # sintético original
FASTEMBED_CACHE_PATH=... python scripts/comparar_indices.py \
  <Tukit-Poc-Tesis>/poc_02_base_de_datos/data/clean/feed_scraper_gt.json   # -> resultados/indices_vectoriales.json
```

Los vectores del catálogo (25 MB) no se versionan; el script los regenera y los guarda en `/tmp`.

## Procedencia

- `Tukit-Col/Isis2610-G19-Tukit-Alternativas@2e03e38` (main): `benchmarks/vectorstore.py`,
  `scripts/run_vectorstore.py` y `REPORTE.md` §3.
- `Tukit-Col/Tukit-Poc-Tesis@534c973` (main): `poc_02_base_de_datos/results/benchmark_backends_2026-09-02_1501.json`,
  `data/clean/feed_scraper_gt.json` y `documento_maestro/seccion_poc02_base_datos.tex` (`tab:backends_vectoriales_ext`).
- `Tukit-Col/FINAL@30cf1b5`: `docs/algoritmos/secciones/05-resolucion.tex`. Ahí consta que el índice
  HNSW existe en la base, pero la clasificación recorre los conceptos de forma exhaustiva.
