# Figuras nuevas (2026-11-06)

Todas usan la paleta de `img/arquitectura/c4-contenedores.tex`. No se editó ningún `.tex` de secciones: el cableado queda para el orquestador.

## 1. Vista de contexto C4 nivel 1

- Archivo: `img/arquitectura/c4-contexto.tex` (compila sola en tikz con arrows.meta y shapes.geometric; ancho nativo unos 23 cm).
- Reemplaza `img/modelo/contexto.jpg`. Conserva las 3 personas del JPG reunidas en 2 (acudiente; equipo de Tukit = administrador + operador de última milla), las 8 flechas de entrada y salida de cada persona, y los sistemas externos agrupados por función (tiendas, pasarela de pago, lectura de listas, canales de aviso, mapas) con la información de cada flecha.
- Dónde va: `sections/disenoSolucion.tex` (línea ~126) y `sections/anexo_figuras.tex` (línea ~8; ambas llevan hoy `\label{fig:c4-contexto}`: dejar el label en una sola, la del cuerpo, y quitar la figura duplicada del anexo como pidió la autora).
- Texto vecino (disenoSolucion.tex:122): dice "de izquierda a derecha" y "a su derecha"; coincide con la figura nueva (personas a la izquierda, externos a la derecha). Menciona Gemini, Wompi, canales de aviso y tiendas; Google Maps también está dibujado, conviene añadirlo a esa frase.

```latex
\begin{figure}[!htb]
\centering
\resizebox{\textwidth}{!}{\input{img/arquitectura/c4-contexto.tex}}
\caption[Vista de contexto: Tukit frente a sus actores y sistemas externos.]{Vista de contexto
(C4 nivel 1): Tukit como un solo sistema frente a sus actores (el padre es el acudiente) y a los
sistemas externos, agrupados por función. Cada flecha lleva la información que pasa entre las partes.}
\label{fig:c4-contexto}
\end{figure}
```

## 2. Diagrama del proceso de calibración

- Archivo: `img/arquitectura/calibracion-flujo.tex` (7 cajas; todas las cifras vienen de macros `\cal*`; requiere `cifras_calibracion.tex` cargado, que ya está en el documento).
- Dónde va: `sections/optimizacion.tex`, párrafo "Calibración de las constantes", justo antes del párrafo que empieza "Las fórmulas de partida".
- Referencias que usa y deben existir: `fig:calopt-umbral`, `tab:calopt-umbral`, `fig:calopt-rejilla`, `tab:calopt-rejilla`, `fig:calopt-sensibilidad`, `tab:calopt-sensibilidad`, `fig:calopt-hv`, `tab:calopt-hv`, `fig:tau-clasificacion`, `sec:recuperacion`, `fig:calibracion-graficas` (las ocho primeras viven en el anexo de calibración, que se compila en el mismo documento).

```latex
\begin{figure}[!htb]
\centering
\resizebox{\textwidth}{!}{\input{img/arquitectura/calibracion-flujo.tex}}
\caption[Proceso de calibración del optimizador.]{Proceso de calibración del optimizador, de los
datos a la evaluación en las listas de prueba. Cada caja trae su cifra principal y la figura o tabla
donde se ve.}
\label{fig:calibracion-flujo}
\end{figure}
```

## 3. Gráficas de calibración (vectoriales)

- Script: `ensayos/calibracion/graficas.py` (paleta C4, serif con mathtext cm, PNG a 200 ppp y PDF; datos sin cambio). Ejecutado con `uv run python ensayos/calibracion/graficas.py`.
- PDF y PNG copiados a `img/calibracion/`: `umbral`, `rejilla`, `sensibilidad`, `hipervolumen_prueba`, `pesos_p21`, `tau_clasificacion`. La fuente es CMU Serif si está instalada, si no DejaVu Serif (las cifras y los símbolos salen en Computer Modern por mathtext).
- Anexo: cambiar `.png` por `.pdf` en los `\includegraphics` de `sections/anexo_calibracion.tex` (umbral, rejilla, sensibilidad, hipervolumen_prueba) y poner `width=\linewidth`; los tamaños ya están pensados para ancho de página A4.
- Cuerpo (opcional): figura compuesta con las cuatro, sin paquetes nuevos (usa minipage). Va en `optimizacion.tex` tras el párrafo "Por último, en las ... listas de los colegios de prueba", y sustituye a la mención solo por el anexo.

```latex
\begin{figure}[!htb]
\centering
\includegraphics[width=\linewidth]{img/calibracion/umbral.pdf}\\[2mm]
\begin{minipage}[t]{0.49\linewidth}\centering
\includegraphics[width=\linewidth]{img/calibracion/rejilla.pdf}\end{minipage}\hfill
\begin{minipage}[t]{0.49\linewidth}\centering
\includegraphics[width=\linewidth]{img/calibracion/sensibilidad.pdf}\end{minipage}\\[2mm]
\includegraphics[width=0.55\linewidth]{img/calibracion/hipervolumen_prueba.pdf}
\caption[Gráficas de la calibración del optimizador.]{Calibración del optimizador. Arriba: tiempo de
la enumeración exacta y de NSGA-II según el tamaño del espacio, y calidad del frente. Centro,
izquierda: rejilla de población y generaciones; derecha: estabilidad del kit bajo la perturbación de
Dirichlet. Abajo: hipervolumen relativo al frente exacto en las listas de prueba.}
\label{fig:calibracion-graficas}
\end{figure}
```

Costo en páginas: el cuerpo está en 59 de 60; una figura de página casi completa puede pasar el límite. Si ocurre, usar solo `umbral.pdf` más la rejilla, o dejarlas en el anexo y poner solo el diagrama del punto 2.

## Verificación

Compilación de prueba en `/tmp/ctx` (article con tikz y `\input{cifras_calibracion}`): ambas TikZ compilan sin errores; las referencias salen como "??" solo porque la prueba no incluye el anexo. Revisadas a 80-110 ppp: sin superposición; etiquetas con fill=white y multilínea con align.
