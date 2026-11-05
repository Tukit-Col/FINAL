# Revisión de la memoria con ojos nuevos: plan

> **Para las sesiones revisoras:** usa superpowers:executing-plans sobre **tu** tarea de este plan. Lee solo los archivos que tu tarea lista. **No edites la memoria**: tu única salida es tu archivo de hallazgos. Pasos con casillas (`- [ ]`).

**Objetivo:** que cuatro sesiones nuevas, sin el contexto de quien la escribió, revisen la memoria del trabajo de grado (cuerpo de 60 páginas) por capítulo y por lente. Cada una entrega hallazgos con página, sección, evidencia y severidad. La conductora (la sesión original) consolida, corre un consejo de 5 asesores sobre los hallazgos dudosos y aplica los cambios.

**Arquitectura:** hay cuatro revisores. Los tres primeros se reparten los capítulos siguiendo las 5 partes clásicas de una tesis (introducción, contexto y literatura, metodología, resultados, discusión) y aplican las fases 2, 3 y 4 de la guía: hilo conductor, claridad y visuales, y citas. El cuarto hace la fase 5, el jurado, sobre el documento entero y sin leer los hallazgos de los demás. La conductora no revisa: une los resultados y decide.

**Insumos:** el PDF compilado `docs/memoria/main.pdf`, las fuentes en `docs/memoria/sections/*.tex`, la bibliografía en `docs/memoria/bib/tukit.bib`, la plantilla oficial con su rúbrica en comentarios en `../Formato TG ISIST esp/sections/*.tex` y las cifras canónicas en `docs/entrega/HECHOS_CANONICOS_DOCS.md`.

## Reglas globales (valen para cada tarea)
- **Solo lectura.** No edites ni `.tex` ni `.bib` ni código, no hagas commits, no compiles en `docs/memoria` (otra sesión puede estar compilando). Para ver el PDF: `pdftotext -f N -l M docs/memoria/main.pdf -`.
- **Salida única:** `docs/memoria/revision/hallazgos-<tarea>.md`, con el formato de abajo. Al terminar, responde a la sesión **conductora** con SendMessage: "listo, N hallazgos (A altos)".
- **No reescribas el texto.** Señala el problema y da como máximo una frase de ejemplo. La reescritura la decide la conductora.
- **Página = número impreso en el PDF** ("Página N" al pie, la del cuerpo), más la sección y el archivo `.tex` con su línea.
- **Rúbrica oficial** (Pontificia Universidad Javeriana, Ingeniería de Sistemas, plantilla en `../Formato TG ISIST esp/`):
  - Cuerpo de máximo 60 páginas desde la Introducción; las referencias y los anexos no cuentan.
  - La Descripción general va en pasado, con referencias actualizadas, y "Oportunidad, Problema" tiene máximo 3 páginas.
  - Los Antecedentes no deben ser un glosario.
  - El Análisis del contexto compara la solución con soluciones referenciadas.
  - El Diseño justifica las herramientas con criterios.
  - El Desarrollo relaciona el proceso con la metodología y muestra el producto con capturas.
  - Los Resultados muestran el control de calidad (unidad, funcional, sistema, aceptación) con análisis.
  - Las Conclusiones traen impacto (en ingeniería de sistemas y en lo global, económico, ambiental y social), cumplimiento de objetivos con su porqué, y trabajo futuro.
  - Las referencias usan un solo estándar. Aquí es numérico con natbib, estilo IEEE o similar.
- **Idioma:** español formal y sencillo. El modelo de estilo es `sections/analisisProblema.tex`: conectores lógicos, primero el contexto, definiciones en la misma frase y vocabulario de ingeniería sin adornos.
- **Cifras:** todo número del texto se contrasta con `HECHOS_CANONICOS_DOCS.md`. Si no está allí, se marca como "sin fuente canónica", no como error.
- **Privacidad:** si ves un nombre real de participante, un correo o una dirección en el texto o en una figura, el hallazgo es ALTO.
- **No inventes fuentes.** Si dudas de que una referencia exista, márcala como "verificar"; no afirmes que es falsa sin buscarla. Puedes buscar en la web solo título más autores.

### Formato de hallazgos (una tabla por archivo, más un resumen)
```markdown
# Hallazgos <tarea> (<fecha>)
Resumen: N hallazgos (A altos, M medios, B bajos). Lo más grave en una frase.

| # | Pág. | Sección / archivo:línea | Lente | Severidad | Hallazgo | Evidencia (cita corta) | Sugerencia (≤1 frase) |
|---|---|---|---|---|---|---|---|
```
- **Lente:** hilo, claridad, visual, cita, cifra, rúbrica, jurado o privacidad.
- **Severidad:**
  - ALTO: un jurado lo objetaría o incumple la rúbrica.
  - MEDIO: confunde o debilita.
  - BAJO: pulido.

---

