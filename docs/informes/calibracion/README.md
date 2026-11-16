# Calibración del optimizador (OE4)

Esta carpeta guarda la evidencia de cada constante del optimizador
(`servicios/inteligencia/tukit_inteligencia/optimizador.py` y `modelos/base.py`)
y la sección `optimizacion.tex` de la Memoria que la presenta. Los scripts están
en `ensayos/calibracion/`; cada uno escribe un JSON aquí y ningún número del
`.tex` se escribe a mano.

## Cómo reproducir cada resultado

Todos los comandos se corren desde la raíz del repositorio, en este orden. Las
listas salen de `ensayos/bench_laya/instancias.json.gz` (foto fija del catálogo),
así que no hace falta la base de datos salvo para `tau.py`.

| Paso | Comando | Salida | Tiempo aprox. |
|---|---|---|---|
| 1. Pesos P21 | `uv run python ensayos/calibracion/pesos_p21.py` | `pesos_p21.json` | segundos |
| 2. Umbral de enumeración | `uv run python ensayos/calibracion/umbral.py` | `umbral.json` | ~30 min (la enumeración de 2^16 y 2^17 tarda minutos) |
| 3. Población y generaciones | `uv run python ensayos/calibracion/calibrar_nsga.py --procesos 8 --pliegues 5 --semillas-cv 2 --semillas-prueba 5` | `calibracion_nsga.json` | ~40 min |
| 4. Umbral con la configuración elegida | `uv run python ensayos/calibracion/umbral_elegida.py` | `umbral_elegida.json` | ~1 min |
| 5. τ | `uv run python ensayos/calibracion/tau.py` | `tau.json` | segundos (lee la base `tukit_inteligencia` si está arriba) |
| 6. Sensibilidad de los pesos | `uv run python ensayos/calibracion/sensibilidad.py` | `sensibilidad.json` | minutos |
| 7. Hipervolumen por perfil | `uv run python ensayos/calibracion/hipervolumen_prueba.py` | `hipervolumen_prueba.json` | minutos |
| 8. Figuras | `uv run python ensayos/calibracion/graficas.py` | `*.png` | segundos |
| 9. Cifras y tablas del `.tex` | `uv run python ensayos/calibracion/cifras_tex.py` | `cifras.tex`, `tabla_*.tex` | segundos |

`extraer_p21.py RUTA_AL_XLSX` regenera `ensayos/calibracion/datos/p21_rankings.csv`
desde el Excel de la encuesta (necesita `openpyxl`); el CSV solo guarda los
órdenes de la P21, sin estrato, correo ni nombre.

Los pasos 2 y 3 aceptan `--rapido` para una versión de humo (salidas
`umbral_rapido.json` y `calibracion_nsga_rapido.json`), que no se usa en el texto.

Los pasos 3 y 6 leen la partición y la configuración de `calibracion_nsga.json`,
y el paso 4 corre después de fijar los factores elegidos. Las semillas son fijas
(`nucleo.SEMILLA_BASE = 20261101`).

**Rejilla reducida, declarada.** El paso 3 usa 2 semillas por lista en la
validación cruzada (no 3) y 5 en la prueba (no 30), para que la corrida completa
quepa en unos 40 minutos. La rejilla de factores sí es la completa (4 × 4).

### Compilar la sección sola

```sh
cd docs/informes/calibracion
mkdir -p /tmp/optcal && cp optimizacion.tex cifras.tex tabla_*.tex *.png optimizacion.bib /tmp/optcal/
cp ~/Documents/university/TUKIT/memoria-final/bib/tukit.bib /tmp/optcal/  # deb_fast_2002, blank_pymoo_2020, zitzler_multiobjective_1999
cd /tmp/optcal && cat > prueba.tex <<'EOF'
\documentclass{article}
\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}
\usepackage[spanish,es-noshorthands,es-tabla]{babel}
\usepackage{amsmath,amssymb,booktabs,graphicx,enumitem,algorithm,algpseudocode,hyperref,cleveref}
\input{cifras.tex}
\begin{document}
\input{optimizacion.tex}
\bibliographystyle{plain}\bibliography{optimizacion,tukit}
\end{document}
EOF
pdflatex prueba && bibtex prueba && pdflatex prueba && pdflatex prueba
```

En la Memoria basta con `\input{cifras.tex}` en el preámbulo y
`\input{optimizacion.tex}` donde va la sección, con las referencias de
`optimizacion.bib` agregadas a `tukit.bib`.

## Máquina

Todos los tiempos se midieron en esta máquina, en serie (los hipervolúmenes, que
no dependen del tiempo, corren en paralelo):

- CPU: Apple M4 (`sysctl -n machdep.cpu.brand_string`), 10 núcleos (`hw.ncpu`)
- RAM: 32 GiB (`hw.memsize` = 34359738368)
- macOS 27.0.1, Python 3.13.11, numpy 2.5.3, pymoo 0.6.2

Cada JSON repite estos datos en su campo `hardware`.

## Limitaciones declaradas

1. **Preferencias declaradas.** Los pesos salen de la P21 (n = 60): lo que los
   acudientes dicen, no lo que compran, y la muestra es sobre todo de estrato 4.
   Los intervalos de precio, marca exigida y calidad se solapan.
2. **Corpus pequeño y agrupado.** 174 listas de 17 colegios (175 instancias en el
   benchmark, una sin líneas decidibles). La partición es por colegio y el
   conjunto de prueba tiene pocos colegios.
3. **τ no se puede calibrar.** La tabla `transicion_resolucion` tiene 1265
   resoluciones, todas automáticas y todas con parecido 1,0; ninguna es humana.
   La única fuente humana es la curaduría de 4 anotadores con una pauta común, que se une con 405
   renglones de 3 colegios (391 de uno solo). τ queda en 0,75 y se declara sin
   calibrar (`tau.json`).
4. **No existe un kit óptimo de referencia.** El hipervolumen mide la
   optimización; si el kit le sirve al acudiente lo mide la validación con
   usuarios (OE5).
5. **Calibración retrospectiva.** Se usaron listas ya recolectadas. El conjunto
   de prueba se apartó antes de mirar nada y se usó una sola vez.
6. **Una sola máquina.** Los tiempos son de un Apple M4 con 32 GiB; en otra
   máquina cambian las constantes del ajuste y el punto de cruce.
