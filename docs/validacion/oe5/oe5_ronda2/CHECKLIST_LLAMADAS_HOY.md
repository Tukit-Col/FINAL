# Checklist de llamadas, ronda 2 sumativa de OE5 (lunes 2-nov-2026)

Llamada de 15 min por papá. Versión evaluada: rama `validacion/oe5`, commit `b6b6fe7` (desplegado el 2-nov antes de las llamadas: dirección con mapa OSM, Fan sin Spiderman repetido, chat del kit ampliado, carrusel responsive), sin cambios entre llamadas. Todo lo que dice "HUECO" está resumido al final (sección 6) con lo que sugiero hacer hoy.

Fuentes: `09_runbook_sesiones.md`, `11_protocolo_sesion_dos_dias.md`, `12_formulario_y_rubrica_15min.md`, `10_mensajes_reclutamiento.md`, `oe5_ronda2/formulario_ronda2.md` (+ `.gs`), `anexos_OE5/*`, `tukit/docs/validacion/plan_analisis_oe5.md` y `analisis_oe5.py`.

---

## 1. Antes de cada llamada (5 min)

Una sola vez, antes de la primera:
- [ ] Hacer una compra completa tú misma con la tarjeta de prueba, por el túnel y desde el celular con datos móviles. Así compruebas de una vez: túnel, chat flotante en `/kits`, pago y pedido. El túnel se reinició el 2-nov (el anterior se cayó) y responde 200 en `https://awards-cigarettes-prevent-por.trycloudflare.com`.
- [ ] `make estado` dice `todos_arriba: true`. Admin (`localhost:3001/cola`) abierto en otra ventana, solo para ti, por si el kit cae en revisión.
- [ ] No tocar servicios, no `make bd-reiniciar-datos`, no `TUKIT_AUTOPUBLICAR`.

Por cada papá:
- [ ] **Código de participante.** Uno libre que no se haya usado en las rondas del 29, 30 y 31-oct (por ejemplo `R2-01`, `R2-02`...). Se anota en la rúbrica, en el nombre de la grabación y en el formulario (pregunta 1).
- [ ] **Enlace del túnel**: `https://awards-cigarettes-prevent-por.trycloudflare.com`. Se manda por privado justo antes, nunca al grupo. Si el túnel se reinició, la URL es otra.
- [ ] **Cuenta**: tarjeta de prueba, no registro con datos propios. El consentimiento promete "cuenta y datos de prueba" y que no se recogen datos del hijo. Registro propio solo si el papá insiste, y en ese caso se anota en la rúbrica y se avisa que su correo queda en la base de prueba.
  - Correo `acu-XX@prueba.tukit.co` (XX = su número), clave `Prueba-2026`, celular `300 000 00XX`.
  - Colegio Agustiniano Ciudad Salitre, Tercero. Al hijo le gusta Spiderman.
  - Entrega: Calle 23 C # 69 B - 01, Bogotá, Fontibón. Recibe "Acudiente de prueba".
- [ ] **Consentimiento escrito, ANTES de grabar o empezar** (ver hueco G1). Qué cuenta como escrito hoy:
  1. Mándale el texto de la sección 1 de `CONSENTIMIENTO_RONDA2.md` con la plantilla de la sección 2 (o el PDF `CONSENTIMIENTO_RONDA2.pdf` para firmar) por WhatsApp o correo, antes de la llamada.
  2. Que conteste por escrito, copiando y completando: *"Yo, [nombre completo], leí el consentimiento, soy mayor de 18 años y acepto participar (Parte A). Grabación de pantalla: SÍ / NO. Grabación de audio: SÍ / NO. Fecha: [..]"*.
  3. Guarda esa respuesta: captura de pantalla o PDF del correo, en una carpeta de consentimientos **aparte** de los datos, con nombre `consent_<código>.png` (el nombre del papá va dentro del archivo, nunca en el nombre). Se guarda bajo llave, retención como dice el protocolo ético (hasta la aprobación del trabajo de grado + 12 meses, plazo aún `[VERIF]`).
  4. Sin la Parte A no hay llamada ni notas. Si dice que no a la grabación, se toman notas y se sigue.
