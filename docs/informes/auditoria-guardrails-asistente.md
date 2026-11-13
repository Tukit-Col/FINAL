# Auditoria de guardrails del asistente (NL2C y `/v1/kits/{id}/asistente/proponer`)

Fecha: 2026-11-12. Rama `mejoras/datos-multihijo`. Alcance: `servicios/inteligencia` (`nl2c.py`, `nl2c_kit.py`,
`nl2c_lote.py`, `nl2c_flujo.py`, `routers/nl2c.py`). Referencia: el checklist del reel (guardrails que filtran lo que
entra, detectan trampas y tapan datos personales en lo que sale; cache y router de modelos; trazas para saber por que
respondio mal; costo bajo carga) y OWASP LLM Top 10. Rutas relativas a `servicios/inteligencia/tukit_inteligencia/`.

## 1. Inventario de guardrails reales

| Guardrail | Donde |
|---|---|
| Interruptor `TUKIT_ASISTENTE=1`; apagado = 404 | `nl2c.py:activo`, `routers/nl2c.py:_exigir_activo` |
| Un solo turno, el resultado de una funcion no vuelve al modelo | `nl2c.py:50` (`MAX_TURNOS`), flujo en `nl2c_flujo.py` |
| Allow-list de funciones por endpoint, enviada a Gemini (`mode: ANY` + `allowedFunctionNames`) y filtrada otra vez en el servidor | `nl2c.py:551-560`, `613`, `660` |
| Esquemas `extra="forbid"` en cuerpos HTTP y en R (`RestriccionesR`, `FiltrosDuros`, `PesosNSGA`, `PreferenciasPRM`) | `routers/nl2c.py:89-110`, `nl2c.py:205-240` |
| Validacion manual de claves y tipos de lo que devuelve el modelo; fuera de forma = `ArgumentosInvalidos`, fuera de rango = se recorta y se avisa | `nl2c.py:proyectar_R` (305+) |
| Texto del padre: NFKC, quita control/ancho cero/bidi, etiquetas del bloque, `<` `>`, tope de 1000 caracteres | `nl2c.py:sanitizar` (169) |
| Redaccion de PII: correo, URL, direccion con prefijo de via, telefono/documento, nombre tras "mi hijo/se llama/soy" | `nl2c.py:~118-170` |
| Texto del padre y renglones del kit viajan como DATO entre marcas; reglas del sistema dicen que es dato | `nl2c.py:armar_usuario`, `_REGLAS` (563) |
| Descripciones del kit saneadas y recortadas a 80 caracteres; 80 renglones maximo en el prompt | `nl2c_kit.py:_texto_renglon`, `nl2c.py:42-43` |
| Todo texto que ve el padre sale de plantillas del servidor; precios, nombres e imagenes salen del kit, no del modelo | `nl2c_kit.py:_propuesta_cambio`, `_cerrar_lote` |
| Referencias L#/A# resueltas contra el kit del portador; item_id/sku del modelo no existen como entrada | `nl2c_kit.py:validar_llamadas_kit` (204) |
| Marca y personaje devueltos por el modelo solo valen si aparecen en el texto del padre / catalogo | `nl2c.py:_en_texto` (295), `proyectar_R` |
| Topes: 5 propuestas sueltas, 12 por categoria, 1 pedido por categoria por respuesta, 400 tokens de salida, 12 s de plazo | `nl2c.py:44-49`, `nl2c_kit.py` |
| Pedido por categoria sin categoria no se expande a todo el kit (salvo "variar") | `nl2c_kit.py:_resolver_lote` |
| Pedido anterior del navegador: dos palabras acotadas por regex y revalidadas contra el kit | `routers/nl2c.py:PedidoAnterior`, `nl2c_lote.py:validar_anterior` (180) |
| Dueno del kit: `usuario_id == portador`; mismo 404 para ajeno e inexistente; solo `PUBLICADO` (409) | `routers/nl2c.py:~160-170` |
| Quien confirma: el padre. El asistente solo propone; aplicar va por los endpoints de siempre. Descarte "aplicable" tambien es del padre | `nl2c_kit.py`, docstring de `routers/nl2c.py` |
| `/decision` solo acepta propuestas emitidas por este servidor al mismo portador | `nl2c_kit.py:522-534`, `routers/nl2c.py:decision` |
| "Que puedes hacer" se responde por regla, sin modelo | `nl2c_lote.py:pide_ayuda` (93) |
| Bitacora sin texto del padre ni PII (huella sha256 de 12 caracteres) | `nl2c.py:auditar` (716) |
| NUEVO (esta auditoria): cupo por portador, 20 llamadas/min y 60.000 tokens/hora, 429 `asistente_limite` | `nl2c.py:LimitadorSesion` (78-132), `routers/nl2c.py:_admitir` |
| NUEVO: se eliminan caracteres Cf, `U+E0000` (tags) y selectores de variacion | `nl2c.py:sanitizar` |
| NUEVO: el `motivo` de `sin_accion` que escribe el modelo ya no entra crudo a la bitacora | `nl2c_flujo.py` |

