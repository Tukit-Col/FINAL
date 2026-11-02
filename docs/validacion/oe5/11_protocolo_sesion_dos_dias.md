# Protocolo de sesión OE5, versión de dos días (jueves 29 y viernes 30 de octubre de 2026)

Esta es la versión corta del plan del 17-oct (`03_plan_validacion_presencial.md`, `anexos_OE5/`). Lo que no cambia se toma de allá: textos del SUS, RTLX, NPS y SEQ (`anexos_OE5/instrumentos.md` §1-4), frases permitidas para el pensamiento en voz alta (`anexos_OE5/guion_sesion.md` §5) y protocolo ético (`anexos_OE5/protocolo_etico.md`). El plan de análisis preregistrado está en `tukit/docs/validacion/plan_analisis_oe5.md`.

## Antes de cada sesión (5 min)
1. El backend y la web corren y el túnel está abierto (`09_runbook_sesiones.md`).
2. Si el acudiente mandó la foto o el PDF de **la página de su grado**, la subí y aprobé en la cola. Si no, usa la tarjeta de prueba.
3. Hay un código ACU-xx libre y una tarjeta impresa o enviada por chat.
4. El formulario en línea (remota) o las hojas (presencial) están listos.
5. Grabación de pantalla lista: QuickTime sobre la ventana de la videollamada (remota) o grabación del celular de prueba (presencial).

## Tarjeta de prueba (datos inventados, ninguno de un niño real)
- Correo: `acu-XX@prueba.tukit.co` (XX = su código) · Clave: `Prueba-2026` · Celular: `300 000 00XX`
- Colegio: Colegio Agustiniano Ciudad Salitre · Grado: Tercero (alternativas con lista verificada: Primero, Quinto, Séptimo)
- Su hijo, en la historia, ama a **Spiderman**.
- Dirección de entrega: Calle 23 C # 69 B - 01, Bogotá, Fontibón. Recibe: "Acudiente de prueba".
- El pago es de prueba: en la pasarela simulada se aprueba sin datos de tarjeta.

## Guion (30 min remota / 40 min presencial)
| Min (R / P) | Bloque | Qué se hace |
|---|---|---|
| 0-3 / 0-5 | Bienvenida y consentimiento | Texto de bienvenida (`guion_sesion.md` §1). Partes A, B y C del consentimiento (abajo). Sin la Parte A no hay sesión |
| 3-6 / 5-9 | Preguntas previas | Rol, nivel escolar del hijo, dispositivo, compra en línea, cómo y cuándo compró útiles la última vez, cuánto le tomó, cuántas tiendas o viajes. Luego el RTLX retrospectivo de esa compra |
| 6-7 / 9-11 | Entrenamiento | "Mientras usa la app, dígame en voz alta lo que mira y lo que piensa." En presencial, una tarea neutra de 1 minuto |
| 7-22 / 11-30 | Tareas T1-T7 | Ver la tabla. Consigna leída y enviada por chat. Ayuda solo después de 90 s sin avance |
| 22-27 / 30-36 | Cuestionarios | RTLX de la tarea con Tukit, SEQ por tarea, SUS y NPS (formulario o papel) |
| 27-30 / 36-40 | Abiertas y cierre | Las 5 preguntas de `guion_sesion.md` §7. Si sobra tiempo: "¿Con qué medio pagaría de verdad?" (H2) y "¿Pagaría un 5 % o un 10 % más por recibirlo armado?" (H6) |

Escenario (se lee y se envía): *"Usted es acudiente de un niño de Tercero del Agustiniano Ciudad Salitre y quiere dejar la lista de útiles resuelta antes de las vacaciones, que llegue todo junto y sin gastar de más. Su hijo ama a Spiderman. Use los datos de la tarjeta."*

| # | Consigna (situación, sin nombrar botones) | Éxito sin ayuda | Máx. | Crítica |
|---|---|---|---|---|
| T1 | "Empiece: créese una cuenta con los datos de la tarjeta y diga de quién es la lista." | Cuenta creada; colegio y grado de la tarjeta elegidos | 4 min | Sí |
| T2 | "Cuéntele a la app qué le gusta a su hijo y cuánto quiere gastar, y envíe la solicitud." | Personaje elegido, opción de gasto elegida, solicitud enviada | 3 min | No |
| T3 | "Espere a que la app termine." | Llega a los kits y explica con sus palabras qué pasó. La espera no cuenta | 2 min activos | No |
| T4 | "Mire las opciones de kit y elija una." | Elige un kit, da un motivo y dice en qué se diferencia de otro | 5 min | Sí |
| T5 | "Un producto del kit no le convence: cámbielo por otra opción." | Línea cambiada y dice cuánto cambió el total | 4 min | No |
| T6 | "Deje pagado el pedido con los datos de la tarjeta." | Llega a la confirmación del pago de prueba | 4 min | Sí |
| T7 | "Más tarde quiere saber cómo va su pedido." | Encuentra su pedido y dice estado y total | 3 min | No |

Notas de la moderadora:
- **T3.** Si eligió "Un punto medio" (kit «A tu Medida»), su solicitud pasa a revisión humana: apruebo el trabajo en `apps/admin` → `/cola` mientras espera, y en la hoja anoto la espera del sistema aparte. Si eligió "Lo más económico" o "Puedo estirarme un poco", pasa directo a los kits.
- **T6.** La pasarela dice "Pasarela simulada (modo de pruebas sin Wompi)". El acudiente toca "Aprobar pago". No se pide ningún dato de tarjeta.
- **Falla del sistema.** Si algo se cae (E6), se repite la tarea y se anota N. No cuenta contra el acudiente.
- **Sin ayuda.** No se explica la app. Si pregunta "¿esto está bien?": *"Lo que usted decida está bien; ¿qué haría si estuviera en su casa?"*

## Cambios al consentimiento (`anexos_OE5/consentimiento_informado.md`)
- Duración: "unos 30 minutos por videollamada o unos 40 minutos en persona".
- Lugar: "por videollamada o en persona, como usted prefiera" (ya no "en el colegio").
- Se quita "No grabamos video ni tomamos fotos ni capturas de pantalla" y se agrega la **Parte C (opcional)**: *"Autorizo que se grabe la pantalla del celular con la app de prueba mientras hago las tareas (no mi cara ni mi cámara), solo para contar pasos y tiempos. La grabación se borra cuando el análisis esté verificado y, a más tardar, en 30 días."*
- Remota: el consentimiento va como primera página del formulario en línea, con las casillas de A, B y C, y se lee en voz alta antes de empezar.
- Pendientes del formato: nombres del equipo, director o directora y correo de contacto (`[...]` en el archivo).

## Después de cada sesión (10 min)
1. Hoja de observación completa: S, A, F o N por tarea, códigos de error y citas sin nombres.
2. Grabación guardada con el código ACU-xx, nunca con el nombre.
3. Una fila al CSV del análisis (`analisis_oe5.py`: columnas en su encabezado). Interacciones y tiempos se cuentan de la grabación ese mismo día.
4. Problemas de severidad 3 o 4 a la bitácora de bugs. **No se corrigen entre sesiones**: la versión evaluada queda fija para las dos jornadas, y lo encontrado va al informe.