- [ ] **Grabación autorizada**: mira en su respuesta escrita el SÍ a pantalla (y audio, si lo dio). Solo entonces QuickTime sobre la ventana de Meet. Al empezar a grabar, dilo en voz alta: "Empiezo la grabación de pantalla, como autorizó". Se borra al verificar el análisis y, a más tardar, en 30 días.
- [ ] Rúbrica en blanco con el código (sección 3), cronómetro o reloj de la grabación visible, el enlace del formulario listo para pegar en el chat.
- [ ] Formulario (`formulario_ronda2`) abierto en una pestaña tuya, solo para comprobar que recibe respuestas.

---

## 2. Guion de 15 minutos

Escenario (leído y pegado en el chat): *"Usted es acudiente de un niño de Tercero del Agustiniano Ciudad Salitre y quiere dejar la lista de útiles resuelta antes de las vacaciones, que llegue todo junto y sin gastar de más. Su hijo ama a Spiderman. Use los datos de la tarjeta."*

Regla de ayuda: 90 s sin avance, solo "¿Qué intentaría hacer ahora?"; si sigue, pista mínima y se anota **A**. Sin avanzar al tope de la tarea, **F** y se pasa a la siguiente. Falla del sistema, **N** y se repite sin culpa al papá. Si pregunta "¿esto está bien?": *"Lo que usted decida está bien; ¿qué haría si estuviera en su casa?"*

| Min | Qué pasa | Tarea e instrumento |
|---|---|---|
| 0:00-1:30 | Saludo. Confirmas que ya tienes su consentimiento escrito y que empiezas a grabar. Le pasas el enlace del túnel por privado. Comparte pantalla del celular. | Ninguno |
| 1:30-2:00 | "Mientras la usa, dígame en voz alta lo que mira y lo que piensa." Lees el escenario. | Ninguno |
| 2:00-6:00 | **T1 y T2, crear el kit con el formulario.** Consigna: "Empiece: créese una cuenta con los datos de la tarjeta, diga de quién es la lista, cuéntele a la app qué le gusta a su hijo y cuánto quiere gastar, y envíe la solicitud." En `/empezar` el chat ya no está: es el formulario guiado. Éxito T1: cuenta creada, colegio y grado correctos. Éxito T2: personaje, opción de gasto y solicitud enviada. Tope 4 min en total. | T1 (crítica) y T2: resultado S/A/F/N, tiempo, errores. Anota en la grabación el momento en que termina el registro, para separar T1 de T2 después |
| hasta 7:30 | **T3, espera** ("Estamos armando tu kit"). No hables. No cuenta para el tiempo. Anota solo cuánto dura. Si cae en revisión, apruebas en `/cola`. Al llegar a los kits: "Cuénteme qué entiende de lo que pasó." | T3: S/A/F/N y duración de la espera aparte |
| 7:30-9:30 | **T4, revisar los kits y el Fan, y elegir.** Consigna: "Mire las opciones de kit. Cuénteme en qué se diferencian y elija la que le parezca mejor para su hijo." No digas "Fan" ni "Ahorrador". Éxito: elige un kit, da un motivo y dice en qué se diferencia de otro. Tope 2 min. | T4 (crítica): S/A/F/N, tiempo, kit elegido, motivo en sus palabras, si miró el kit Fan y si notó los productos de Spiderman |
| 9:30-10:30 | **T5, cambiar un producto.** "Un producto del kit no le convence: cámbielo por otra opción." Éxito: línea cambiada y dice cuánto cambió el total. Tope 1 min. | T5: S/A/F/N, tiempo |
| 10:30-12:00 | **T8, usar el chat del kit** (tarea nueva, ver hueco G3). "Quiere pedirle un cambio a la app en sus propias palabras, sin tocar los botones del kit. Pruebe." Sin nombrar el chat ni el ícono. No sugieras ejemplos. Éxito: escribe un pedido, la app propone, y él confirma o rechaza. Tope 1:30. Al terminar, pregunta en voz alta: "Del 1 al 7, ¿qué tan fácil fue? 1 muy difícil, 7 muy fácil." | T8: S/A/F/N, tiempo, qué escribió (cita), propuesta aceptada o rechazada, SEQ hablado |
| 12:00-13:30 | **T6, pagar (simulado).** "Deje pagado el pedido con los datos de la tarjeta." Éxito: llega a la confirmación "Pago aprobado". En modo simulado ya no hay botón "Aprobar pago": sale "Procesando pago de prueba…" y pasa solo (ver hueco G5). Si ves la pantalla de Wompi en vez de eso, es el modo sandbox: anótalo. | T6 (crítica): S/A/F/N, tiempo |
| 13:30-14:00 | **T7, el pedido.** "Más tarde quiere saber cómo va su pedido." Éxito: encuentra el pedido (Ver mi pedido o Mis pedidos) y dice estado y total. Si falta tiempo, se anota "no alcanzó" (ver abajo). | T7: S/A/F/N, tiempo |
| 14:00-15:00 | Pegas el enlace del formulario en el chat. Si hay tiempo, 1 pregunta abierta: "¿Qué fue lo más confuso?". Le recuerdas que lo conteste hoy, que son unos 8 minutos y que no cambie respuestas con nadie. Cierras la grabación. | SUS, NPS, SEQ y RTLX llegan por el formulario |