## 2. Matriz reel / OWASP

Severidad = riesgo real hoy con el asistente propositivo (no aplica nada solo). Entre parentesis, la severidad si se habilitan acciones en lote (Fase 5).

| Control | Estado | Severidad | Nota |
|---|---|---|---|
| Inyeccion directa (LLM01) | Cubierto | Baja | Estructural: el modelo no tiene herramientas de escritura ni segundo turno; salida validada. Pruebas `test_inyeccion_directa_*` |
| Inyeccion indirecta (nombre de producto, colegio, apodo) | Cubierto | Baja | Marcas y `<` eliminadas, bloque cerrado una sola vez, 80 caracteres. La marca (`marca`) del kit va al navegador sin sanear: texto del catalogo, no del padre |
| Exfiltracion del prompt (LLM07) | Cubierto | Baja | No hay campo de texto libre del modelo hacia el padre. El prompt no contiene secretos |
| Manejo inseguro de salida (LLM05) | Cubierto | Baja | Plantillas y lista blanca de componentes; el navegador revalida la spec |
| Acciones excesivas (LLM06) | Cubierto hoy / Parcial en Fase 5 | Baja (Alta) | Hoy no escribe. En lote hace falta confirmacion unica con tope y firma (seccion 4) |
| IDOR / kit de otro hijo o usuario | Cubierto | Baja | 404 uniforme; refs resueltas dentro del kit del portador. Hijo: hoy el trabajo es del acudiente, el kit por `perfil`; no hay seleccion de hijo en el endpoint |
| PII / datos de menores | Cubierto | Baja | Frase gatillo + lista de nombres de pila frecuentes (con o sin mayuscula, sin frase gatillo; respeta personajes del catalogo y nombres de colegio) + conjunto/edificio/torre/apto. Solo al texto del padre, no a las descripciones de la lista. Un nombre poco comun sin frase gatillo aun puede pasar |
| Precio/descuento manipulado | Cubierto | Baja | El precio sale del kit; claves extra se ignoran o invalidan |
| Compra/pago | Cubierto | Baja | No existe la herramienta; tarjeta/cedula se redactan antes del modelo |
| Limite de longitud | Cubierto | Baja | 4000 en la puerta, 1000 al modelo, 80 renglones |
| Limite de tasa y de costo (LLM10) | **Era Falta; ahora Parcial** | Media | Antes: ninguno, y `/interpretar` acepta anonimos. Ahora cupo por portador/IP en memoria de un proceso (no compartido entre procesos ni sobrevive reinicios) |
| Concurrencia al modelo | Falta | Media | `asyncio.to_thread` sin semaforo global; un timeout deja el hilo vivo hasta que Gemini responde |
| Unicode / homoglifos | Parcial | Baja | Ancho cero, bidi, tags y NFKC cubiertos. Homoglifos cirilicos no se transliteran: no importa para marcas/personajes (se descartan por `_en_texto`), pero el modelo si ve el texto |
| Jailbreak / roleplay / falsa memoria multi-turno | Cubierto | Baja | Un turno, sin estado; el unico estado del navegador es `PedidoAnterior` validado |
| Validacion de esquema | Cubierto | Baja | Doble: `proyectar_R` y `validar_llamadas_kit` |
| Fuera de dominio | Cubierto | Baja | `sin_accion` y mensaje de plantilla |
| Trazas persistentes (reel: "nadie sabe por que") | **Falta** | **Media (Alta)** | `BITACORA` es un deque de 1000 en memoria + log INFO; no hay tabla ni retencion; sin el texto saneado no se puede reproducir un caso |
| Evals en CI | Parcial | Media | Pruebas deterministas con modelo doble, ahora tambien adversariales (este informe). El banco `ensayos/nl2c` mide ASR con modelo real pero no corre en CI |
| Cache | Falta | Baja | Cada mensaje llama a Gemini salvo "ayuda". Candidatos: huella saneada + huella del kit |
| Router de modelos | Falta | Baja | Un solo modelo. La regla `pide_ayuda` hace el papel de router barato; ampliar a frases frecuentes ("mas barato en X") ahorra costo |
| Escalada a humano | Falta | Baja | Cae al formulario clasico (503); no hay "hablar con una persona" |
| Citar fuentes | No aplica | n/a | No responde con conocimiento; las cifras salen del kit |
| Integridad de la decision | Parcial | Baja (Alta) | Emisiones por portador (200 c/u, 30 min); inundar como anonimo no expulsa las de un padre con sesion. `/decision` exige un `tipo` que la propuesta traia (422 si no). Falta ligar el contenido (precio/sku) antes de la Fase 5 |

## 3. Pruebas nuevas

`servicios/inteligencia/tests/test_nl2c_adversarial.py`: 86 casos parametrizados, modelo siempre simulado (el doble OBEDECE al atacante). Cubre inyeccion directa e indirecta, prompt y roleplay, precio/descuento, IDOR (kit, perfil, decision), compra/pago, menores, fuera de tema, mensajes enormes, unicode, lote de 100 y limites. Resultado inicial: 79 pasan y 7 `xfail(strict)` que documentaban huecos reales. Los 7 se cerraron el 2026-11-13 (seccion 4b) y sus pruebas pasan sin marca.

