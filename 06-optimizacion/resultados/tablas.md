### Resumen por algoritmo (listas reales, sin preferencias)

| Algoritmo | Instancias | Tiempo mediano | Tiempo p95 | Tiempo máx. | Memoria pico mediana | HV / HV exacto (media) | HV mín. | Frente exacto | Cobertura del frente exacto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Enumeración exacta | 65 | 47.7 ms | 8.85 s | 29.30 s | 1.54 MiB | 1.0000 | 1.0000 | 100.0 % | 100.0 % |
| Programación dinámica | 174 | 640 µs | 4.1 ms | 8.7 ms | 0.12 MiB | 1.0000 | 1.0000 | 100.0 % | 100.0 % |
| NSGA-II (producción) | 174 | 995.6 ms | 1.61 s | 3.76 s | 1.79 MiB | 0.9998 | 0.9936 | 89.7 % | 98.3 % |
| NSGA-II sin siembra | 174 | 1.02 s | 1.64 s | 4.74 s | 1.79 MiB | 0.9015 | 0.6900 | 7.5 % | 54.1 % |
| Voraz (heurística + escalera) | 174 | 569 µs | 2.0 ms | 4.5 ms | 0.04 MiB | 0.4299 | 0.1113 | 1.1 % | 44.0 % |

DP = enumeración en 65 de 65 listas.

### Iguala el óptimo por escenario (kit proyectado del frente)

| Algoritmo | Ahorrador | Premium | Fan | Presupuesto | Calidad con presupuesto |
|---|---:|---:|---:|---:|---:|
| Programación dinámica | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 100.0 % |
| NSGA-II (producción) | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 100.0 % |
| NSGA-II sin siembra | 98.9 % | 7.5 % | 100.0 % | 29.3 % | 93.6 % |
| Voraz (heurística + escalera) | 100.0 % | 100.0 % | 100.0 % | 86.8 % | 99.1 % |

n por escenario: {'ahorrador': 174, 'premium': 174, 'fan': 157, 'presupuesto': 174}.

### Tiempo y memoria por tamaño (n = líneas decidibles)

| n | Listas | log10 \|E\| mediano | Enumeración | DP | NSGA-II | NSGA-II sin siembra | Voraz | Ternas DP (máx./etapa) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-10 | 37 | 2.7 | 12.3 ms / 0.56 MiB (37) | 245 µs / 0.04 MiB | 463.0 ms / 0.78 MiB | 528.7 ms / 0.78 MiB | 238 µs / 0.02 MiB | 21 |
| 11-15 | 43 | 4.9 | 968.3 ms / 16.69 MiB (21) | 566 µs / 0.09 MiB | 677.1 ms / 1.36 MiB | 738.4 ms / 1.36 MiB | 450 µs / 0.03 MiB | 44 |
| 16-20 | 57 | 6.2 | 7.72 s / 71.28 MiB (6) | 751 µs / 0.13 MiB | 1.10 s / 1.90 MiB | 1.10 s / 1.89 MiB | 658 µs / 0.05 MiB | 54 |
| 21-30 | 21 | 7.4 | 3.17 s / 129.83 MiB (1) | 1.1 ms / 0.16 MiB | 1.19 s / 1.96 MiB | 1.21 s / 1.95 MiB | 1.0 ms / 0.06 MiB | 62 |
| 31-64 | 16 | 12.8 | — | 4.5 ms / 0.91 MiB | 1.18 s / 2.06 MiB | 1.12 s / 2.05 MiB | 2.1 ms / 0.14 MiB | 253 |

### Variabilidad del NSGA-II con 5 semillas (0-4)

| Variante | Corridas | HV medio | HV mín. | Frente exacto | Listas con frente exacto en las 5 semillas |
|---|---:|---:|---:|---:|---:|
| NSGA-II (producción) | 870 | 0.9998 | 0.9911 | 92.2 % | 89.7 % |
| NSGA-II sin siembra | 870 | 0.8967 | 0.6900 | 7.6 % | 2.9 % |

### Hogares sintéticos (varios hijos)

