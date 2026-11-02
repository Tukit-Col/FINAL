# 02 · Modelos de *embeddings*: ¿cuál representa mejor un renglón de lista?

## Pregunta

¿Qué modelo de *embeddings* conviene para emparejar un renglón de una lista de útiles con un producto
del catálogo, frente a una línea base léxica?

## Alternativas

`intfloat/multilingual-e5-large` (1.024 d, el de producción), `jinaai/jina-embeddings-v2-base-es`
(768 d, entrenado para español), `paraphrase-multilingual-mpnet-base-v2` (768 d),
`paraphrase-multilingual-MiniLM-L12-v2` (384 d, ONNX cuantizado en fastembed),
`all-MiniLM-L6-v2` (384 d, solo inglés) y la línea base léxica de TF-IDF sobre n-gramas de caracteres
3–5, que aproxima pg_trgm.

## Datos

1. **Arnés sintético** (repositorio de Alternativas): 29 productos y 87 paráfrasis con su producto
   correcto.
2. **Gold real** (nuevo en este repositorio): los 542 renglones del *gold* de calibración
   ([`../05-umbral/datos/gold_standard_final.csv`](../05-umbral/datos/gold_standard_final.csv)), cada
   uno con 5 candidatos del catálogo real (2.710 pares, 1.273 correctos). Se reordenan los candidatos de
   cada renglón por coseno(renglón, nombre del producto).
3. **MTEB** (PoC-02): STS22 y SpanishPassageRetrievalS2P, solo para e5-large y mpnet, en GPU.

## Métricas

MRR@10 y Recall@5/10 en el arnés sintético. En el *gold* real: P@1 y MRR sobre los 392 renglones con
algún candidato correcto, y ROC-AUC del coseno sobre los 2.710 pares.

## Resultados

**Arnés sintético** (re-ejecutado con las versiones fijadas: fastembed 0.8.0, numpy 2.5.1). MRR y
Recall se reproducen exactamente. Se agrega la columna de MRR@10 truncado en el puesto 10; el original
no truncaba (ver [CORRECCIONES](../CORRECCIONES.md#02-embeddings)).

| Modelo | MRR (publicado) | MRR@10 (truncado) | Recall@5 | Recall@10 | Dim. |
|---|---:|---:|---:|---:|---:|
| multilingual-e5-large | 0,9943 | 0,9943 | 1,0000 | 1,0000 | 1.024 |
| n-gramas 3–5 (léxico) | 0,9943 | 0,9943 | 1,0000 | 1,0000 | 975 |
| jina-embeddings-v2-base-es | 0,9722 | 0,9713 | 0,9885 | 0,9885 | 768 |
| all-MiniLM-L6-v2 | 0,9573 | 0,9573 | 1,0000 | 1,0000 | 384 |
| paraphrase-multilingual-MiniLM-L12-v2 | 0,8627 | 0,8621 | 0,9655 | 0,9885 | 384 |
| paraphrase-multilingual-mpnet-base-v2 | 0,8508 | 0,8477 | 0,9195 | 0,9540 | 768 |

**Gold real** (reordenar los 5 candidatos de 392 renglones de listas reales; nuevo):

| Señal | P@1 | MRR | ROC-AUC (pares) | ms por texto* |
|---|---:|---:|---:|---:|
| n-gramas 3–5 (léxico) | **0,865** | **0,924** | **0,835** | ≈ 0 |
| jina-embeddings-v2-base-es | 0,837 | 0,907 | 0,813 | 34,8 |
| all-MiniLM-L6-v2 | 0,811 | 0,885 | 0,801 | 3,4 |
| multilingual-e5-large | 0,791 | 0,885 | 0,774 | 84,0 |
| multilingual-e5-large con prefijos `query:`/`passage:` | 0,778 | 0,875 | 0,710 | 94,2 |
| paraphrase-multilingual-mpnet-base-v2 | 0,747 | 0,850 | 0,674 | 23,2 |
| paraphrase-multilingual-MiniLM-L12-v2 | 0,712 | 0,824 | 0,635 | 13,6 |
| *Referencia*: `vec_score` guardado (e5-large sobre nombre, categoría, marca y precio) | 0,829 | 0,906 | 0,805 | — |
| *Referencia*: `rerank_score` guardado (cross-encoder bge-reranker-v2-m3) | 0,903 | 0,946 | 0,880 | — |

\* Latencia en CPU (Apple M4) con otras cargas corriendo; solo indicativa.

**MTEB** (PoC-02, GPU CUDA; no se re-ejecutó porque descarga los conjuntos de MTEB):

| Modelo | STS22 (Spearman) | SpanishPassageRetrievalS2P MRR@10 | Recall@10 | ms por consulta |
|---|---:|---:|---:|---:|
| multilingual-e5-large | 0,682 | 0,616 | 0,408 | 550,1 |
| paraphrase-multilingual-mpnet-base-v2 | 0,599 | 0,473 | 0,317 | 69,9 |

## Conclusión

- En el arnés sintético, e5-large y la línea base léxica **empatan** (MRR de 0,994): el arnés satura y
  no discrimina.
- Con renglones reales, **la señal léxica es la más fuerte por sí sola** (P@1 de 0,865). Entre los
  modelos neuronales, jina-v2-base-es (0,837) supera a e5-large (0,791) con menos de la mitad del costo
  por texto. Los prefijos de e5 no ayudan con nombres cortos de producto.
- En los benchmarks generales (MTEB), e5-large sí gana a mpnet por un margen claro.
- La evidencia respalda el diseño de FINAL: **la estructura léxica decide** (cabeza anclada) y el canal
  semántico solo desempata o rescata sinónimos con un umbral alto (κ ≥ 0,86). Si se cambiara de modelo,
  jina-v2-base-es es el candidato con mejor relación calidad-costo en estos datos. Tiene una salvedad:
  el *pool* de 5 candidatos lo trajo el sistema híbrido, así que el reordenamiento favorece a las
  señales que lo construyeron.

## Reproducir

```bash
export FASTEMBED_CACHE_PATH=/ruta/cache   # unos 4 GB de modelos
python scripts/origen_alternativas/run_embeddings.py   # desde la raíz de Isis2610-G19-Tukit-Alternativas
python scripts/evaluar_embeddings_gold.py <raíz de Isis2610-G19-Tukit-Alternativas>  # -> resultados/embeddings_gold.json
```

Con onnxruntime 1.31, e5-large falla al validar la ruta de `model.onnx_data` si el caché usa enlaces
simbólicos. Se resolvió reemplazando los enlaces de la carpeta del modelo por enlaces duros.

## Procedencia

- `Tukit-Col/Isis2610-G19-Tukit-Alternativas@2e03e38` (main): `benchmarks/embeddings.py`, `benchmarks/data.py`,
  `scripts/run_embeddings.py`, `REPORTE.md` §1. Los resultados crudos no estaban versionados
  (`resultados/` está en `.gitignore`); se re-ejecutaron.
- `Tukit-Col/Tukit-Poc-Tesis@534c973` (main): `poc_02_base_de_datos/tests/benchmark_mteb.py`,
  `results/benchmark_mteb_*.json` y `documento_maestro/seccion_poc02_base_datos.tex` (`tab:mteb_benchmark_ext`).
- `Tukit-Col/tukit-mvp-pipeline@3ef9c2e` (master): `calibration/gold_standard_final.csv` (el *gold* real).
