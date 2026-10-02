# Pagos de prueba con Wompi (sandbox) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el botón "Pagar" de `/kits/{trabajo_id}` lleve al Web Checkout de Wompi en modo pruebas y que, al volver, el pedido quede `pagado` o `rechazado` sin depender del webhook.

**Architecture:** Comercio arma una URL firmada del Web Checkout (sin red). Al regresar, `apps/web` llama a `POST /v1/pagos/{transaccion_id}/sincronizar`. Comercio consulta la transacción a Wompi y la aplica con el mismo aplicador idempotente que usa el webhook.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, httpx, pytest-asyncio (SQLite en memoria); Next.js 16, React 19, TypeScript.

**Spec:** `docs/superpowers/specs/2026-10-02-pagos-wompi-sandbox-design.md`

## Global Constraints

- Solo sandbox. No existe modo `produccion` en esta rama.
- Con `WOMPI_MODO=sandbox`, las llaves deben empezar por `pub_test_`, `prv_test_`, `test_events_`, `test_integrity_`; si no, Comercio no arranca.
- `WOMPI_MODO=falso` sigue siendo el valor por omisión y no sale a la red.
- Nunca se persiste dato de tarjeta (SG-03). Solo referencia, id de transacción, estado, monto y medio.
- URL del checkout: `https://checkout.wompi.co/p/`. Moneda `COP`. Monto en centavos (total × 100).
- Firma de integridad: `firma_integridad(referencia, monto_centavos, secreto_integridad)` existente.
- Referencia por intento: `tukit-{pago_id}`.
- Clave de idempotencia: `"{transaccion_id}:{ESTADO_WOMPI}"` (estado en mayúsculas, p. ej. `APPROVED`).
- El navegador nunca habla con el backend: todo pasa por rutas de servidor de `apps/web`.
- Textos de UI en español, mismo tono que `VistaKits.tsx`.
- La rama arrancó con cambios ajenos sin commitear (`git status` los muestra; entre ellos `README.md` y `Makefile`). Nunca se hace `git add .` ni `git add -A`; en `README.md` se agrega solo la sección nueva con `git add -p`.
- Pruebas Python en Windows: `.venv/Scripts/python -m pytest <ruta> -q` desde la raíz.

## Review Focus

- **Recargar `/pago/resultado` tras un pago aprobado:** muestra el mismo estado y no escribe un segundo `pedido_pagado` en la bandeja. Prueba en Task 4.
- **Webhook que llega después de sincronizar:** se responde `repetido`. Prueba en Task 4.
- **PSE/Nequi que vuelve en PENDING y luego APPROVED:** la segunda sincronización sí avanza el pedido. Prueba en Task 4.
- **Llave de producción en `.env` con modo sandbox:** Comercio no arranca y nombra la llave. Prueba en Task 1.
- **Reintento tras un rechazo:** crea un pago nuevo con otra referencia, sin chocar con el índice único. Prueba en Task 3.

---

### Task 1: Pasarela — URL del Web Checkout y candado de llaves de prueba

**Files:**
- Modify: `servicios/comercio/tukit_comercio/pasarela.py`
- Test: `servicios/comercio/tests/test_pasarela.py`

