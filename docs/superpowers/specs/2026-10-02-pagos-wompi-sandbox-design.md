# Pagos de prueba con Wompi (sandbox): del botón "Pagar" a la pasarela real

Fecha: 2026-10-02
Rama: `feature/pagos-wompi-sandbox`
Estado: implementado, con cambios (ver "Lo que cambió durante la implementación", al final)

## Intención

Hoy, en `/kits/{trabajo_id}`, el botón **Pagar $ X** crea el pedido pero nunca lleva
a una pasarela de verdad: con `WOMPI_MODO=falso` (el valor por omisión) la pasarela
devuelve como "url de pago" la misma página del kit, y el acudiente se queda viendo
"Llevándote a la pasarela…".

En una frase: que ese botón lleve al acudiente al **checkout de Wompi en modo de
prueba**, que pueda pagar con los datos de prueba de Wompi (tarjeta, PSE o Nequi) sin
que se mueva dinero real, y que al volver a Tukit vea si el pago quedó aprobado o
rechazado y el pedido quede `pagado` en la base.

### Lo que pediste y lo que asumo

| Pediste | Asumo (corrígeme si no) |
|---|---|
| Que esta pantalla dirija de verdad a pagar con Wompi | Usamos la **página de pago alojada por Wompi** (Web Checkout). Tukit no dibuja formulario de tarjeta. |
| Conectar con su API para pagos de prueba | Solo **sandbox**: llaves `pub_test_` / `prv_test_`. Producción queda fuera de esta rama. |
| Sin que se descuente dinero | El sistema **se niega a arrancar** si en modo sandbox recibe una llave que no sea de prueba. |
| — | Tienes (o crearás) una cuenta en comercios.wompi.co y copiarás las 4 llaves de la pestaña "Desarrolladores" en modo prueba al `.env`. |
| — | Todo corre en tu máquina (localhost). El webhook de Wompi no puede llegar a localhost sin un túnel, así que el diseño **no depende del webhook** para funcionar en local. |

### Éxito

1. Clic en **Pagar** → el navegador abre `checkout.wompi.co` con el monto exacto del kit.
2. Pago con tarjeta de prueba `4242 4242 4242 4242` → vuelvo a Tukit y veo "Pago aprobado"; el pedido queda `pagado` y aparece en el back-office de logística.
3. Pago con tarjeta `4111 1111 1111 1111` → vuelvo y veo "Pago rechazado" con opción de reintentar; el pedido sigue `pendiente_pago`.
4. Ningún peso real se mueve y ninguna llave sale del `.env`.

## Contexto verificado (estado real del código, 2026-10-02)

Buena parte ya existe en `servicios/comercio`. Lo que falta es el tramo que
conecta con Wompi de verdad.

**Ya funciona y se reutiliza tal cual:**

- El recorrido navegador → `apps/web` (ruta `/api/trabajos/{id}/ordenar`) → gateway →
  Inteligencia (`trabajos.ordenar`) → Comercio (`POST /v1/ordenes` y luego
  `POST /v1/ordenes/{id}/pago`). Se congela precio y dirección y se reserva inventario.
- El puerto `PasarelaPago` con dos adaptadores (`WompiSandbox` y `PasarelaFalsa`) y la
  selección por `WOMPI_MODO` en `pasarela_desde_entorno()`.
- `firma_integridad()` y `firma_evento()`, con la receta de docs.wompi.co.
- `POST /v1/webhooks/wompi`: verifica firma, es idempotente con
  `evento_pasarela_procesado`, pasa el pedido a `pagado` y escribe `pedido_pagado` en la
  bandeja de salida en la misma transacción.
- El gateway ya rutea `/v1/ordenes` y `/v1/webhooks/wompi` hacia Comercio.
- `tukit.ps1` ya carga el `.env` de la raíz y levanta Comercio en el 8014.

**Lo que está roto o falta:**

