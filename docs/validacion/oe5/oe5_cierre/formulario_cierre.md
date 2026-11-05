# TUKIT: su opinión después de la prueba (3 minutos)

Cuestionario de cierre de OE5 para los seis acudientes de la ronda del 2 y 3 de noviembre. Aplica los instrumentos preregistrados (SUS, RTLX tradicional y con TUKIT, NPS) por formulario en línea después de la sesión. El SEQ por tarea no se incluye: se mide justo después de cada tarea y no se puede reconstruir días después.

## Cómo crearlo y enviarlo
1. Abra script.google.com con la cuenta del proyecto, cree un proyecto nuevo y pegue `formulario_cierre_GoogleForms.gs`.
2. Ejecute `crearCuestionarioCierre` y acepte los permisos.
3. En **Ver > Registros** salen el enlace de edición y seis enlaces prellenados, uno por código (ACU-01 a ACU-06). Envíe a cada acudiente el suyo según la tabla de códigos (local, no en el repo).
4. Al cerrar: **Respuestas > Descargar respuestas (.csv)**. No cambie el orden de las preguntas.
5. `python docs/validacion/oe5/oe5_cierre/unir_cierre.py <descarga>.csv` y luego `uv run python docs/validacion/analisis_oe5.py docs/validacion/oe5/oe5_cierre/datos_oe5.csv`.
6. Las cifras van a `oe5.tex` y `conclusiones.tex` (los dos `\pendienteEvidencia` del formulario).

## Mensaje para WhatsApp
> ¡Hola! Otra vez gracias por probar TUKIT 🙌 Nos falta un último pasito para la tesis: un formulario de 3 minutos con su opinión. Es este enlace: [enlace]. ¡Mil gracias!

## Contenido
- Código (prellenado) y autorización de uso sin nombre.
- **1. SUS** (Brooke, 1996), 10 ítems, 1–5, en español, alternando positivos y negativos.
- **2. RTLX de la compra habitual**: exigencia mental, física, presión de tiempo, resultado (0 = perfecto), esfuerzo, frustración; 0–10.
- **3. RTLX de la prueba con TUKIT**: las mismas seis escalas.
- **4. NPS** 0–10 y un "¿por qué?" opcional.

## Puntuación (la hace `analisis_oe5.py`)
- SUS: ítems impares `x − 1`, pares `5 − x`, suma × 2,5 → 0–100.
- RTLX: media de las seis escalas × 10 → 0–100, por condición. C2 compara TUKIT contra habitual.
- NPS: % de 9–10 menos % de 0–6.