**Interfaces:**
- Produces:
  - `URL_CHECKOUT = "https://checkout.wompi.co/p/"`
  - `url_checkout(*, llave_publica: str, referencia: str, monto_centavos: int, secreto_integridad: str, url_redireccion: str | None, correo: str) -> str`
  - `WompiSandbox.crear_transaccion(...)` devuelve `TransaccionCreada(referencia, transaccion_id=None, estado=EstadoPago.INICIADO, url_redireccion=<url_checkout>)` sin red.
  - `PasarelaFalsa.crear_transaccion(...)` devuelve `url_redireccion = urljoin(url_redireccion, "/pago/simulado") + "?ref=" + referencia` (o `None` si no se pasó `url_redireccion`) y guarda `monto_centavos` por referencia en `self.montos: dict[str, int]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_url_checkout_lleva_parametros_y_firma():
    url = url_checkout(llave_publica="pub_test_x", referencia="tukit-abc", monto_centavos=900000,
                       secreto_integridad="test_integrity_s", url_redireccion="http://localhost:3000/pago/resultado",
                       correo="ana@ejemplo.com")
    partes = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(partes.query))
    assert url.startswith("https://checkout.wompi.co/p/?")
    assert q["public-key"] == "pub_test_x"
    assert q["currency"] == "COP"
    assert q["amount-in-cents"] == "900000"
    assert q["reference"] == "tukit-abc"
    assert q["signature:integrity"] == firma_integridad("tukit-abc", 900000, "test_integrity_s")
    assert q["redirect-url"] == "http://localhost:3000/pago/resultado"
    assert q["customer-data:email"] == "ana@ejemplo.com"

async def test_wompi_sandbox_crear_no_sale_a_la_red():
    # cliente con MockTransport que falla si se llama
    ...
    assert creada.transaccion_id is None and creada.url_redireccion.startswith(URL_CHECKOUT)

async def test_pasarela_falsa_manda_a_la_pagina_simulada():
    creada = await PasarelaFalsa().crear_transaccion(referencia="tukit-1", monto_centavos=100, correo_cliente="a@b.co",
                                                      metodo="pse", url_redireccion="http://localhost:3000/pago/resultado")
    assert creada.url_redireccion == "http://localhost:3000/pago/simulado?ref=tukit-1"

@pytest.mark.parametrize("variable,valor", [("WOMPI_LLAVE_PUBLICA", "pub_prod_x"), ("WOMPI_LLAVE_PRIVADA", "prv_prod_x"),
                                            ("WOMPI_SECRETO_EVENTOS", "prod_events_x"), ("WOMPI_SECRETO_INTEGRIDAD", "prod_integrity_x")])
def test_sandbox_rechaza_llaves_que_no_son_de_prueba(monkeypatch, variable, valor):
    # las cuatro de prueba puestas, luego monkeypatch.setenv(variable, valor)
    with pytest.raises(RuntimeError, match=variable):
        pasarela_desde_entorno()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests/test_pasarela.py -q`
Expected: FAIL (`url_checkout` no existe).

- [ ] **Step 3: Implement**

`url_checkout` con `urllib.parse.urlencode(params, safe=":/")`; omite `redirect-url` si es `None`. `WompiSandbox.crear_transaccion` deja de usar `cliente`, `_token_aceptacion` y `POST /transactions` (bórralos). En `pasarela_desde_entorno`, tras comprobar que existen, comprueba los prefijos de los Global Constraints y lanza `RuntimeError` que nombre la variable. Actualiza el docstring del módulo.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests/test_pasarela.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add servicios/comercio/tukit_comercio/pasarela.py servicios/comercio/tests/test_pasarela.py
git commit -m "Comercio: Web Checkout de Wompi y candado de llaves de prueba"
```

### Task 2: Pasarela — consultar transacción y nueva clave de idempotencia

**Files:**
- Modify: `servicios/comercio/tukit_comercio/pasarela.py`
- Test: `servicios/comercio/tests/test_pasarela.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `EventoPasarela` gana `monto_centavos: int | None = None` y `metodo: str | None = None`.
  - `evento_id = f"{transaccion_id}:{estado_wompi.upper()}"` en `parsear_evento` de ambos adaptadores.
  - `_METODO_WOMPI = {"CARD": "tarjeta", "PSE": "pse", "NEQUI": "nequi"}`; otro valor da `metodo=None`.
  - `class PasarelaCaida(Exception)` y `class TransaccionNoExiste(Exception)`.
  - Puerto: `async def consultar_transaccion(self, transaccion_id: str) -> EventoPasarela`.
  - `WompiSandbox.consultar_transaccion`: `GET {base}/transactions/{id}` (sin auth). 404 lanza `TransaccionNoExiste`; error de red o 5xx lanza `PasarelaCaida`.
  - `PasarelaFalsa.consultar_transaccion("falsa-{APPROVED|DECLINED|PENDING}-{referencia}")`: monto de `self.montos[referencia]`, `metodo="pse"`. Formato inválido o referencia desconocida lanza `TransaccionNoExiste`.
  - `PasarelaFalsa.emitir_evento(..., monto_centavos: int)` (nuevo parámetro obligatorio) pone `amount_in_cents` y añade `"transaction.amount_in_cents"` a `signature.properties`.

- [ ] **Step 1: Write the failing tests**

