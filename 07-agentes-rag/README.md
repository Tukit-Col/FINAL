# 07 · Agentes y RAG: ¿LLM, grafo o consulta estructurada?

## Pregunta

1. **NL2C**: ¿un agente con LLM local convierte mejor que el parser de reglas una lista escrita por un
   papá en ítems y restricciones?
2. **Preguntas sobre el catálogo**: para responder precio, disponibilidad, marca, categoría y URL,
   ¿conviene RAG (con o sin LLM), GraphRAG (Neo4j), KAG/OpenSPG o un *workflow* n8n sobre Postgres?

## Alternativas

- NL2C: parser de reglas con recuperador léxico (producción) frente a un agente *plan-then-execute*
  con Qwen2.5-1.5B-Instruct Q4_K_M (llama.cpp, CPU). El agente OpenAI con *tool-calling* se diseñó
  (`agente_nl2c.py`) pero no se corrió, por costo.
- Preguntas: RAG sin LLM (e5-large, top-5), RAG con LLM local, GraphRAG puro (Cypher), GraphRAG con
  LLM, KAG/OpenSPG (*solver* con LLM local) y n8n (Webhook → reglas → SQL `ILIKE` → respuesta).

## Datos

- NL2C: 30 casos (20 en prosa y 10 en lista) con *ground truth*, semillas 7 y 11, catálogo sintético.
- Preguntas: el *feed* real VTEX con 413 productos escolares limpios
  ([`datos/feed_scraper_gt.json`](datos/feed_scraper_gt.json)) y 16 preguntas con oro
  ([`datos/preguntas.json`](datos/preguntas.json)).

## Métricas

NL2C: F1, precisión y *recall* de ítems (promedio por caso), cantidades correctas, acierto por tipo de
restricción y latencia. Preguntas: acierto de recuperación (el hecho oro está en el contexto) y de
respuesta (el hecho oro está en la respuesta), más la latencia.

## Resultados

**NL2C** (reglas re-ejecutadas e idénticas; el agente LLM no se re-ejecutó):

| Métrica | Reglas (producción) | Agente LLM local (publicado) |
|---|---:|---:|
| F1 de ítems | 0,9159 ✔ | 0,9356 |
| Precisión / Recall | 0,8861 / 0,9556 ✔ | 0,9556 / 0,9222 |
| Cantidades correctas | 0,8389 ✔ | 0,8833 |
| F1 en prosa / en lista | 0,8905 / 0,9667 ✔ | 0,9300 / 0,9467 |
| Restricción de exclusión de marca | 0,50 ✔ | 1,00 |
| Latencia por caso | ≈ 0 ms | 2,1 s |

✔ = reproducido en este repositorio.

**Preguntas sobre el catálogo:**

| Variante | Recuperación | Respuesta | Latencia por pregunta | Estado |
|---|---:|---:|---:|---|
| RAG sin LLM | **15/16** (puntaje original y estricto) | — | 0,061 s | re-ejecutado ✔ |
| RAG con LLM local | 15/16 | 12/16 (publicado) | 24,9 s | no re-ejecutado |
| GraphRAG puro (Cypher) | 16/16 | — | 0,019 s | no re-ejecutado (Neo4j) |
| GraphRAG con LLM local | 16/16 | 9/16 (publicado) | 0,6 s | no re-ejecutado |
| KAG/OpenSPG con LLM local | — | 3/16 publicado, **1/16** sin los 2 falsos positivos que el mismo REPORTE reconoce | 14,5 s | no re-ejecutado |
| n8n sobre Postgres | 16/16 | — | 0,023 s | no re-ejecutado (contenedor) |

**Problema del puntaje.** 6 de las 16 preguntas preguntan el precio de un producto con precio no
publicado, cuyo oro es «$0». El puntaje original busca los dígitos del oro dentro del texto, así que
cualquier respuesta o contexto con un «0» cuenta como acierto. Con un criterio estricto (el chunk del
producto preguntado debe estar entre los recuperados), RAG sin LLM mantiene 15/16; el único fallo es
la pregunta de agregación «¿cuál es el producto más barato de la categoría Textos?». En cambio, los
aciertos de **respuesta** con LLM (RAG 12/16, GraphRAG 9/16, KAG 3/16) pueden estar inflados hasta en
6 preguntas, y no se pueden recalcular porque las respuestas no se guardaron
(`resultados/` está en `.gitignore`). Ver [CORRECCIONES](../CORRECCIONES.md#07-agentes-y-rag).

## Conclusión

- Para **precio, disponibilidad, marca, categoría y URL**, una consulta estructurada y determinista
  (Cypher sobre Neo4j o SQL sobre Postgres desde n8n) responde exacto en unos 20 ms y sin alucinar. Es
  la mejor opción.
- RAG sin LLM recupera bien cuando la pregunta nombra el producto, pero **no resuelve agregaciones**
  (el más barato de una categoría).
- Un LLM local de 1,5B no sirve en línea: RAG con LLM tarda unos 25 s por pregunta, y KAG asume un
  modelo de frontera (contexto de unos 13 K tokens).
- En NL2C, el agente local gana algo de F1 (0,936 contra 0,916) a 2,1 s por caso, y es claramente
  mejor en exclusiones de marca. El REPORTE es contradictorio en su recomendación: §5.5 adopta «LLM
  local primario» y §13 mantiene «reglas + léxico».

## Reproducir

```bash
# NL2C (reglas), desde la raíz de Isis2610-G19-Tukit-Alternativas
python scripts/run_agentes.py --sin-agente
# RAG sin LLM, sin servidor de embeddings y con el puntaje estricto
FASTEMBED_CACHE_PATH=... python scripts/rag_sin_llm_offline.py <raíz de Isis2610-G19-Tukit-Alternativas>
```

El agente LLM (`--agente-local`, unos 1 GB de GGUF y llama-cpp-python), GraphRAG (Neo4j), KAG (OpenSPG)
y n8n necesitan servicios o contenedores locales y no se re-ejecutaron. La credencial de Postgres del
*workflow* n8n (`n8n/creds/`) **no se copió** a este repositorio.

## Procedencia

- `Tukit-Col/Isis2610-G19-Tukit-Alternativas@2e03e38` (main): `benchmarks/agente_local.py`, `agente_nl2c.py`,
  `_debug_agente.py`, `baseline_actual.py`, `scripts/run_agentes.py`, `analizar_agentes.py`, `rag_bench.py`,
  `graphrag_bench.py`, `n8n_bench.py`, `preguntas_papa.py`, `kag/tukit/solver/eval.py`,
  `n8n/workflow/tukit_pregunta.json`, `datos/preguntas.json`, `datos/feed_scraper_gt.json` y `REPORTE.md` §5 y §8–§13.