### Tarea R1: Introducción y planteamiento (Introducción, Descripción general)
**Rango:** del cuerpo, pp. 1–10. Archivos `sections/introduccion.tex` y `sections/descripcionGeneral.tex`.
**Contexto previo:** solo `sections/covers/abstract_resumen.tex`.

- [ ] **Paso 1, Fase 1 (contexto).** Lee el resumen y escribe en 5 líneas, al inicio de tu archivo, qué entendiste del problema, del objetivo general y de los cinco objetivos específicos. Si algo no se entiende solo con el resumen, eso ya es un hallazgo.
- [ ] **Paso 2, Fase 2 (hilo).** Para cada `\section` y `\subsection`:
  - ¿Abre diciendo qué se verá?
  - ¿Cierra conectando con lo siguiente?
  - ¿Hay saltos bruscos entre párrafos?
  - ¿Cada objetivo específico dice qué fase de la metodología y de CRISP-DM lo cubre?
- [ ] **Paso 3, Fase 3 (claridad y visuales).** Marca:
  - Frases de más de unas 40 palabras o confusas.
  - Cada tabla y figura: verifica que el párrafo anterior la introduzca y diga qué mirar en ella.
  - El tiempo verbal: la rúbrica pide pasado en la Descripción general.
- [ ] **Paso 4, Fase 4 (citas).** Marca:
  - Afirmaciones fuertes sin cita (cifras de contexto, mercado, normas).
  - Consistencia del formato de cita.
  - Cada `\citep` o `\citet` cuya clave no esté en `bib/tukit.bib` (usa `rg -o '\\cite[pt]?\{[^}]+\}'` contra `rg '^@'`).
- [ ] **Paso 5, rúbrica.** Comprueba:
  - Que "Oportunidad, Problema" tenga 3 páginas o menos.
  - Que la tabla de entregables y estándares exista y tenga justificación.
  - Que el área de la propuesta esté dicha.
- [ ] **Paso 6.** Escribe `revision/hallazgos-R1.md` y avisa a la conductora.

### Tarea R2: Contexto, análisis y diseño (literatura y metodología de diseño)
**Rango:** del cuerpo, pp. 11–26. Archivos `contextoProyecto.tex`, `analisisProblema.tex` y `disenoSolucion.tex`, más las figuras de `img/arquitectura/`.
**Contexto previo:** el resumen y la Tabla de objetivos de `descripcionGeneral.tex`.

- [ ] **Paso 1, Fase 1.** Haz el mismo resumen de 5 líneas.
- [ ] **Paso 2, Fase 2 (hilo).** Revisa:
  - ¿Los antecedentes llevan de los retos de la lista a cada técnica?
  - ¿El análisis del contexto termina mostrando la brecha que llena Tukit?
  - ¿Cada decisión de diseño remite a un requerimiento o impulsor?
- [ ] **Paso 3, Fase 3.** Revisa:
  - Claridad.
  - Que la Tabla de antecedentes, la de requerimientos y el C4 de contenedores se introduzcan y se expliquen. El C4 se lee de izquierda a derecha.
  - Si el C4 o el despliegue son legibles en papel: tamaño de letra y contraste.
- [ ] **Paso 4, Fase 4 (literatura).** Es la parte con más peso de citas. Revisa:
  - ¿Las soluciones existentes del análisis del contexto están referenciadas?
  - ¿Cada concepto tiene una fuente primaria y no solo un blog?
  - Busca en la web 10 referencias elegidas al azar del `.bib` citadas en este rango y verifica que existan y que el año coincida.
- [ ] **Paso 5, rúbrica.** Comprueba:
  - Que los antecedentes no sean un glosario.
  - Que el contexto compare fortalezas contra debilidades.
  - Que el diseño justifique las herramientas con criterios.
  - Que se mencione el SDD para el detalle.
- [ ] **Paso 6.** Escribe `revision/hallazgos-R2.md` y avisa.

### Tarea R3: Desarrollo, resultados y conclusiones (resultados y discusión)
**Rango:** del cuerpo, pp. 27–60. Archivos:
- `desarrolloSolucion.tex`
- `optimizacion.tex`, el núcleo de la tesis: revísalo con más cuidado.
- `resultados.tex`, `calidad.tex`, `oe5.tex` y `conclusiones.tex`.
- Para las cifras: `docs/validacion/oe5/oe5_cierre/salida_analisis.txt`, `docs/validacion/oe5/oe5_ronda2/datos_ronda2.csv`, `docs/informes/calibracion/esc_d4.json` y `docs/informes/calidad/hallazgos_qa.csv`.

- [ ] **Paso 1, Fase 1.** Haz el resumen de 5 líneas.
- [ ] **Paso 2, Fase 2 (hilo).** Revisa:
  - ¿Cada etapa del pipeline sigue el patrón análisis → diseño de entradas y salidas → estrategia → seudocódigo → complejidad → comparación con el método exhaustivo?
  - ¿Los resultados responden en el mismo orden a lo que el desarrollo prometió?
  - ¿Las conclusiones dicen por qué se cumple cada objetivo, con la cifra que lo prueba?
