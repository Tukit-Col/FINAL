### Resumen por algoritmo (listas reales, sin preferencias)

| Algoritmo | Instancias | Tiempo mediano | Tiempo p95 | Tiempo máx. | Memoria pico mediana | HV / HV exacto (media) | HV mín. | Frente exacto | Cobertura del frente exacto |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Enumeración exacta | 65 | 47.7 ms | 8.85 s | 29.30 s | 1.54 MiB | 1.0000 | 1.0000 | 100.0 % | 100.0 % |
| Programación dinámica | 174 | 640 µs | 4.1 ms | 8.7 ms | 0.12 MiB | 1.0000 | 1.0000 | 100.0 % | 100.0 % |
| NSGA-II (producción) | 174 | 242.6 ms | 323.3 ms | 781.5 ms | 0.82 MiB | 0.9981 | 0.9511 | 81.6 % | 94.9 % |
| NSGA-II sin siembra | 174 | 235.5 ms | 306.3 ms | 801.4 ms | 0.81 MiB | 0.8673 | 0.6678 | 6.3 % | 42.5 % |
| Voraz (heurística + escalera) | 174 | 569 µs | 2.0 ms | 4.5 ms | 0.04 MiB | 0.4299 | 0.1113 | 1.1 % | 44.0 % |

DP = enumeración en 65 de 65 listas.

### Iguala el óptimo por escenario (kit proyectado del frente)

| Algoritmo | Ahorrador | Premium | Fan | Presupuesto | Calidad con presupuesto |
|---|---:|---:|---:|---:|---:|
| Programación dinámica | 100.0 % | 100.0 % | 100.0 % | 100.0 % | 100.0 % |
| NSGA-II (producción) | 100.0 % | 100.0 % | 100.0 % | 98.9 % | 100.0 % |
| NSGA-II sin siembra | 94.3 % | 6.3 % | 100.0 % | 18.4 % | 90.6 % |
| Voraz (heurística + escalera) | 100.0 % | 100.0 % | 100.0 % | 86.8 % | 99.1 % |

n por escenario: {'ahorrador': 174, 'premium': 174, 'fan': 157, 'presupuesto': 174}.

### Tiempo y memoria por tamaño (n = líneas decidibles)

| n | Listas | log10 \|E\| mediano | Enumeración | DP | NSGA-II | NSGA-II sin siembra | Voraz | Ternas DP (máx./etapa) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1-10 | 37 | 2.7 | 12.3 ms / 0.56 MiB (37) | 245 µs / 0.04 MiB | 108.8 ms / 0.40 MiB | 121.5 ms / 0.41 MiB | 238 µs / 0.02 MiB | 21 |
| 11-15 | 43 | 4.9 | 968.3 ms / 16.69 MiB (21) | 566 µs / 0.09 MiB | 166.3 ms / 0.62 MiB | 163.0 ms / 0.62 MiB | 450 µs / 0.03 MiB | 44 |
| 16-20 | 57 | 6.2 | 7.72 s / 71.28 MiB (6) | 751 µs / 0.13 MiB | 252.3 ms / 0.85 MiB | 244.2 ms / 0.83 MiB | 658 µs / 0.05 MiB | 54 |
| 21-30 | 21 | 7.4 | 3.17 s / 129.83 MiB (1) | 1.1 ms / 0.16 MiB | 275.4 ms / 0.87 MiB | 269.2 ms / 0.85 MiB | 1.0 ms / 0.06 MiB | 62 |
| 31-64 | 16 | 12.8 | — | 4.5 ms / 0.91 MiB | 284.3 ms / 1.00 MiB | 269.1 ms / 0.87 MiB | 2.1 ms / 0.14 MiB | 253 |

### Variabilidad del NSGA-II con 5 semillas (0-4)