Si a los 12:00 no ha empezado T6, **sáltate lo que falte hasta T6**, pues pagar es tarea crítica. T5, T8 y T7 son las que se sacrifican; se anotan como "no alcanzó" y no como F.

Sobre "ver pedido/caso": hoy solo se mide el pedido (T7). El caso (`/dashboard` → "Mis casos" → "Abrir un caso nuevo") no tiene tarea ni criterio de éxito en el plan preregistrado; no lo pidas, solo anótalo si el papá lo abre solo.

---

## 3. Qué medir y dónde anotarlo

Una hoja por papá, copiando la rúbrica de `12_formulario_y_rubrica_15min.md` §B pero con estas filas (la original solo trae T1, T4 y T6, ver G2):

| Tarea | Inicio | Fin | S/A/F/N/NA | Ayudas | Errores E1-E7 (sev. 0-4) | Cita |
|---|---|---|---|---|---|---|
| T1 cuenta, colegio y grado (crítica) | | | | | | |
| T2 gusto y gasto, enviar | | | | | | |
| T3 espera (solo duración) | | | | | | |
| T4 revisar kits/Fan y elegir (crítica) | | | | | | |
| T5 cambiar un producto | | | | | | |
| T8 chat del kit (nueva) | | | | | | |
| T6 pagar (crítica) | | | | | | |
| T7 ver el pedido | | | | | | |

Cabecera: código, fecha y hora, remota, grabación pantalla (sí/no), audio (sí/no), celular (Android o iPhone), opción de gasto elegida, kit elegido, ¿cayó en revisión humana?

Códigos: **S** sin ayuda, **A** asistida, **F** fallida o tope, **N** falla del sistema (se repite, no cuenta contra el papá), **NA** no alcanzó por tiempo (dato faltante, no fallida). Errores: E1 no encuentra dónde ir, E2 error en un campo, E3 malinterpreta texto o precio, E4 acción equivocada, E5 omite un paso, E6 falla o lentitud del sistema, E7 duda de más de 10 s. Severidad: 1 cosmético, 2 menor, 3 mayor, 4 bloqueante.

Rápidos con palotes: se detuvo y dudó, volvió atrás, preguntó "¿esto está bien?", comentó precio, comentó personaje o gusto del hijo.