```python
def test_parsear_evento_usa_transaccion_y_estado_como_clave():
    ev = PasarelaFalsa().emitir_evento(referencia="tukit-1", transaccion_id="tx-9", estado_wompi="APPROVED", monto_centavos=500)
    datos = PasarelaFalsa().parsear_evento(ev)
    assert datos.evento_id == "tx-9:APPROVED"
    assert datos.monto_centavos == 500

async def test_wompi_consultar_traduce_estado_monto_y_metodo():
    # MockTransport: GET /v1/transactions/tx-1 -> {"data": {"id": "tx-1", "reference": "tukit-1", "status": "APPROVED",
    #                                              "amount_in_cents": 900000, "payment_method_type": "CARD"}}
    ev = await WompiSandbox(cliente=cliente).consultar_transaccion("tx-1")
    assert (ev.evento_id, ev.referencia, ev.estado, ev.monto_centavos, ev.metodo) == \
        ("tx-1:APPROVED", "tukit-1", EstadoPago.APROBADO, 900000, "tarjeta")

async def test_wompi_consultar_404_es_transaccion_no_existe(): ...   # pytest.raises(TransaccionNoExiste)
async def test_wompi_consultar_500_es_pasarela_caida(): ...         # pytest.raises(PasarelaCaida)

async def test_falsa_consultar_descompone_el_id():
    p = PasarelaFalsa()
    await p.crear_transaccion(referencia="tukit-1", monto_centavos=700, correo_cliente="a@b.co", metodo="pse")
    ev = await p.consultar_transaccion("falsa-DECLINED-tukit-1")
    assert (ev.referencia, ev.estado, ev.monto_centavos) == ("tukit-1", EstadoPago.RECHAZADO, 700)
```

Ajusta `test_parsear_evento_saca_solo_id_referencia_transaccion_y_estado` a la nueva clave.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests/test_pasarela.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** según Interfaces. `WompiSandbox` reutiliza el patrón `propio = self.cliente is None` para el cliente httpx. El id falso se parte con `split("-", 2)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests/test_pasarela.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add servicios/comercio/tukit_comercio/pasarela.py servicios/comercio/tests/test_pasarela.py
git commit -m "Comercio: consultar transaccion en Wompi y clave de idempotencia por estado"
```

### Task 3: Comercio API — aplicador compartido, validación de monto y referencia por intento

**Files:**
- Modify: `servicios/comercio/tukit_comercio/api.py`
- Test: `servicios/comercio/tests/test_checkout.py`

**Interfaces:**
- Consumes: Task 2 (`EventoPasarela` con `monto_centavos` y `metodo`; `emitir_evento(..., monto_centavos=...)`).
- Produces:
  - `@dataclass(frozen=True) class ResultadoAplicacion: estado: str; pedido_id: uuid.UUID | None; estado_pago: str | None; estado_pedido: str | None; transicionado: bool`. Valores de `estado`: `"aplicado"`, `"repetido"`, `"sin_pago"`, `"monto_no_coincide"`.
  - `async def _aplicar_resultado(conexion, datos: EventoPasarela) -> ResultadoAplicacion` contiene el candado, la búsqueda por referencia, la validación de monto, la actualización del pago (estado, `transaccion_wompi`, y `metodo` si no es `None`), la transición y el outbox que hoy viven en `webhook_wompi`. En `repetido`, devuelve igualmente el estado actual del pago y del pedido si la referencia existe.
  - Monto distinto de `pago.monto * 100`: pago a `rechazado`, pedido sin mover, `estado="monto_no_coincide"`. Si `monto_centavos` es `None`, también se trata como no coincidente.
  - `webhook_wompi` conserva su forma de respuesta actual (`estado`, `evento_id`, `pago_estado`, `pedido_transicionado`) usando el aplicador.
  - `iniciar_pago` genera `pago_id` antes de llamar a la pasarela y usa `referencia = f"tukit-{pago_id}"`.

- [ ] **Step 1: Write the failing tests**

Actualiza `_flujo_hasta_webhook` para pasar `monto_centavos=9000 * 100` y `test_iniciar_pago_guarda_solo_referencia_y_estado` para exigir `cuerpo["referencia_wompi"] == f"tukit-{cuerpo['pago_id']}"`. Añade:

