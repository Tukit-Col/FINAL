# Resultados del benchmark Laya contra NSGA-II

Las salidas que cita el [informe](../reporte-benchmark-laya-nsga.md), tal como quedaron en la corrida
del 4 de octubre de 2026. Las escriben los scripts de [`ensayos/bench_laya/`](../../../ensayos/bench_laya/);
volver a correrlos las sobrescribe.

| Archivo | Qué es | Lo escribe |
|---|---|---|
| `resumen.json` | Métricas agregadas por escenario y competidor: las cifras de las tablas del informe | `evaluar.py` |
| `resultados.json.gz` | El detalle por lista, escenario y competidor, más la variabilidad entre semillas y los puntos del frente dominados. Su campo `resumen` es `resumen.json` | `evaluar.py` |
| `tablas.md` | Las tablas del informe, generadas desde `resumen` | `graficas.py` |
| `fig_optimo.png` | Porcentaje de listas en que cada competidor iguala el óptimo | `graficas.py` |
| `fig_frente_2.14_Jardin.png` | El frente del NSGA-II, los kits de Laya y el óptimo con presupuesto en una lista típica | `graficas.py "2.14\|Jardin"` |
| `tiempos_nsga.json`, `tiempos_laya_gpu.json` | Tiempos medidos con la máquina sola | `tiempos.py nsga`, `tiempos.py laya` |
| `cordura.json`, `cordura_variantes.json` | La prueba de cordura de Laya: aciertos por versión y forma de preguntar | `cordura.py`, `cordura_variantes.py` |

Los datos de entrada no están aquí sino con el código, porque son lo que los scripts consumen:
`instancias.json.gz` (la foto del catálogo y las 175 listas), `escenarios.json`, `nsga.json.gz`
(las corridas del NSGA-II con cinco semillas) y `laya_A.json` a `laya_D.json` (las respuestas de
Laya, que solo se regeneran con GPU).
