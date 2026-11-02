# 05 · Umbral de autoaceptación: ¿qué τ, y hace falta δ?

## Pregunta

¿Con qué umbral τ se debe aceptar automáticamente el primer candidato de un renglón? ¿Aporta algo el
margen δ entre el primero y el segundo candidato, o un mecanismo alternativo (familias de
equivalencia, grafo de sustituibilidad, verificador LLM)?

## Alternativas

- **Señales de confianza**: `rrf_score` (fusión por rango), `lex_score` (pg_trgm), `vec_score`
  (e5-large), max(vec, lex) y `rerank_score` (cross-encoder `bge-reranker-v2-m3` con sigmoide).
- **Reglas de decisión**: τ = 0,85 heredado; τ = 0,58 (Youden); τ = 0,630 (P ≥ 75 % calibrada);
  τ = 0,716 (P ≥ 85 %); τ + δ = 0,05; τ + familias H1/H2/H3; τ + verificador LLM.

## Datos

El *gold* de calibración tiene **542 renglones** de 5 listas reales, cada uno con sus 5 candidatos del
*retrieval* híbrido: son 2.710 pares, 1.273 de ellos correctos, anotados a mano. Los datos están en
[`datos/gold_standard_final.csv`](datos/gold_standard_final.csv). Las salidas guardadas del verificador
LLM están en [`datos/verificador_seleccion_resultados.csv`](datos/verificador_seleccion_resultados.csv).

## Métricas

ROC-AUC y PR-AUC por par; P@1 por renglón; Brier y ECE *out-of-fold* (GroupKFold de 5 particiones por
renglón). En la simulación sobre los 542 renglones: cobertura (fracción autoaceptada) y precisión (de
lo autoaceptado, lo correcto).

## Resultados (recalculados desde el CSV)

**Poder discriminativo por señal** (2.710 pares; P@1 sobre los 394 renglones con `sin_match = 0`, como
en el documento):

| Señal | ROC-AUC | PR-AUC | P@1 |
|---|---:|---:|---:|
| `rrf_score` | 0,739 | 0,694 | 79,4 % |
| `lex_score` | 0,728 | 0,683 | — |
| `vec_score` | 0,805 | 0,792 | — |
| max(vec, lex) | 0,843 | 0,784 | 84,3 % |
| **`rerank_score`** | **0,880** | **0,846** | **89,8 %** |

