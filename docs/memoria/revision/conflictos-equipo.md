# Conflictos entre la versión del equipo y las cifras vigentes

Regla: gana la cifra vigente (`cifras_calibracion.tex`, `HECHOS_CANONICOS_DOCS.md`, `PUNTO_EQUILIBRIO.md`). Aquí se anota cada discrepancia y qué se hizo.

## Validación financiera (Daniel, `resultados.tex` del zip, l. 388-470)

Decisión de la usuaria (6-nov): se queda la estructura de Daniel (proyección a tres años + balance) y se recalcula con el escenario base vigente. Script: `revision/cierre-final/proyeccion.py`, que importa las constantes de `docs/negocio/punto_equilibrio.py`.

| Dato | Daniel | Recalculado | Nota |
|---|---:|---:|---|
| Ticket | $180.000 (supuesto) | $609.343 (medido, 13 kits canónicos) | |
| Comisión por kit (15 %) | $27.000 | $91.401 | |
| Costos variables por kit | $7.500 (Wompi + IA) | $62.049 (Wompi + IVA, IA, domicilio $33.000, CAC $8.000) | Daniel no contaba la logística ni el CAC |
| Contribución por kit | $19.500 | $29.353 | |
| Equilibrio año 1 (fijos $15 M) | ~770 | 512 | |
| Kits año 1/2/3 | 1.500 / 8.000 / 25.000 | igual | supuesto del equipo, sin fuente |
| Fijos año 1/2/3 | 15 / 40 / 120 M | igual | supuesto del equipo |
| Resultado operativo (M) | 14,25 / 116,00 / 367,50 | 29,03 / 194,82 / 613,82 | |
| Antes de impuestos (M) | −10,95 / 108,30 / 359,80 | 3,83 / 187,12 / 606,12 | |
| Efectivo al cierre (M) | 28,25 / 144,25 / 511,75 | 43,03 / 237,85 / 851,67 | |
| VPN al 20 % | ~235 M | 444,71 M | la fórmula reproduce 235,10 con las cifras de Daniel |

Observación: con el ticket de $180.000 de Daniel y la logística y el CAC incluidos, la contribución sería de −$21.509 por kit. Por eso no se puede usar su ticket con los costos completos.