1. **`WompiSandbox.crear_transaccion` no puede funcionar.** Llama a
   `POST /v1/transactions` sin `payment_method`. Wompi exige el medio de pago (y para
   tarjeta, un token creado en el navegador) en ese endpoint, así que responde 422. Esa
   API además no devuelve una URL para redirigir al acudiente.
2. **No hay página de regreso.** El `redirect-url` actual es la misma página del kit, que
   no sabe leer el `?id=<transacción>` que Wompi añade al volver.
3. **No hay forma de confirmar el pago en local.** Sin túnel, el webhook nunca llega, y
   el pedido se quedaría en `pendiente_pago` para siempre.
4. **El candado del webhook usa un id que Wompi no manda.** Los eventos reales de Wompi
   no traen `id` de evento; el código cae al id de transacción. Dos eventos de la misma
   transacción con estados distintos (PENDING y luego APPROVED) chocarían, y el segundo,
   el que importa, se descartaría como "repetido".
5. **No se valida el monto del evento** contra el monto congelado del pago.
6. **El medio de pago se fija antes de pagar** (`pse` por omisión), pero en el checkout
   alojado el acudiente lo elige dentro de Wompi.

## Enfoques considerados

### A. Web Checkout por redirección (recomendado)

Comercio arma la URL `https://checkout.wompi.co/p/?public-key=…&currency=COP&amount-in-cents=…&reference=…&signature:integrity=…&redirect-url=…`
y el navegador navega a ella. Wompi pinta su formulario (tarjeta, PSE, Nequi,
Bancolombia), cobra y devuelve al acudiente a `redirect-url?id=<transacción>&env=test`.

- **A favor:** cero datos de tarjeta en Tukit (cumple SG-03 sin esfuerzo, sin alcance PCI);
  encaja con el código actual, que ya espera una `url_redireccion`; la firma de
  integridad ya está escrita; la misma URL sirve para sandbox y producción, solo cambia la llave.
- **En contra:** el acudiente sale del sitio de Tukit durante el pago.

### B. Widget embebido de Wompi

Se carga el script de Wompi y el formulario se abre como modal sobre la página del kit.

- **A favor:** el acudiente no sale de Tukit.
- **En contra:** hay que cargar un script de terceros en Next.js, pasar la firma de
  integridad al navegador y manejar el callback en el cliente. Más piezas para el mismo
  resultado en pruebas.

### C. API directa de transacciones (lo que intenta el código hoy)

Tukit pinta su propio formulario, tokeniza la tarjeta contra Wompi y crea la transacción
desde Comercio.

- **A favor:** control total del diseño.
- **En contra:** un formulario y un flujo por cada medio de pago (PSE pide banco y tipo de
  persona, Nequi pide celular y espera la confirmación en el teléfono). Es mucho más
  trabajo y más superficie sensible.

**Recomendación: A.** Es el camino más corto y seguro a "pagar de verdad en pruebas", y
deja B como mejora visual posterior sin tocar el backend.

## Diseño

### Flujo completo

```
Navegador (/kits/{trabajo})                 apps/web          gateway → Inteligencia → Comercio            Wompi
  Pagar ──────────────────────────────────► /api/.../ordenar ──────────────────────────► crear orden
                                                                                          crear pago (iniciado)
                                                                                          arma URL firmada
  ◄──────────────── { url_redireccion: "https://checkout.wompi.co/p/?…" } ◄──────────────
  window.location = url ──────────────────────────────────────────────────────────────────────────────► paga (sandbox)
  ◄─────────────────────────────────────────────────────────────── redirect /pago/resultado?id=TX&env=test
/pago/resultado
  POST /api/pagos/TX/sincronizar ─────────► gateway ─────────────────────────────────────► GET /v1/transactions/TX ──► Wompi
                                                                                          aplica estado (mismo código del webhook)
  ◄──────────────── { estado_pago, estado_pedido, pedido_id, total } ◄────────────────────
  "Pago aprobado" / "Pago rechazado, reintentar" / "Procesando…" (reconsulta)

(Opcional, con túnel)  Wompi ── POST /v1/webhooks/wompi ──► gateway ──► Comercio (mismo aplicador, idempotente)
```