Dónde sale cada cosa:
| Dato | De dónde |
|---|---|
| Éxito por tarea, errores, severidad, citas, kit y gasto elegidos | Tu hoja, en vivo |
| Tiempo por tarea | De la grabación, mismo día (la espera de T3 no cuenta) |
| Interacciones (toques, campos, búsquedas, vueltas atrás) en T1, T4, T6 | Contadas en la grabación, mismo día |
| SUS (10 ítems, 1-5) y NPS (0-10) | Formulario, preguntas 32-41 y 42 |
| SEQ por tarea (1-7) | Formulario, preguntas 25-30 (T1, T2, T4, T5, T6, T7) y 31 (seguridad con el kit). El SEQ del chat (T8) lo dice en voz alta; anótalo en la hoja |
| RTLX de la compra tradicional y de TUKIT | Formulario, preguntas 13-18 y 19-24 (escala 0-10) |
| Línea base tradicional (tiempo, lugares, canal) | Formulario, preguntas 9-12 |
| Pago y medio de pago | Preguntas 46-47 |

Línea base tradicional: hoy no hay tarea de control en vivo (el plan de las etapas A/B/C ya se descartó). La línea base es el RTLX retrospectivo de su última compra más las preguntas 11-12. Si el papá no alcanza a llenar la Parte 2 del formulario, ese papá aporta SUS, NPS y tareas, pero no entra en C2.

---

## 4. Qué NO decir (para no sesgar)

- No nombres botones, pestañas ni kits: ni "Fan", ni "Ahorrador", ni "Premium", ni "A tu Medida", ni "Cambiar por otra opción", ni "el chat" ni "el asistente". Cada consigna describe una situación.
- No digas "fácil", "rápido", "sencillo", "mejor", "ahorra" ni "inteligente" cuando hables de la app. Tampoco "muy bien", "ese no es", "casi".
- No expliques cómo funciona la app, ni por qué algo se demora (en T3 solo "espere a que la app termine").
- No sugieras ejemplos de qué escribirle al chat. No anticipes que hay un chat.
- No preguntes "¿le parece claro?" ni "¿por qué no usó X?". Frases permitidas: "Siga contándome lo que piensa", "¿Qué está mirando ahora?", "¿Qué esperaba que pasara?" (solo después de que algo ocurra), "¿Qué haría ahora?", "Cuénteme qué entiende de esta pantalla".
- No corrijas ni comentes sus respuestas del formulario ni sus calificaciones. No lo ayudes con el SUS ("la pregunta es negativa a propósito" no se dice).
- No muestres tu pantalla ni la del admin. Si el kit tarda y lo apruebas en `/cola`, no lo menciones.
- No arregles nada de la app entre llamadas. Los problemas se anotan y van al informe.
- Si conoce el grupo de papás y comenta que "ya lo vio por ahí": anótalo (contaminación declarada en `10_mensajes_reclutamiento.md`), no lo cortes.

---

## 5. Después de cada llamada y al cerrar el día

Por papá (10 min):
1. Hoja completa y grabación guardada como `<código>.mov`, sin su nombre.
2. Sacar de la grabación los tiempos por tarea y los toques en T1, T4 y T6.
3. Verificar que contestó el formulario. Si no, recordatorio hoy mismo (un papá sin SUS y NPS no cuenta para n).
4. Problemas de severidad 3 o 4 a la bitácora de bugs, sin corregir.