```python
async def test_webhook_con_monto_distinto_no_aprueba(cliente):
    # emitir_evento con monto_centavos=1 -> respuesta estado "monto_no_coincide";
    # pedido sigue pendiente_pago y pago queda rechazado

async def test_reintento_tras_rechazo_crea_otro_pago(cliente):
    # orden -> pago 1 -> webhook DECLINED -> POST /pago otra vez: 201,
    # referencia distinta de la primera; webhook APPROVED del segundo -> pedido pagado

async def test_webhook_guarda_el_metodo_que_reporta_wompi(cliente):
    # evento cuyo parsear_evento devuelve metodo="tarjeta" (monkeypatch del parseo o
    # payment_method_type en emitir_evento) -> pedido["pago"]["metodo"] == "tarjeta"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests/test_checkout.py -q`
Expected: FAIL en las nuevas y en la referencia.

- [ ] **Step 3: Implement** según Interfaces. Si el último test lo necesita, añade a `emitir_evento` un parámetro opcional `metodo_wompi: str | None = None` que escriba `payment_method_type`, y haz que `parsear_evento` lo traduzca con `_METODO_WOMPI`.

- [ ] **Step 4: Run all Comercio tests**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests -q`
Expected: PASS (todas, incluidas las de pedidos pagados y estado).

- [ ] **Step 5: Commit**

```bash
git add servicios/comercio/tukit_comercio/api.py servicios/comercio/tukit_comercio/pasarela.py servicios/comercio/tests/test_checkout.py
git commit -m "Comercio: aplicador de pago compartido, validacion de monto y referencia por intento"
```

### Task 4: Comercio API — endpoint de sincronización

**Files:**
- Modify: `servicios/comercio/tukit_comercio/api.py`
- Test: `servicios/comercio/tests/test_checkout.py`

**Interfaces:**
- Consumes: Task 3 (`_aplicar_resultado`, `ResultadoAplicacion`), Task 2 (`consultar_transaccion`, `PasarelaCaida`, `TransaccionNoExiste`).
- Produces: `POST /v1/pagos/{transaccion_id}/sincronizar` → `200 {"pedido_id": str, "total": int, "estado_pago": str, "estado_pedido": str}`.
  - `TransaccionNoExiste` → `ErrorDominio("transaccion_no_existe", ..., estado=404)`.
  - `PasarelaCaida` → `ErrorDominio("pasarela_no_disponible", ..., estado=502)`.
  - `ResultadoAplicacion.estado == "sin_pago"` → `ErrorDominio("pago_no_existe", ..., estado=404)`.

- [ ] **Step 1: Write the failing tests**

Helper: crea orden y pago con `url_redireccion="http://localhost:3000/pago/resultado"`, y devuelve `pedido_id` y `referencia`. El id de transacción es `f"falsa-{ESTADO}-{referencia}"`.

```python
async def test_sincronizar_aprobado_marca_pagado(cliente):
    r = await cliente.post(f"/v1/pagos/falsa-APPROVED-{ref}/sincronizar")
    assert r.status_code == 200
    assert r.json() == {"pedido_id": pedido_id, "total": 9000, "estado_pago": "aprobado", "estado_pedido": "pagado"}

async def test_sincronizar_dos_veces_no_duplica_el_aviso(cliente):
    # dos POST iguales -> mismo cuerpo; una sola fila tipo "pedido_pagado" en bandeja_salida

async def test_webhook_despues_de_sincronizar_es_repetido(cliente):
    # sincronizar APPROVED; luego emitir_evento(transaccion_id=f"falsa-APPROVED-{ref}", estado_wompi="APPROVED",
    # monto_centavos=900000) al webhook -> estado "repetido"

async def test_pendiente_y_luego_aprobado_avanza(cliente):
    # sincronizar falsa-PENDING-ref -> estado_pago "iniciado", estado_pedido "pendiente_pago"
    # sincronizar falsa-APPROVED-ref -> "aprobado"/"pagado"