Todas las cifras se reproducen. El documento de algoritmos de FINAL (`05-resolucion.tex`, tabla
`tab:auc-prototipo`) dice que el canal denso tiene 0,825 y el RRF 0,753, valores que **no salen de
estos datos** (0,805 y 0,739). La conclusión no cambia: el RRF sigue por debajo del canal denso. Ver
[CORRECCIONES](../CORRECCIONES.md#05-umbral).

**Umbrales sobre `rerank_score`**: Youden da τ = 0,582 (J = 0,601) y F1 máximo da τ = 0,520 (F1 = 0,800).
El percentil 90 de los candidatos correctos es 0,726, así que τ = 0,85 es inalcanzable.

**Calibración isotónica** (*out-of-fold*):

| Población | Brier crudo | Brier calibrado | ECE crudo | ECE calibrado |
|---|---:|---:|---:|---:|
| Top-1 (n = 542, tasa base 65,3 %) | 0,1802 | 0,1214 | 0,2092 | 0,0327 |
| Todos (n = 2.710, tasa base 47,0 %) | 0,2149 | 0,1397 | 0,2240 | 0,0174 |

La probabilidad calibrada del renglón marginal a τ = 0,58 es 46,6 %.

**Simulación extremo a extremo** (542 renglones; las configuraciones con H1, H2 y H3 necesitan
Postgres y no se recalcularon):

| Configuración | Cobertura | Precisión | A revisión |
|---|---:|---:|---:|
| τ = 0,58 + δ = 0,05 (vigente entonces) | 21,0 % | 69,3 % | 50,2 % |
| Solo τ = 0,58 | 71,2 % | 83,2 % | 0 % |
| **Solo τ = 0,630 (P ≥ 75 %)** | **65,3 %** | **86,7 %** | 0 % |
| Solo τ = 0,716 (P ≥ 85 %) | 30,8 % | 91,6 % | 0 % |

Con τ = 0,630 se autoaceptan 354 renglones: 307 aciertos, 20 errores en renglones sin candidato correcto
(huecos del catálogo) y 27 errores en renglones que sí tenían uno correcto.

**Barrido de δ en el orden de producción** (los candidatos ordenados por el *reranker*, 394 renglones):

| δ | Cobertura | Precisión del top-1 |
|---:|---:|---:|
| 0 | 100 % | 89,9 % |
| 0,005 | 62,4 % | 86,2 % |
| 0,01 | 48,2 % | 84,7 % |
| 0,02 | 38,6 % | 86,8 % |
| 0,05 | 23,6 % | 86,0 % |

El ROC-AUC del margen como señal de acierto es 0,354, menor que 0,5: un margen grande indica
**error**. El documento publicaba un barrido distinto (de 59,9 %/87,7 % a 25,4 %/89,0 %, con
AUC = 0,713) que se reproduce solo con el orden del RRF, que el mismo documento identifica después
como el orden equivocado. Ver [CORRECCIONES](../CORRECCIONES.md#05-umbral).

**Verificador LLM de selección** (Gemini Flash-Lite elige entre los 5 candidatos o responde «ninguno»;
354 renglones autoaceptados, 14 lotes fallidos y 340 válidos): acierta en 309 de 322 cuando hay un
candidato correcto (96,0 %) y reconoce «ninguno» en 6 de 18 huecos. La precisión pasa de 86,7 % a
93,6 % con una cobertura de 97,1 %. Las cifras se reproducen desde las salidas guardadas.

**Contexto de producción.** MS-Busqueda (corrida E2E sobre 2.176 renglones, τ = 0,85, δ = 0,05) dejó
35,3 % autoaceptado, 36,5 % ambiguo y 28,1 % sin coincidencia ([`resultados/e2e_f3_resultados_ms_busqueda.json`](resultados/e2e_f3_resultados_ms_busqueda.json)).
El sistema final (FINAL) usa otra función de puntaje: un puntaje híbrido con cabeza anclada y
τ = 0,75. Por eso los umbrales de esta sección valen para el *reranker* del prototipo y no se
trasladan tal cual.

## Conclusión

Para la señal del *reranker*, **τ = 0,630 sin δ** domina a la configuración vigente en los dos ejes:
triplica la cobertura (de 21,0 % a 65,3 %) y sube la precisión (de 69,3 % a 86,7 %). δ debe eliminarse,
y con los datos en el orden correcto la evidencia es aún más fuerte que la publicada: subir δ **baja**
la precisión. El verificador LLM de selección es el mecanismo de indecisión con mejor relación
(+6,9 puntos de precisión por −2,9 de cobertura).

## Reproducir

```bash
python scripts/verificar_calibracion.py   # -> resultados/verificacion_calibracion.json
```

## Procedencia

- `Tukit-Col/tukit-mvp-pipeline@3ef9c2e` (master): `calibration/` (`gold_standard_final.csv`,
  `calibrar_score.py`, `simular_delta.py`, `simular_verificador_seleccion.py`, `tabla_calibracion.csv`,
  `verificador_*_resultados.csv`). La misma carpeta está en `Tukit-Col/Tukit-Poc-Tesis@534c973`
  (`tukit-mvp-pipeline-investigacion/calibration/`, con `resultado_calibracion.json`).
- La sección publicada es `Tukit-Poc-Tesis@534c973`: `documento_maestro/seccion_pipeline_mvp.tex`.
- `Tukit-Col/MS-Busqueda@cd48507`: `data/e2e/e2e_f3_resultados.json` y `scripts/calibracion_resolucion.py`
  (calibración sobre un catálogo sintético).
- `Tukit-Col/FINAL@30cf1b5`: `docs/algoritmos/secciones/05-resolucion.tex` (`tab:auc-prototipo`).