- [ ] **Paso 3, Fase 3.** Revisa:
  - Que el modelo formal de optimización sea legible: variables, restricciones R1 a R3 y objetivos f1 a f4 definidos antes de usarse.
  - Que las tablas de resultados (métricas, tareas del OE5, cuestionario, ISO 25010) tengan una introducción y una lectura.
  - Que las capturas de `fig:recorrido` y `fig:equipo` se puedan leer.
- [ ] **Paso 4, cifras.** Contrasta cada número de este rango con HECHOS_CANONICOS y con los archivos de datos. En especial:
  - F1 0,948, HV 0,9969, p95 0,31 s.
  - SUS 90 [82–98], RTLX 63 → 9 con dz 1,83, NPS +83.
  - Las tareas T1 a T7.
  - Los 59 hallazgos de QA.
- [ ] **Paso 5, citas y rúbrica.** Comprueba:
  - Que el control de calidad cubra unidad, funcional, sistema y aceptación con análisis.
  - Que el desarrollo relacione el proceso con la metodología.
  - Que las conclusiones traigan impacto y trabajo futuro.
  - Que cada OE marcado "Cumplido" en `tab:cumplimiento` tenga su evidencia.
- [ ] **Paso 6.** Escribe `revision/hallazgos-R3.md` y avisa.

### Tarea R4: Jurado (Fase 5, documento entero)
**Rango:** el PDF completo, cuerpo y anexos. **No leas `revision/hallazgos-R*.md`** de los demás.

- [ ] **Paso 1.** Lee el PDF de principio a fin como jurado estricto pero justo de un trabajo de grado de pregrado de Ingeniería de Sistemas.
- [ ] **Paso 2.** Para cada capítulo (I a VIII), escribe las 3 preguntas más difíciles que harías en la sustentación. Cada pregunta lleva la página que la motiva y lo que el documento responde hoy, o "no responde".
- [ ] **Paso 3.** Escribe aparte los 5 puntos débiles del trabajo completo, ordenados por cuánto bajarían la nota. Revisa en particular:
  - Tamaño y sesgo de la muestra del OE5.
  - Independencia de los conjuntos de oro.
  - Validez de la calibración.
  - Hallazgos de seguridad abiertos.
  - Cumplimiento real de cada objetivo específico.
- [ ] **Paso 4.** Evalúa la coherencia global:
  - ¿El objetivo general se cumple por la suma de los específicos?
  - ¿Hay contradicciones entre capítulos (cifras, nombres de componentes, número de servicios)?
- [ ] **Paso 5.** Escribe `revision/hallazgos-R4.md`. La tabla lleva lente "jurado", más la sección de preguntas. Avisa.

### Tarea C: Conductora (la sesión original, después de R1 a R4)
- [ ] **Paso 1.** Une los cuatro archivos en `revision/CONSOLIDADO.md`:
  - Quitar duplicados.
  - Ordenar por severidad.
  - Marcar cuáles ya contradicen una decisión tomada (por ejemplo, la optimización completa en el cuerpo o el OE5 Cumplido).
- [ ] **Paso 2.** Los hallazgos ALTO en los que hay desacuerdo o que tocan una decisión de fondo pasan por `/llm-council`, un solo consejo con todos ellos juntos.
- [ ] **Paso 3.** Se aplican los cambios aceptados:
  - Se compila con `bash compilar.sh`.
  - El cuerpo se mantiene en 60 páginas o menos.
  - Commit como MapaRuiz y push con confirmación.
- [ ] **Paso 4.** Con las preguntas de R4 se arma `revision/PREGUNTAS_SUSTENTACION.md`, con la respuesta corta de cada una.

## Foco de revisión (lo que más probablemente se escape)
1. **Cifras que cambiaron tarde.** El OE5 se cerró el 4 y el 5 de noviembre, así que el abstract, la introducción y las conclusiones pueden tener una versión vieja (por ejemplo, "SUS no aplicado"). Esto lo cubre R3, paso 4, y R1 debe cruzarlo con el abstract.
2. **Referencias a secciones movidas al anexo.** NL2C, datos, constantes, requerimientos, autorización y antecedentes cambiaron de lugar el 5 de noviembre, y un texto puede seguir diciendo "en esta sección" o "a continuación" cuando el contenido ya está en el anexo. Lo cubren R1, R2 y R3 en el paso 2.
3. **Afirmaciones de "Cumplido" sin evidencia.** El OE5 se defiende con C3 formativo. Lo cubren R3 en el paso 5 y R4 en el paso 3.
4. **Privacidad en figuras.** Capturas de la app, citas de acudientes. Lo cubren R3 en el paso 3 y R4.
5. **Mezcla de tiempos verbales y de estilo de cita.** Lo cubren R1 y R2.