| Variante | Corridas | HV medio | HV mín. | Frente exacto | Listas con frente exacto en las 5 semillas |
|---|---:|---:|---:|---:|---:|
| NSGA-II (producción) | 870 | 0.9980 | 0.9511 | 77.5 % | 58.6 % |
| NSGA-II sin siembra | 870 | 0.8612 | 0.6189 | 6.7 % | 3.4 % |

### Hogares sintéticos (varios hijos)

| Hogar | Hijos | n | log10 \|E\| | Ternas DP | DP | NSGA-II | NSGA-II sin siembra | Voraz | HV NSGA-II | HV sin siembra | HV voraz |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2.4|3h|Quinto | 3 | 21 | 6.7 | 114 | 2.1 ms / 0.3 MiB | 259.3 ms / 0.9 MiB | 241.2 ms / 0.8 MiB | 725 µs / 0.0 MiB | 0.9997 | 0.7920 | 0.4730 |
| 1.2|3h|Cuarto | 3 | 30 | 11.1 | 126 | 1.5 ms / 0.3 MiB | 285.1 ms / — | 267.5 ms / — | 1.4 ms / 0.1 MiB | 1.0000 | 0.7331 | 0.7419 |
| 2.4|3h|Octavo | 3 | 39 | 12.8 | 349 | 6.0 ms / 1.2 MiB | 295.2 ms / — | 274.6 ms / — | 1.9 ms / 0.1 MiB | 0.9791 | 0.6636 | 0.4782 |
| 2.11|3h|Quinto | 3 | 40 | 15.9 | 366 | 9.2 ms / 1.7 MiB | 282.0 ms / 1.1 MiB | 272.7 ms / 0.9 MiB | 3.1 ms / 0.2 MiB | 0.9322 | 0.7041 | 0.1971 |
| 2.9|3h|Segundo | 3 | 48 | 15.8 | 248 | 6.5 ms / 1.4 MiB | 317.7 ms / — | 305.5 ms / — | 3.1 ms / 0.2 MiB | 0.9729 | 0.6741 | 0.1556 |
| 2.9|5h|Once | 5 | 59 | 18.8 | 431 | 14.7 ms / 2.6 MiB | 355.3 ms / — | 344.0 ms / — | 4.3 ms / 0.3 MiB | 0.9432 | 0.6127 | 0.2734 |
| 2.11|4h|Cuarto | 4 | 60 | 23.4 | 546 | 19.1 ms / 3.7 MiB | 351.4 ms / 1.6 MiB | 346.5 ms / 1.2 MiB | 7.2 ms / 0.4 MiB | 0.9291 | 0.6423 | 0.1949 |
| 2.13|2h|Octavo | 2 | 68 | 24.1 | 495 | 19.0 ms / 3.7 MiB | 391.4 ms / — | 374.9 ms / — | 6.9 ms / 0.5 MiB | 0.9377 | 0.6489 | 0.3543 |
| 2.3|5h|Once | 5 | 78 | 28.5 | 1162 | 35.9 ms / 6.6 MiB | 426.3 ms / — | 435.4 ms / — | 9.4 ms / 0.6 MiB | 0.9148 | 0.5604 | 0.5381 |
| 2.3|6h|Cuarto | 6 | 80 | 27.1 | 1515 | 45.6 ms / 8.4 MiB | 439.4 ms / 2.0 MiB | 421.2 ms / 1.4 MiB | 12.7 ms / 0.6 MiB | 0.8786 | 0.5832 | 0.5801 |
| 2.9|7h|Primero | 7 | 90 | 26.9 | 728 | 40.5 ms / 7.5 MiB | 471.2 ms / — | 459.2 ms / — | 9.2 ms / 0.7 MiB | 0.9023 | 0.5808 | 0.1366 |
| 2.6|8h|Cuarto | 8 | 108 | 37.0 | 1680 | 114.5 ms / 19.0 MiB | 547.7 ms / — | 523.4 ms / — | 15.7 ms / 1.2 MiB | 0.8348 | 0.5472 | 0.2085 |
| 2.14|7h|Cuarto | 7 | 110 | 36.5 | 1994 | 118.5 ms / 22.5 MiB | 562.3 ms / 3.1 MiB | 532.8 ms / 1.9 MiB | 18.3 ms / 1.3 MiB | 0.8340 | 0.5667 | 0.3157 |
| 2.9|6h|Cuarto | 6 | 119 | 39.4 | 1517 | 92.1 ms / 16.4 MiB | 592.2 ms / — | 569.0 ms / — | 18.9 ms / 1.3 MiB | 0.8833 | 0.5346 | 0.2904 |
| 2.13|3h|Cuarto | 3 | 133 | 43.9 | 1921 | 124.7 ms / 22.8 MiB | 654.8 ms / — | 627.3 ms / — | 23.6 ms / 1.6 MiB | 0.8885 | 0.5441 | 0.4435 |
| 2.9|8h|Cuarto | 8 | 141 | 45.7 | 2097 | 157.0 ms / 25.9 MiB | 686.5 ms / 3.8 MiB | 657.1 ms / 2.1 MiB | 25.8 ms / 1.6 MiB | 0.8198 | 0.5107 | 0.2596 |
| 2.8|7h|Primero | 7 | 143 | 50.6 | 1400 | 110.0 ms / 19.6 MiB | 703.9 ms / — | 657.2 ms / — | 30.7 ms / 2.0 MiB | 0.8825 | 0.5434 | 0.1678 |
| 2.13|4h|Cuarto | 4 | 170 | 57.1 | 3406 | 264.8 ms / 47.6 MiB | 812.5 ms / — | 766.6 ms / — | 38.2 ms / 2.4 MiB | 0.6678 | 0.4725 | 0.4254 |
| 2.13|5h|Once | 5 | 195 | 67.5 | 5290 | 473.7 ms / 95.3 MiB | 925.1 ms / 7.0 MiB | 882.0 ms / 3.1 MiB | 51.9 ms / 3.9 MiB | 0.7013 | 0.4778 | 0.4540 |
| 2.13|5h|Cuarto | 5 | 205 | 69.1 | 4955 | 575.8 ms / 95.2 MiB | 963.3 ms / — | 901.6 ms / — | 58.2 ms / 4.2 MiB | 0.6305 | 0.4634 | 0.4200 |
| 2.13|6h|Primero | 6 | 224 | 79.4 | 9141 | 898.6 ms / 174.4 MiB | 1.05 s / — | 1.03 s / — | 69.7 ms / 4.9 MiB | 0.7180 | 0.4402 | 0.4745 |
| 2.13|6h|Cuarto | 6 | 238 | 81.2 | 6184 | 705.4 ms / 134.8 MiB | 1.11 s / 8.8 MiB | 1.02 s / 3.4 MiB | 74.9 ms / 5.4 MiB | 0.5920 | 0.4596 | 0.4050 |
| 2.13|7h|Cuarto | 7 | 275 | 94.2 | 7910 | 1.08 s / 190.8 MiB | 1.33 s / — | 1.19 s / — | 132.2 ms / 6.8 MiB | 0.5857 | 0.4396 | 0.4122 |
| 2.13|8h|Cuarto | 8 | 313 | 107.0 | 11900 | 2.56 s / 297.3 MiB | 1.46 s / 12.6 MiB | 1.32 s / 4.1 MiB | 273.0 ms / 8.4 MiB | 0.6484 | 0.4285 | 0.4440 |

### Exponente empírico b (t ∝ n^b, listas con n ≥ 15 y hogares)

| Algoritmo | b (tiempo) | b (memoria) |
|---|---:|---:|
| Enumeración exacta | -0.95 | 1.98 |
| Programación dinámica | 2.55 | 2.61 |
| NSGA-II (producción) | 0.49 | 0.83 |
| NSGA-II sin siembra | 0.48 | 0.50 |
| Voraz (heurística + escalera) | 1.78 | 1.78 |

Enumeración con |E| ≤ 4.096 (lo que produccion enumera): máximo 335.3 ms.