Al cerrar el día, pasar a CSV (`docs/validacion/analisis_oe5.py`, columnas en su encabezado):
| Columna del CSV | Sale de |
|---|---|
| `codigo` | pregunta 1 del formulario |
| `sus1`...`sus10` | preguntas 32 a 41 (1-5, en ese orden, sin invertir: el script invierte) |
| `nps` | pregunta 42 |
| `tlx_trad_1`...`tlx_trad_6` | preguntas 13 a 18, **multiplicadas por 10** (el formulario es 0-10 y el script espera 0-100) |
| `tlx_tukit_1`...`tlx_tukit_6` | preguntas 19 a 24, multiplicadas por 10 |
| `t1`...`t7` | tu hoja (S, A, F, N; vacío si no alcanzó) |
| `seg_t1`...`seg_t7`, `int_t1`...`int_t7` | de la grabación; vacío si no se midió |
Correr: `python docs/validacion/analisis_oe5.py datos.csv`. Una fila sin SUS o NPS completos hace fallar el script: no la incluyas hasta tenerlos. T8 (chat), SEQ, tiempos de espera, kit elegido y medio de pago **no** tienen columna; van en una hoja aparte, descriptiva.

Dónde cae en la memoria (`memoria-final/sections/`):
| Resultado | Destino |
|---|---|
| Tabla de participantes (reclutados, completos, excluidos), SUS, NPS, éxito por tarea, tiempos, RTLX | `oe5.tex` (hoy tiene solo la frase de apertura) |
| Protocolo ético, consentimiento e instrumentos | Anexo nuevo; cierra el `\pendienteEvidencia` de `anexos.tex:54` |
| Resumen SUS, NPS y carga cognitiva para el impacto social | `conclusiones.tex:25` |
| Estado OE5 en la tabla de cumplimiento | `conclusiones.tex:58` |
| Cambios al plan (sesión de 15 min, topes de tiempo, T8, SEQ, línea base) | "Desviaciones posteriores" de `docs/validacion/plan_analisis_oe5.md` (hoy vacía, ver G6) |
| n efectiva y cifras | HECHOS_CANONICOS, una sola vez |

**Umbral de n** (plan de análisis y decisión del 25-oct):
- **n ≥ 5 papás con sesión completa** (consentimiento, tareas y SUS + NPS contestados): se reporta la ronda 2.
- **n < 5**: solo se reporta la ronda 1; la ronda 2 queda como intento, con su n y el motivo.
- **5 ≤ n < 10**: C1 y C2 se reportan como **indicativos**, no "cumplido" ni "no cumplido". C3 con n=5 exige 4 de 5 sin ayuda por tarea crítica; se reporta el IC de Wilson, que será muy amplio.
- C2 solo con papás que tengan los dos RTLX completos. El plan viejo exigía 24 pares; con n pequeño se declara inconcluyente en lugar de forzarlo.
- Para ronda 1 y ronda 2, no se mezclan los datos.

---

## 6. Huecos detectados

