# Anexo N. Protocolo ético de la validación con acudientes (OE5)

Versión 0.1, 2026-10-17. Estado: borrador para revisión. Las marcas `[VERIF]` se resuelven y se borran antes de pegar en la memoria.

## 1. Propósito
Medir con acudientes del Colegio Agustiniano Ciudad Salitre (Bogotá) la usabilidad, la carga de trabajo percibida y la satisfacción al armar el kit de útiles con Tukit, frente a su proceso tradicional de compra. Los datos se usan solo para el trabajo de grado (finalidad exclusivamente académica) y para corregir el prototipo.

## 2. Marco normativo
- Ley 1581 de 2012, art. 7 (tratamiento de datos de niños, niñas y adolescentes), art. 9 (autorización previa, expresa e informada) y art. 12 (deber de informar al titular la finalidad, el carácter facultativo de las respuestas, sus derechos y la identidad del responsable).
- Decreto 1377 de 2013, art. 12 (requisitos especiales para datos de menores: interés superior y respeto de sus derechos prevalentes). `[VERIF]` con asesor jurídico si hoy se cita desde el Decreto 1074 de 2015, que lo compila.
- Ley 1581, art. 8 (derechos del titular) y arts. 14 y 15 (consultas y reclamos). `[VERIF]` plazos antes de publicarlos.
- Registro interno de datos: Anexo M (tratamiento de datos personales, campo a campo).

## 3. Participantes
- Madres, padres o acudientes mayores de 18 años con al menos un hijo en el colegio. Etapa A: 3 rondas de 5 (15). Etapa B: 30 analizables, se reclutan 36.
- Se excluye a familiares del equipo y a quien tenga relación laboral con el colegio o con el equipo.
- **No participan menores.** No hay sesiones, preguntas ni observación con niños. Por eso no se requiere asentimiento del menor. El art. 7 de la Ley 1581 se respeta evitando recoger datos del hijo, no con un consentimiento adicional.

## 4. Riesgos y mitigaciones
| Riesgo | Mitigación |
|---|---|
| Incomodidad o cansancio en una sesión de 55 minutos | Pausa a demanda; puede saltarse cualquier pregunta y terminar cuando quiera sin explicar |
| El participante da datos del hijo sin que se le pidan | Se le advierte al inicio; se omiten de las notas y de la transcripción |
| Sensación de ser evaluado | Se dice que se evalúa el sistema, no a la persona; no hay respuestas correctas |
| Presión de la institución al invitar | El colegio solo transmite la invitación; no recibe lista de quién participó ni los resultados individuales |
| Reidentificación por voz o contenido | Códigos `ACU-xx`, transcripción despersonalizada, audio destruido tras verificar |
| Pago o datos reales en un entorno de prueba | Solo pago simulado o de prueba (sandbox); no se usa tarjeta real ni cuenta real |

## 5. Minimización de datos
| Dato | ¿Se recoge? | Nota |
|---|---|---|
| Nombre y firma del acudiente | Sí, solo en el formato de consentimiento | Se guarda aparte de los datos de la sesión |
| Correo o teléfono | Solo el necesario para agendar; opcional para contacto posterior | Se borra al cerrar el estudio |
| Nombre, documento, fecha de nacimiento, foto o colegio específico del hijo | **No** | Del hijo solo se usa el nivel (preescolar, primaria, bachillerato) y el grado |
| Datos de la lista de útiles real | No | Se usan listas de referencia y datos sintéticos |
| Respuestas de cuestionarios (SUS, NASA-TLX, NPS, SEQ) | Sí, con código `ACU-xx` | Sin nombre |
| Notas de observación y tiempos | Sí, con código `ACU-xx` | |
| Audio de la sesión | Solo si el participante lo autoriza aparte | Ver sección 6 |
| Video, fotografías, captura de pantalla | **No** | Cualquier cambio exige modificar este protocolo y volver a pedir autorización |