La idea clave: **hay dos caminos para enterarse del resultado y ambos usan el mismo
aplicador.** El regreso del navegador consulta a Wompi servidor a servidor, así que
funciona en localhost sin túnel. El webhook queda listo para cuando haya URL pública, y
la idempotencia hace que llegar por los dos caminos no aplique el pago dos veces.

### 1. Comercio — `pasarela.py`

**`WompiSandbox.crear_transaccion` deja de llamar a la API** y pasa a armar la URL del
Web Checkout. No sale a la red:

- `public-key`, `currency=COP`, `amount-in-cents` (total × 100), `reference`,
  `signature:integrity` = `firma_integridad(referencia, centavos, secreto_integridad)`,
  `redirect-url`, y `customer-data:email` con el correo del acudiente.
- Devuelve `TransaccionCreada(transaccion_id=None, estado=INICIADO, url_redireccion=<url>)`.
  El id de transacción no existe todavía: Wompi lo crea cuando el acudiente paga.

**Nuevo método del puerto: `consultar_transaccion(transaccion_id) -> EventoPasarela`.**

- `WompiSandbox`: `GET {base}/transactions/{id}` (endpoint público de Wompi) y lo reduce a
  un `EventoPasarela`. Como la consulta la hace Comercio directamente a Wompi, la respuesta
  es de fiar sin firma.
- `PasarelaFalsa`: el id de transacción simulado lleva el desenlace,
  `falsa-{APPROVED|DECLINED}-{referencia}`. La pasarela lo descompone y toma el monto de
  su registro en memoria de lo creado. Sin red y sin estado compartido con el navegador.

**`EventoPasarela` gana dos campos**: `monto_centavos` y `metodo` (el
`payment_method_type` de Wompi traducido: `CARD`→`tarjeta`, `PSE`→`pse`,
`NEQUI`→`nequi`; cualquier otro se deja sin traducir y no se sobrescribe).

**Clave de idempotencia corregida**: `evento_id = "{transaccion_id}:{estado_wompi}"`.
Así, PENDING y APPROVED de la misma transacción son eventos distintos, y el webhook que
llega después de la sincronización (o al revés) se reconoce como repetido.

**`PasarelaFalsa` también arma una URL**, pero hacia una página local de simulación
(ver frontend, punto 5), para que el flujo completo se pueda caminar sin llaves.

**Candado contra dinero real en `pasarela_desde_entorno()`**: con `WOMPI_MODO=sandbox`,
falla al arrancar si `WOMPI_LLAVE_PUBLICA` no empieza por `pub_test_`,
`WOMPI_LLAVE_PRIVADA` por `prv_test_`, `WOMPI_SECRETO_EVENTOS` por `test_events_` o
`WOMPI_SECRETO_INTEGRIDAD` por `test_integrity_`. No existe un modo `produccion` en
esta rama.

### 2. Comercio — `api.py`

**Un solo aplicador `_aplicar_resultado(conexion, evento)`**, extraído del webhook actual:
candado de idempotencia, buscar el pago por referencia, validar monto, actualizar pago,
transicionar pedido y escribir el outbox. Lo usan el webhook y la sincronización.

**Validación de monto**: si `monto_centavos` del evento no coincide con
`pago.monto × 100`, no se aprueba nada. El pago queda `rechazado` y se responde con el
motivo `monto_no_coincide`. Es la defensa contra una URL de pago manipulada.

**Nuevo endpoint `POST /v1/pagos/{transaccion_id}/sincronizar`**:

1. `pasarela.consultar_transaccion(transaccion_id)`.
2. `_aplicar_resultado(...)` con lo que respondió Wompi.
3. Devuelve `{pedido_id, total, estado_pago, estado_pedido}`.

Errores: Wompi caído o transacción inexistente → `502 pasarela_no_disponible` /
`404 transaccion_no_existe`; referencia que no es de Tukit → `404 pago_no_existe`.