## 4. Arreglado en esta auditoria

- Cupo por portador (20/min, 60.000 tokens/h; anonimo por IP) con 429 `asistente_limite` y bitacora `limite_excedido`.
- `sanitizar` quita categoria Cf (ancho cero, bidi, soft hyphen), tags `U+E0000-E007F` y selectores de variacion: antes se podian esconder ordenes invisibles para el padre.
- `motivo` de `sin_accion` forzado a la lista antes de la bitacora.
- `conftest.py`: reinicia el limitador por prueba.

## 4b. Cerrado el 2026-11-13 (los 7 xfail)

1. **Nombre del menor sin frase gatillo o en minuscula** (3 casos): `nombres_comunes.py` con nombres de pila frecuentes. Se conservan los personajes del catalogo y del kit, y lo que sigue a "colegio/San/Gimnasio..." (nombre de colegio). Los apellidos con mayuscula que siguen al nombre redactado tambien se van.
2. **Conjunto residencial**: `conjunto/edificio/urbanizacion/barrio + nombre` y `torre/apto/bloque/interior/casa + numero` quedan como `[direccion]`, solo en el texto del padre ("bloque 5 materias" de una lista no se toca).
3. **Inundar `_EMITIDAS`**: un cupo por portador (200) con vencimiento de 30 min; los anonimos comparten el suyo.
4. **`tipo` de la decision**: la emision guarda los tipos que traia (`restricciones`, `cambio`, `descarte`) y `/decision` responde 422 si no coincide.
5. **Cupo anonimo por IP**: la regla de `X-Forwarded-For` con proxies de confianza pasa del gateway a `tukit_comun.red` y la usa tambien Inteligencia. La web reenvia la cabecera del padre (`cabecerasReenviadas`) y el compose confia en la red de Docker para Inteligencia.

## 5. Recomendaciones antes de habilitar acciones en lote (Fase 5)

Orden de prioridad:

1. **Confirmacion unica con firma (Alta).** La propuesta debe quedar guardada en servidor (BD o Redis con TTL de 15 min): `propuesta_id`, portador, trabajo, lista de cambios (`item_id`, sku destino, precio visto) y hash. "Aplicar todo" recibe solo `propuesta_id`; el servidor aplica lo guardado y rechaza si el precio o el kit cambiaron. Reemplaza `_EMITIDAS`.
2. **Tope de N cambios por propuesta (Alta).** Ya hay 12 por categoria y 5 sueltas; fijar un tope duro de lote (p. ej. 12) en el endpoint de aplicar, ademas del de proponer, y un tope de delta en pesos que exija segunda confirmacion.
3. **Atomicidad e idempotencia (Alta).** Aplicar en una transaccion, con clave de idempotencia por `propuesta_id`; un doble clic no debe duplicar ni aplicar parcial en silencio.
4. **Tope de costo por sesion (Alta).** Mover `LimitadorSesion` a Redis (comun a todos los procesos) y sumar el costo de aplicar. Hoy el tope real es N procesos x cupo.
5. **Trazas persistentes (Media-Alta).** Tabla `asistente_traza` (propuesta_id, huella de usuario, trabajo, texto saneado, llamadas del modelo, rechazos, tokens, decision, aplicacion) con retencion definida y supresion junto con la cuenta (ya existe `test_supresion_inteligencia`). Sin esto no se puede responder "por que propuso eso".
6. **PII de menores (Media).** Redactar nombres con lista de nombres propios colombianos o un paso de NER local antes de Gemini; o dejar de enviar texto libre y enviar solo los campos extraidos. Decision de producto: hoy se acepta el riesgo residual.
7. **Semaforo global y plazo real al modelo (Media).** `asyncio.Semaphore` en `consultar_modelo` y cancelar la llamada al vencer.
8. **Evals en CI (Media).** Correr `ensayos/nl2c` con modelo grabado (replay) en el job `ensayos`; las nuevas pruebas ya corren en el job del servicio.
9. **Cache y router (Baja).** Despues de las anteriores.

## 6. No verificado

- Comportamiento con Gemini real ante los textos adversariales (solo modelo simulado). El ASR real sigue en `ensayos/nl2c`.
- La web trata 503 y 404 como "caer al formulario" (`apps/web/src/components/asistente/servidor.ts:66`, `PanelKit.tsx:159`, `PanelEmpezar.tsx:88`); el nuevo 429 pasa como error generico. Pendiente: tratarlo igual (zona de la web, no tocada).
- Los endpoints que aplican el cambio (`PUT .../descarte`, elegir producto) y su validacion de propiedad: fuera del alcance de este servicio auditado aqui.
- Backend: hay que reiniciar con `make reanudar` para que el limitador y el saneado nuevos tengan efecto (no se ejecuto).