La sesión corre en un entorno de pruebas con datos sintéticos. El acudiente usa una cuenta de prueba entregada por el equipo; no crea una cuenta real. No se pregunta ingreso, estrato, ni datos sensibles (Ley 1581, art. 5).

## 6. Grabación de audio
Es opcional y se autoriza con una casilla separada del consentimiento principal. Si la persona dice que no, la sesión se hace igual y el observador toma notas escritas. El audio sirve solo para transcribir el pensamiento en voz alta. Se transcribe, el segundo codificador verifica la transcripción y el audio se destruye en ese momento, y en todo caso en un plazo máximo de 30 días `[VERIF]`. Nadie sube el audio a servicios externos de transcripción sin que el consentimiento lo diga.

## 7. Almacenamiento y retención
- Datos de sesión (códigos `ACU-xx`): carpeta cifrada de la universidad o del equipo con acceso de las 4 personas del estudio. Nunca en el repositorio público ni en `git` (el repositorio solo recibe resultados agregados y el cuaderno de análisis). `[VERIF]` ubicación institucional.
- Formatos de consentimiento: archivo aparte, bajo llave, sin relación con los datos de sesión.
- Retención propuesta: datos despersonalizados hasta la aprobación final del trabajo de grado y 12 meses más; consentimientos por el mismo plazo. `[VERIF]` plazo con la facultad y el asesor jurídico. Al vencer, se borran.
- Si un participante pide supresión, se eliminan sus datos de sesión y se deja constancia en la bitácora. Si el análisis ya se publicó en forma agregada, los resultados agregados no cambian.

## 8. Derechos y contacto
El participante puede conocer, actualizar, rectificar y pedir la supresión de sus datos, revocar la autorización y presentar quejas ante la Superintendencia de Industria y Comercio. Responsable del tratamiento: `[NOMBRES DEL EQUIPO]`, estudiantes de Ingeniería de Sistemas, Pontificia Universidad Javeriana, bajo la dirección de `[DIRECTOR/A]`. Contacto: `[correo institucional del equipo]`. Respuesta a consultas en un plazo de 10 días hábiles `[VERIF]`.

## 9. Autorización del colegio
Antes de invitar a nadie se pide por escrito a rectoría: (a) permiso para que el colegio transmita la invitación por su canal; (b) un espacio de la jornada o del evento de padres para las sesiones; (c) constancia de que el colegio no recibe datos individuales. Tukit no recibe bases de familias: los acudientes se inscriben ellos mismos en un formulario con su propia autorización.

> Carta tipo: "Solicitamos autorización para invitar a los acudientes del colegio a una sesión individual de 55 minutos de evaluación de un prototipo de compra de útiles escolares, con fines exclusivamente académicos. No participan estudiantes. El colegio no entregará datos de las familias. Adjuntamos el protocolo y el formato de consentimiento." Firma de rectoría: `[ ]`. Estado: aval escrito **pendiente** `[VERIF]`.

## 10. Voluntariedad y sin incentivos
La participación es voluntaria y sin pago ni obsequio, para no inducir complacencia. No participar no tiene consecuencia alguna con el colegio ni con Tukit.

## 11. Incidentes y aprobaciones
Si hay una filtración o un uso no previsto de datos, el equipo informa a los afectados y a la dirección del trabajo de grado en un máximo de 72 horas y lo registra. Aprobaciones: director/a del trabajo de grado `[ ]`; comité de ética de la facultad, si aplica `[VERIF]`; rectoría `[ ]`.

---
Notas para revisión (borrar al pegar): (1) `anexos.tex` y MATRIZ_OE_EVIDENCIA dicen "asentimiento del menor"; este protocolo lo excluye porque los menores no participan. Hay que ajustar el texto del índice de anexos. (2) El plan 03 §6 propone una captura de pantalla opcional; aquí se descarta para respetar "solo audio". (3) La etapa C (reserva real) es otra finalidad y requiere su propia autorización comercial; no está cubierta por este anexo.