**Referencia por intento**: `tukit-{pago_id}` en lugar de `tukit-{pedido_id}`. La columna
`referencia_wompi` es única, así que la referencia actual impide un segundo intento sobre
el mismo pedido tras un rechazo. Wompi también exige referencias únicas por comercio.

**Medio de pago**: se crea el pago con el valor por omisión de hoy y se corrige con el
`metodo` que reporta Wompi al aplicar el resultado. No hace falta migración: los valores
posibles ya están en el `CHECK` de la tabla.

### 3. Gateway

Añadir el prefijo `/v1/pagos` → `comercio` en la tabla de ruteo (`tukit_gateway/api.py`).
`/v1/webhooks/wompi` ya está.

### 4. Inteligencia

Sin cambios de lógica. `trabajos.ordenar` ya reenvía `url_redireccion` y devuelve lo que
Comercio responde.

### 5. Frontend (`apps/web`)

- **`VistaKits.tsx`, `Checkout.pagar`**: `url_redireccion` pasa a ser
  `${window.location.origin}/pago/resultado`, sin query (Wompi añade `?id=…&env=test`).
  Se elimina la rama del `window.alert`, porque ahora siempre hay URL.
- **Nueva página `/pago/resultado`**: lee `id` de la URL y llama a la nueva ruta de
  servidor. Muestra tres estados:
  - **Aprobado**: total, número de pedido y botón "Ir a mi panel".
  - **Rechazado**: mensaje claro y "Volver a mi kit" para reintentar.
  - **Pendiente** (PSE y Nequi pueden tardar unos segundos): "Estamos confirmando tu
    pago" y reconsulta cada 3 s, hasta 60 s; después, mensaje de que el estado llegará
    a su panel.
- **Nueva ruta de servidor `/api/pagos/[transaccion_id]/sincronizar`**: misma costura que
  `/api/trabajos/[id]/ordenar` (el navegador nunca habla con el backend).
- **Contrato TS** (`libs/ts/tukit-contrato`): tipo `ResultadoPago` y método
  `sincronizarPago(transaccionId)` en el origen de datos y en el cliente HTTP.
- **Página de simulación (solo `WOMPI_MODO=falso`)**: `/pago/simulado?ref=…` con dos
  botones, "Aprobar" y "Rechazar", que redirigen a
  `/pago/resultado?id=falsa-APPROVED-{ref}` o `falsa-DECLINED-{ref}`. Permite
  caminar el flujo sin llaves y en las pruebas automáticas.

### 6. Configuración

Añadir a `.env.ejemplo` (sin valores reales):

```
# --- Pasarela de pago (Wompi) ---------------------------------------------
# falso   -> pasarela simulada, no sale a la red (por omision)
# sandbox -> checkout real de Wompi en modo PRUEBAS. Solo acepta llaves de prueba.
WOMPI_MODO=falso
# WOMPI_LLAVE_PUBLICA=pub_test_...
# WOMPI_LLAVE_PRIVADA=prv_test_...
# WOMPI_SECRETO_EVENTOS=test_events_...
# WOMPI_SECRETO_INTEGRIDAD=test_integrity_...
```

Y una sección corta en el README: cómo sacar las llaves de prueba, los datos de prueba
de Wompi y, opcional, cómo exponer el webhook con un túnel
(`cloudflared tunnel --url http://127.0.0.1:8010`) y pegarlo en el panel de Wompi como
URL de eventos.

## Datos de prueba de Wompi (sandbox)

| Medio | Dato | Resultado |
|---|---|---|
| Tarjeta | `4242 4242 4242 4242`, cualquier CVC y fecha futura | APPROVED |
| Tarjeta | `4111 1111 1111 1111` | DECLINED |
| Nequi | `3991111111` | APPROVED |
| Nequi | `3992222222` | DECLINED |
| PSE | Banco "Banco que aprueba" / "Banco que rechaza" | APPROVED / DECLINED |