async def test_sincronizar_rechazado_deja_pendiente(cliente):  # "rechazado"/"pendiente_pago"
async def test_sincronizar_transaccion_desconocida_es_404(cliente):  # "falsa-APPROVED-tukit-nada" -> 404 transaccion_no_existe
async def test_sincronizar_con_pasarela_caida_es_502(cliente):  # pasarela doble que lanza PasarelaCaida
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests/test_checkout.py -q -k sincronizar`
Expected: FAIL con 404 (la ruta no existe).

- [ ] **Step 3: Implement** el endpoint en la sección de escritura, después del webhook. Abre una sesión, llama al aplicador y relee `pedido.total` para la respuesta.

- [ ] **Step 4: Run all Comercio tests**

Run: `.venv/Scripts/python -m pytest servicios/comercio/tests -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add servicios/comercio/tukit_comercio/api.py servicios/comercio/tests/test_checkout.py
git commit -m "Comercio: sincronizar el pago con Wompi al regreso del acudiente"
```

### Task 5: Gateway — prefijo `/v1/pagos`

**Files:**
- Modify: `servicios/gateway/tukit_gateway/api.py` (tabla de prefijos, junto a `/v1/ordenes`)
- Test: `servicios/gateway/tests/test_ruteo.py` (parametrización de `test_cada_prefijo_va_a_su_servicio`)

- [ ] **Step 1:** Añade `("/v1/pagos/abc/sincronizar", "comercio")` a la parametrización.
- [ ] **Step 2:** Run `.venv/Scripts/python -m pytest servicios/gateway/tests/test_ruteo.py -q`. Expected: FAIL en el caso nuevo.
- [ ] **Step 3:** Añade `"/v1/pagos": "comercio"` con un comentario de una línea.
- [ ] **Step 4:** Repite el comando. Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add servicios/gateway
git commit -m "Gateway: /v1/pagos va a Comercio"
```

### Task 6: Contrato TS y ruta de servidor en `apps/web`

**Files:**
- Modify: `libs/ts/tukit-contrato/src/contrato.ts` (junto a `Checkout`)
- Modify: `libs/ts/tukit-contrato/src/origen.ts` (junto a `iniciarCheckout`)
- Modify: `libs/ts/tukit-contrato/src/cliente-http.ts` (junto a `iniciarCheckout`)
- Modify: `libs/ts/tukit-contrato/src/indice.ts` (exportar el tipo, si los tipos se reexportan ahí)
- Create: `apps/web/src/app/api/pagos/[transaccion_id]/sincronizar/route.ts`
- Modify: `apps/web/src/lib/api-navegador.ts`

**Interfaces:**
- Consumes: Task 4 (forma de la respuesta).
- Produces:
  - `export interface ResultadoPago { pedido_id: string; total: number; estado_pago: "iniciado" | "aprobado" | "rechazado" | "reembolsado"; estado_pedido: string }`
  - `OrigenDatos.sincronizarPago(transaccionId: string): Promise<ResultadoPago>`, implementado en `ClienteApi` como `POST /v1/pagos/${encodeURIComponent(id)}/sincronizar`.
  - Ruta `POST /api/pagos/[transaccion_id]/sincronizar` con el mismo patrón que `api/trabajos/[trabajo_id]/ordenar/route.ts` (`origenDeDatos()`, `respuestaDeError`).
  - `api-navegador.ts`: `export async function sincronizarPago(transaccionId: string): Promise<ResultadoPago>`.

- [ ] **Step 1:** Implementa los tres cambios del contrato y las dos piezas de `apps/web`.
- [ ] **Step 2:** Run `npm run typecheck --workspace @tukit/web` y `npm run lint --workspace @tukit/web`. Expected: sin errores.
- [ ] **Step 3: Commit**

```bash
git add libs/ts/tukit-contrato/src apps/web/src/app/api/pagos apps/web/src/lib/api-navegador.ts
git commit -m "Contrato y web: sincronizarPago y su ruta de servidor"
```

### Task 7: Páginas de resultado y de simulación, y el botón Pagar

**Files:**
- Create: `apps/web/src/app/pago/resultado/page.tsx` (servidor: `await searchParams`, pasa `id` al cliente)
- Create: `apps/web/src/app/pago/resultado/ResultadoPago.tsx` (`"use client"`)
- Create: `apps/web/src/app/pago/simulado/page.tsx`
- Create: `apps/web/src/app/pago/Pago.module.css`
- Modify: `apps/web/src/app/kits/[trabajo_id]/VistaKits.tsx` (función `pagar` del componente `Checkout`)