| Hogar | Hijos | n | log10 \|E\| | Ternas DP | DP | NSGA-II | NSGA-II sin siembra | Voraz | HV NSGA-II | HV sin siembra | HV voraz |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.4|3h|Quinto | 3 | 21 | 6.7 | 114 | 2.1 ms / 0.3 MiB | 1.21 s / 2.0 MiB | 1.38 s / 1.9 MiB | 725 µs / 0.0 MiB | 1.0000 | 0.8946 | 0.4730 |
| 1.2|3h|Cuarto | 3 | 30 | 11.1 | 126 | 1.5 ms / 0.3 MiB | 1.17 s / — | 1.33 s / — | 1.4 ms / 0.1 MiB | 1.0000 | 0.7508 | 0.7419 |
| 2.4|3h|Octavo | 3 | 39 | 12.8 | 349 | 6.0 ms / 1.2 MiB | 1.22 s / — | 1.16 s / — | 1.9 ms / 0.1 MiB | 0.9986 | 0.7130 | 0.4782 |
| 2.11|3h|Quinto | 3 | 40 | 15.9 | 366 | 9.2 ms / 1.7 MiB | 1.15 s / 2.1 MiB | 1.32 s / 2.1 MiB | 3.1 ms / 0.2 MiB | 0.9793 | 0.7402 | 0.1971 |
| 2.9|3h|Segundo | 3 | 48 | 15.8 | 248 | 6.5 ms / 1.4 MiB | 1.33 s / — | 1.47 s / — | 3.1 ms / 0.2 MiB | 0.9954 | 0.7389 | 0.1556 |
| 2.9|5h|Once | 5 | 59 | 18.8 | 431 | 14.7 ms / 2.6 MiB | 1.89 s / — | 1.90 s / — | 4.3 ms / 0.3 MiB | 0.9930 | 0.6614 | 0.2734 |
| 2.11|4h|Cuarto | 4 | 60 | 23.4 | 546 | 19.1 ms / 3.7 MiB | 1.58 s / 2.8 MiB | 1.81 s / 2.4 MiB | 7.2 ms / 0.4 MiB | 0.9756 | 0.6567 | 0.1949 |
| 2.13|2h|Octavo | 2 | 68 | 24.1 | 495 | 19.0 ms / 3.7 MiB | 1.82 s / — | 1.82 s / — | 6.9 ms / 0.5 MiB | 0.9739 | 0.6931 | 0.3543 |
| 2.3|5h|Once | 5 | 78 | 28.5 | 1162 | 35.9 ms / 6.6 MiB | 2.04 s / — | 1.79 s / — | 9.4 ms / 0.6 MiB | 0.9600 | 0.6104 | 0.5381 |
| 2.3|6h|Cuarto | 6 | 80 | 27.1 | 1515 | 45.6 ms / 8.4 MiB | 1.96 s / 3.3 MiB | 1.88 s / 2.7 MiB | 12.7 ms / 0.6 MiB | 0.9520 | 0.6309 | 0.5801 |
| 2.9|7h|Primero | 7 | 90 | 26.9 | 728 | 40.5 ms / 7.5 MiB | 2.37 s / — | 2.11 s / — | 9.2 ms / 0.7 MiB | 0.9555 | 0.6359 | 0.1366 |
| 2.6|8h|Cuarto | 8 | 108 | 37.0 | 1680 | 114.5 ms / 19.0 MiB | 2.53 s / — | 2.48 s / — | 15.7 ms / 1.2 MiB | 0.9165 | 0.6132 | 0.2085 |
| 2.14|7h|Cuarto | 7 | 110 | 36.5 | 1994 | 118.5 ms / 22.5 MiB | 2.86 s / 5.0 MiB | 2.43 s / 3.7 MiB | 18.3 ms / 1.3 MiB | 0.9154 | 0.6074 | 0.3157 |
| 2.9|6h|Cuarto | 6 | 119 | 39.4 | 1517 | 92.1 ms / 16.4 MiB | 3.08 s / — | 2.75 s / — | 18.9 ms / 1.3 MiB | 0.9489 | 0.5713 | 0.2904 |
| 2.13|3h|Cuarto | 3 | 133 | 43.9 | 1921 | 124.7 ms / 22.8 MiB | 3.28 s / — | 2.85 s / — | 23.6 ms / 1.6 MiB | 0.9461 | 0.5835 | 0.4435 |
| 2.9|8h|Cuarto | 8 | 141 | 45.7 | 2097 | 157.0 ms / 25.9 MiB | 3.04 s / 5.9 MiB | 3.30 s / 4.3 MiB | 25.8 ms / 1.6 MiB | 0.9294 | 0.5517 | 0.2596 |
| 2.8|7h|Primero | 7 | 143 | 50.6 | 1400 | 110.0 ms / 19.6 MiB | 3.05 s / — | 2.89 s / — | 30.7 ms / 2.0 MiB | 0.9518 | 0.5515 | 0.1678 |
| 2.13|4h|Cuarto | 4 | 170 | 57.1 | 3406 | 264.8 ms / 47.6 MiB | 3.43 s / — | 3.29 s / — | 38.2 ms / 2.4 MiB | 0.9095 | 0.5335 | 0.4254 |
| 2.13|5h|Once | 5 | 195 | 67.5 | 5290 | 473.7 ms / 95.3 MiB | 3.83 s / 10.0 MiB | 3.69 s / 6.1 MiB | 51.9 ms / 3.9 MiB | 0.8988 | 0.5085 | 0.4540 |
| 2.13|5h|Cuarto | 5 | 205 | 69.1 | 4955 | 575.8 ms / 95.2 MiB | 4.03 s / — | 3.89 s / — | 58.2 ms / 4.2 MiB | 0.8810 | 0.5392 | 0.4200 |
| 2.13|6h|Primero | 6 | 224 | 79.4 | 9141 | 898.6 ms / 174.4 MiB | 4.30 s / — | 4.34 s / — | 69.7 ms / 4.9 MiB | 0.8716 | 0.4962 | 0.4745 |
| 2.13|6h|Cuarto | 6 | 238 | 81.2 | 6184 | 705.4 ms / 134.8 MiB | 4.56 s / 12.2 MiB | 4.46 s / 6.9 MiB | 74.9 ms / 5.4 MiB | 0.8545 | 0.5148 | 0.4050 |
| 2.13|7h|Cuarto | 7 | 275 | 94.2 | 7910 | 1.08 s / 190.8 MiB | 9.63 s / — | 7.89 s / — | 132.2 ms / 6.8 MiB | 0.8615 | 0.5093 | 0.4122 |
| 2.13|8h|Cuarto | 8 | 313 | 107.0 | 11900 | 2.56 s / 297.3 MiB | 9.03 s / 16.6 MiB | 9.17 s / 8.2 MiB | 273.0 ms / 8.4 MiB | 0.8295 | 0.4528 | 0.4440 |

### Exponente empírico b (t ∝ n^b, listas con n ≥ 15 y hogares)

| Algoritmo | b (tiempo) | b (memoria) |
|---|---:|---:|
| Enumeración exacta | -0.95 | 1.98 |
| Programación dinámica | 2.55 | 2.61 |
| NSGA-II (producción) | 0.50 | 0.65 |
| NSGA-II sin siembra | 0.46 | 0.45 |
| Voraz (heurística + escalera) | 1.78 | 1.78 |

Enumeración con |E| ≤ 4.096 (lo que produccion enumera): máximo 335.3 ms.