Se verificarán contra docs.wompi.co al implementar, y la tabla final irá al README.

## Manejo de errores

| Situación | Qué pasa |
|---|---|
| Faltan llaves o alguna no es de prueba con `WOMPI_MODO=sandbox` | Comercio no arranca y dice cuál. |
| Wompi caído al sincronizar | `502`; la página de resultado muestra "No pudimos confirmar todavía" y reintenta. |
| El acudiente cierra Wompi sin pagar | No vuelve nadie; el pedido queda `pendiente_pago`. Expirar pedidos abandonados queda fuera de alcance. |
| El acudiente recarga `/pago/resultado` | La sincronización es idempotente: muestra el mismo estado sin re-aplicar. |
| Monto del evento distinto del congelado | Pago `rechazado`, pedido no se mueve. |
| Webhook con firma inválida | Se ignora con `200`, como hoy. |

## Pruebas

Siguiendo TDD (prueba primero) en `servicios/comercio/tests/`:

- **`test_pasarela.py`**: la URL del checkout lleva todos los parámetros y la firma de
  integridad correcta; `consultar_transaccion` traduce estado, monto y medio (con
  `httpx.MockTransport`, sin red); `pasarela_desde_entorno` rechaza llaves `pub_prod_` y
  `prv_prod_`.
- **`test_checkout.py`**: sincronizar aprueba el pedido y escribe el outbox; sincronizar
  dos veces no duplica; sincronizar y luego recibir el webhook del mismo estado no
  duplica; PENDING y luego APPROVED sí avanza; monto distinto no aprueba; un segundo
  intento tras rechazo crea un pago nuevo con otra referencia.
- **Gateway**: `test_ruteo.py` cubre `/v1/pagos`.
- **Frontend**: `npm run build` y lint del workspace web.
- **Manual (criterio de aceptación)**: con llaves de prueba reales, los pasos 1 a 3 de
  "Éxito" en el navegador, más un pago PSE con "Banco que aprueba".

## Fuera de alcance

- Producción y llaves reales.
- Widget embebido (enfoque B).
- Expirar pedidos `pendiente_pago` abandonados y liberar su reserva de inventario.
- Reembolsos reales en Wompi. El retracto sigue marcando `reembolsado` solo en la base.
- Evitar que varios clics en "Pagar" creen varios pedidos. Ya pasa hoy y no cambia.
- Correo de comprobante propio de Tukit. Wompi ya envía el suyo al correo del formulario.

## Orden de implementación (resumen)

El plan detallado, tarea por tarea, se escribe al aprobar este diseño.

1. Pasarela: URL de Web Checkout, `consultar_transaccion`, candado de llaves de prueba, nueva clave de idempotencia.
2. Comercio API: aplicador compartido, validación de monto, referencia por intento, endpoint de sincronización.
3. Gateway: prefijo `/v1/pagos`.
4. Contrato TS y ruta de servidor en `apps/web`.
5. Página `/pago/resultado`, página de simulación y cambio en `VistaKits.tsx`.
6. `.env.ejemplo`, README y prueba manual con llaves sandbox.

## Lo que cambió durante la implementación

Este diseño se aprobó el 2026-10-02 y se ejecutó con el plan
`docs/superpowers/plans/2026-10-02-pagos-wompi-sandbox.md`. Lo de arriba queda como se aprobó,
porque es el razonamiento con el que se empezó. Lo que sigue es lo que la realidad corrigió,
en el orden en que apareció. Las decisiones que quedaron están en los ADR 0021 a 0024
(`arquitectura/adr/`), y el contrato de la API (§9, versión 1.2) describe el estado final.

### 1. El Web Checkout no puede volver a `localhost` (y se cambió al widget)

Con llaves reales, el checkout abría bien desde el servidor y Wompi bloqueaba el navegador con
un 403 de su CDN. Probando parámetro por parámetro, el único que lo dispara es `redirect-url`
cuando apunta a `localhost` o a una IP privada; un dominio público pasa. El supuesto del diseño
—"todo corre en localhost y no depende del webhook"— era cierto para la confirmación y falso
para el retorno.

