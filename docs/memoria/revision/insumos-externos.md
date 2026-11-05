# Insumos externos para la consolidación (5-nov-2026, conductora)

No es un hallazgo de revisor; lo aplica la conductora junto con R1-R4.

## Tukit-Benchmarks/06-optimizacion (commit 8d917ae, 3-nov)
- Mide el mismo optimizador de la memoria: FINAL@a8f09c7 en validacion/oe5; `optimizador.py` sin cambios entre a8f09c7, b6b6fe7 y HEAD.
- `fig_opt_tiempo.pdf` y `fig_opt_memoria.pdf` del zip de Juan son idénticos byte a byte a `figuras/` del repo; se generan con `scripts/graficas.py` desde `resultados/*.json.gz` versionados.
- Cifras confirmadas en `resultados/tablas.md`, `RESULTADOS.md` y `resumen.json`:
  - PD = enumeración en 65/65 listas, más 1.000 instancias aleatorias (test).
  - Medianas en listas reales: PD 0,64 ms y 0,12 MiB; NSGA-II 243 ms y 0,82 MiB.
  - Exponentes: memoria PD n^2,61, memoria NSGA-II n^0,83 (30 puntos), tiempo NSGA-II n^0,49.
  - Hogar de 8 hijos y 313 líneas: PD 2,56 s y 297 MiB; NSGA-II 1,46 s y 12,6 MiB.
  - Con siembra: Ahorrador, Premium y Fan 100 % (Fan sobre 157 listas), presupuesto 98,9 % (172/174), HV medio 0,9981, mínimo 0,9511, frente exacto 81,6 %.
  - Sin siembra: Premium 6,3 %, presupuesto 18,4 %, HV 0,867.
- Límites que hay que declarar:
  - Tiempo y memoria con una sola semilla.
  - La memoria de NSGA-II se midió en 1 de cada 5 listas.
  - Postgres, Redis y RabbitMQ estaban activos durante la medición, así que los tiempos son indicativos.
  - Son 175 listas, pero 174 tienen frente.
  - Hay 5 semillas solo para la calidad: HV 0,9980.
- Acción: agregar las dos figuras y el párrafo de PD frente a NSGA-II en Optimización (Resultados), citando el repo y el commit.

## Tukit-QA (informe de fases 7-9 y trazabilidad, 5-nov)
- **Hallazgos:** hay 85 vigentes (17 H-C, 57 H-A, 11 H-B) y 10 H-A cerrados (`trazabilidad/hallazgos.md`). La memoria dice 59 (contados por los xfail de una rama). Hay que reemplazar esa cifra por la del repo QA y regenerar `tab:hallazgos-abiertos` desde `hallazgos.md`, con severidad y estado.
- **Carga (B), 5-nov, en Windows 11 con WSL2, 4 CPU:**
  - 25 ensayos: 14 cumplen, 10 no cumplen y 1 no concluyente.
  - L-02: el catálogo se satura desde 30 usuarios, con P95 de 1.200 ms.
  - L-03 (100 usuarios): P95 de 30 s y 49,9 % de error en la peor ventana.
  - L-06: identidad queda al 0 % unos 4 min cuando cae el catálogo.
  - El propio QA (D-B-11 y D-B-18) dice que no son comparables con Mac ni se deben tomar como definitivos del producto. Falta repetirlos en Mac.
  - Acción: la memoria ya no puede decir que DP-02 "no se midió". Debe decir que se midió en una VM con Windows y que no cumplió desde 30 usuarios, con el límite del entorno declarado. La corrida en Mac de 1 a 20 usuarios (0 errores) se mantiene.
- **Caos:** se agregan CH-09 (la reserva vencida no se libera), CH-24 (la supresión queda propagando, igual que H-A-66) y CH-30 (perder RabbitMQ pierde el aviso de pago).
- **ESC-D4:** la matriz QA dice "no medible por reordenador" (H-C-10) y B mide un P50 de 1.365 ms extremo a extremo frente a 8 s. Nuestro p95 de 0,31 s es solo la etapa del optimizador, así que hay que distinguir ambos alcances en el texto.
- **Pruebas:** la línea base de oe5 tiene 2.616 pruebas que pasan (la memoria dice 2.542, de la corrida del 2-nov) y la suite completa sin stack, 5.099. Hay que citar cada cifra con su commit.
- **Cobertura global:** 77,36 %.