| # | Hueco | Qué hacer hoy |
|---|---|---|
| G1 | **[CERRADO 2-nov: `CONSENTIMIENTO_RONDA2.md/.pdf/.docx`, partes A/B/C alineadas con el formulario] ** El consentimiento escrito está dentro del formulario largo**, que el papá solo puede enviar completo, al final. No hay consentimiento previo a la llamada, ni formato imprimible/firmable de ronda 2. `anexos_OE5/consentimiento_informado.md` es de la versión de 55 min presencial (habla de 7 tareas, "en el colegio", "no grabamos video") y dice que no hay grabación de pantalla. Además los nombres de las partes no coinciden: el formulario dice B = pantalla, C = audio; `11_protocolo...` dice C = pantalla; el `.md` viejo dice B = audio. | Usar el procedimiento de la sección 1 (respuesta escrita por chat o correo, guardada como captura) y pedir que repita Parte 1 en el formulario al final como segundo registro. Decidir si eso basta como "escrito" (Ley 1581 admite autorización por medio técnico, `[VERIF]` con asesor). Idealmente, partir el formulario en dos (consentimiento + previa / resto) editando el `.gs`. |
| G2 | **[CERRADO 2-nov: correo, equipo y director llenos en `.md`, `.gs` y `.docx`; retención fijada en 12 meses + 30 días para grabaciones, igual que /legal/privacidad] ** Placeholders sin llenar** en `formulario_ronda2.md` y `.gs`: `[correo institucional del equipo]`, `[nombres del equipo]`, `[director/a]`. También `[VERIF]` en el plazo de retención. Sin eso el consentimiento no dice a quién escribir para retirar la autorización. | Llenarlos antes de mandar el texto al primer papá. No los inventé. |
| G3 | **[MITIGADO 2-nov: SEQ opcional del chat agregado al formulario (30b); T8 se reporta como exploratoria] ** T8 (chat del kit) no existe en ningún instrumento**: ni en el guion, ni en la rúbrica, ni en el CSV, ni en el plan preregistrado. El chat de `/empezar` está apagado por omisión (`NEXT_PUBLIC_TUKIT_ASISTENTE_EMPEZAR`); el asistente actual es el chat flotante "Asistente de tu kit" en `/kits/[trabajo_id]`, y solo aparece si la web se construyó con `NEXT_PUBLIC_TUKIT_ASISTENTE=1` (no pude comprobar el build: la variable se fija al compilar y la salida de `.next` está bloqueada). El formulario no tiene SEQ para el chat. | Verificar en tu prueba previa que el botón flotante aparece. Medir T8 como **exploratoria**, SEQ hablado, fuera de C1-C3. Si el botón no aparece, quitar T8 y su minuto pasa a T4. |
| G4 | **El guion y la rúbrica de 15 min cubren solo T1, T4 y T6**; los topes de tiempo (3 min por tarea) y el escenario de 30/40 min no encajan con 8 tareas en 12 min. La rúbrica de §B del doc 12 y el formulario de 2 min (solo SUS y NPS) compiten con el formulario largo `formulario_ronda2` (47 preguntas, unos 8 min, con SEQ y RTLX). | Usé el formulario largo, porque trae consentimiento, SEQ y línea base. La sección 2 recorta los topes; ver G6. Ese formulario no cabe en los 15 min: el papá lo contesta después de la llamada, el mismo día, y su tasa de respuesta decide la n efectiva. |
| G5 | **Pago simulado: el protocolo manda tocar "Aprobar pago"**, pero esa pantalla ya no existe (`pago/simulado/ProcesandoPrueba.tsx` aprueba sola tras 1,2 s y no tiene botón). Y el plan del 25-oct cambió el pago a Wompi sandbox; no puedo saber con cuál modo (`WOMPI_MODO`) corre el backend vivo sin leer `.env`. | Comprobarlo en tu compra previa. Si sale Wompi, el papá no debe usar tarjeta real: el consentimiento dice "pago simulado". |
| G6 | **Plan preregistrado desactualizado**: sigue hablando de sesiones de 30/40 min, T1-T7 y 5 papás mínimo; "Desviaciones posteriores" está vacío. Hoy hay cambios: 15 min, topes recortados, T8 añadida, T2 y T1 medidas juntas, chat de `/empezar` apagado, SEQ y RTLX solo por formulario. | Registrarlas en esa sección con fecha y motivo antes de analizar (regla del plan). |
| G7 | **`analisis_oe5.py` no lee SEQ, T8 ni la espera de T3**, y espera RTLX en 0-100 (formulario en 0-10). Con SEQ el plan prevé Wilcoxon con Holm (S3), pero ese cálculo no existe aún. | Multiplicar RTLX por 10 al armar el CSV; SEQ en hoja aparte, descriptivo. |
| G8 | **Retención**: el formulario dice borrar datos a los 12 meses de la aprobación y grabaciones a 30 días; `consentimiento_informado.md` lo deja en `[VERIF]`. | Mantener lo del formulario y confirmar con asesor. |
| G9 | **Cuenta de invitado `sin-credencial`** tomable por quien se registre primero (abierto en el runbook). | Se neutraliza porque cada papá se registra en T1; no cambiar nada hoy. |
| G10 | **Contaminación**: el grupo de papás se ve entre sí y la petición de no comentar la app no se puede verificar. | Declararlo en la memoria (ya está previsto). |