Se probó primero un túnel (`cloudflared`) hacia la app web, que funciona pero obliga a abrir
Tukit por otro dominio para pagar. A propuesta del dueño del proyecto se cambió al **enfoque B,
el widget**, que aquí se había dejado como mejora visual: el pago se abre en un modal encima
del kit, `comercio` firma sus datos y el acudiente no sale de Tukit. El túnel se retiró.

### 2. PSE se lleva la pestaña al banco

Con tarjeta el widget avisa a la página y todo cuadra. Con PSE no: el banco se lleva la pestaña
entera, el modal desaparece con su aviso, y sin `redirectUrl` el comprobante de Wompi deja al
acudiente ahí, sin botón de vuelta. Se devolvió `redirectUrl` a los datos del widget. La API de
Wompi acepta `localhost` como retorno; el 403 era solo de la URL del checkout.

### 3. El widget también mete la configuración en una URL

Al devolver `redirectUrl` el modal empezó a girar sin fin, en el kit y en "Mis pedidos". Leyendo
`widget.js`: por omisión el widget serializa su configuración en la URL de su iframe, que es la
que el CDN bloquea. Con `bootstrapTransport: "postmessage"`, una opción que la documentación
pública no menciona, la configuración viaja por mensaje. Una prueba fija esa opción.

### 4. Lo que la revisión del código encontró

Además de lo que el diseño ya preveía (la clave `<transacción>:<ESTADO>`, la validación de
monto, la referencia por intento):

- **Un pago aprobado podía retroceder** con un evento tardío. Los estados `aprobado` y
  `reembolsado` ya no se pisan, y un `PENDING` tardío no revive uno `rechazado`.
- **El webhook y la sincronización podían llegar a la vez** y el segundo chocaba con el índice
  único. La sincronización reintenta una vez en una sesión nueva.
- **La consulta pública de transacciones aceptaba cualquier comercio.** Ahora exige `COP` y, si
  Wompi dice de qué comercio es, que sea el nuestro. En sandbox se confirmó que Wompi sí manda
  `merchant.public_key`.
- **"Volver" tras un rechazo usaba `history.back()`**, que con Wompi regresa a su página. Ahora
  la respuesta trae `trabajo_id` y el botón es "Volver a mi kit".

### 5. Lo que se agregó después, a pedido

Ninguna de estas estaba en el diseño. Cada una se presentó en el chat y se aprobó antes de
escribirla.

- **Pantallas de resultado** con el pedido completo: total, medio, fecha, los pasos que siguen,
  los productos agrupados y la entrega; rechazado con causas comunes y reintento.
- **"Mis pedidos" con acciones:** pagar un pedido pendiente sin rearmarlo y cancelarlo. Cancelar
  consulta antes a Wompi con la llave privada, porque un PSE en curso que se cancela cobraría sin
  entregar; si la aprobación llega igual, queda una incidencia (ADR 0023).
- **Vigencia de 24 horas** para pagar, derivada de `creado_en`, y **un pedido pendiente por
  kit**: uno idéntico se reutiliza y uno distinto reemplaza al anterior. Esto saca de "Fuera de
  alcance" el punto de los varios clics en Pagar.
- **Estados por color y estado de compra en "Mis solicitudes"**, calculado cruzando pedidos por
  kit en vez de guardado (ADR 0024).

### 6. Lo que se probó y lo que no

Con llaves de sandbox reales se verificaron la llave pública, la privada y la firma de
integridad (una transacción por API con la tarjeta `4242`, aprobada), la búsqueda por referencia,
la cancelación contra Wompi, y pagos con tarjeta aprobada, tarjeta rechazada y PSE en el
navegador. La suite de `comercio` y `gateway` termina con 138 pruebas, y la app web estrena
`npm test` con el runner nativo de Node. El webhook con túnel no se probó: la sincronización lo
hace innecesario en desarrollo.