**Interfaces:**
- Consumes: Task 6 (`sincronizarPago`, `ResultadoPago`), `formatearPesos` (ya usado en `VistaKits.tsx`).

**Comportamiento de `ResultadoPago`:**
- Sin `id`: "No encontramos el pago que intentas ver." y enlace a `/dashboard`.
- `aprobado`: título "¡Pago aprobado!", total con `formatearPesos`, "Pedido {primeros 8 caracteres de pedido_id}", botón "Ir a mi panel" a `/dashboard`.
- `rechazado`: título "Tu pago no fue aprobado", texto "No se hizo ningún cobro. Puedes intentarlo de nuevo.", botón "Volver" con `history.back()`.
- `iniciado`: "Estamos confirmando tu pago…". Reconsulta cada 3 s, hasta 20 intentos. Al agotarlos: "Tu banco aún no confirma. Verás el estado en tu panel."
- Error `502`: "No pudimos confirmar todavía", reintento con el mismo ciclo. Otros errores: el mensaje de `FalloApi`.

**`/pago/simulado`:** lee `ref`. Muestra "Pasarela simulada (modo de pruebas sin Wompi)" y los botones "Aprobar pago" y "Rechazar pago". Navegan a `/pago/resultado?id=falsa-APPROVED-{ref}` y `/pago/resultado?id=falsa-DECLINED-{ref}`.

**`VistaKits.tsx`:** `url_redireccion: `${window.location.origin}/pago/resultado``; si `checkout.url_redireccion` es `null`, muestra el error "No pudimos abrir la pasarela de pago." y reactiva el botón. Elimina el `window.alert`.

- [ ] **Step 1:** Implementa las páginas y el cambio en `VistaKits.tsx`, con estilos que reutilicen los tokens de `globals.css`.
- [ ] **Step 2:** Run `npm run typecheck --workspace @tukit/web`, `npm run lint --workspace @tukit/web` y `npm run build --workspace @tukit/web`. Expected: sin errores.
- [ ] **Step 3: Recorrido en modo falso.** Levanta todo con `.\tukit.ps1 arriba` y `npm run dev:web`. Abre un kit publicado y paga. Expected: llega a `/pago/simulado`. "Aprobar pago" muestra "¡Pago aprobado!" y el pedido aparece `pagado` en `GET http://127.0.0.1:8010/v1/comercio/pedidos`. Recargar la página muestra lo mismo. Repite con "Rechazar pago".
- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/pago apps/web/src/app/kits
git commit -m "Web: el boton Pagar lleva a la pasarela y la pagina de resultado confirma el pago"
```

### Task 8: Configuración, README y prueba con Wompi sandbox

**Files:**
- Modify: `.env.ejemplo` (bloque de Wompi del spec, sección 6)
- Modify: `README.md` (sección "Pagos de prueba con Wompi")

- [ ] **Step 1:** Verifica los datos de prueba contra docs.wompi.co (tarjetas, Nequi, PSE) y corrige la tabla del spec si algo cambió.
- [ ] **Step 2:** Escribe el bloque de `.env.ejemplo` y la sección del README: dónde sacar las llaves de prueba, la tabla de datos de prueba y el túnel opcional para el webhook (`cloudflared tunnel --url http://127.0.0.1:8010` más la URL de eventos `https://<túnel>/v1/webhooks/wompi`).
- [ ] **Step 3: Prueba sandbox (requiere las llaves en `.env`).** Pon `WOMPI_MODO=sandbox` y reinicia con `.\tukit.ps1 abajo` y `.\tukit.ps1 arriba`. Paga un kit con `4242 4242 4242 4242`: debe abrir `checkout.wompi.co`, volver con "¡Pago aprobado!" y dejar el pedido `pagado`. Repite con `4111 1111 1111 1111` (rechazado) y con PSE "Banco que aprueba". Si las llaves no están, deja este paso sin marcar y dilo en el resumen.
- [ ] **Step 4:** Run `.venv/Scripts/python -m pytest servicios/comercio/tests servicios/gateway/tests -q`. Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add .env.ejemplo
git add -p README.md   # solo los trozos de la seccion de Wompi
git commit -m "Docs: como probar pagos con Wompi sandbox"
```
