// El flujo del acudiente en el navegador, de punta a punta: entrar, ver la solicitud aprobada, sus
// kits, pagar el recomendado en la pasarela simulada y ver el pedido pagado en el tablero.
//
// Desde ADR 0030 (efb0827) un pedido sin personaje trae dos kits, Ahorrador y Premium; el Fan solo
// sale si se pide. Los titulos de las pruebas conservan «tres kits» por trazabilidad con la matriz y
// las evidencias de 58b9e47 (decision N-97).
//
// Lo que el navegador no puede hacer queda por el gateway, en `stack.mjs`:
//   - el registro: `/empezar` ya carga (H-A-01 corregido, primera prueba), pero registrarse ahi
//     necesita la subida de la lista;
//   - la subida de la lista: la percepcion necesita el modelo. Se escribe lo mismo que deja la subida
//     tras percibir (una lista `sugerencia_padre` con el `usuario_id` del acudiente) y un administrador
//     la cierra; el poller arma el trabajo por la ruta rapida (decision N-45).
//
// El pago va entero por el navegador: con WOMPI_MODO=falso, comercio manda al acudiente a
// `/pago/simulado`, que desde oe5 aprueba solo y pasa a `/pago/resultado`, que sincroniza el pago con
// la pasarela falsa.
//
// Cada contexto del navegador llega a la puerta con la IP de su familia (`extraHTTPHeaders`; el
// servidor de Next la reenvia), porque el limite de tasa cuenta por IP (ADR 0047, decision N-120). La
// direccion va sin Google Places: la web arranca sin llave de Maps y la guardia cuenta y aborta
// cualquier intento (ADR 0044, decision N-129). Sin llave, desde oe5 el campo es el de OpenStreetMap
// (ADR 0049); la web arranca sin `TUKIT_NOMINATIM_CONTACTO`, asi que no se busca, y la guardia cuenta
// y aborta Nominatim y los mosaicos del mapa (decision N-147).

import { expect, test } from "@playwright/test";

import * as stack from "./stack.mjs";

const WEB = process.env.TUKIT_WEB_URL ?? "http://localhost:3000";

let contexto;
let pagina;
let intentos;
let acudiente;
let vista;
let pedido;

// La primera prueba usa el `page` de Playwright: su contexto tambien llega como una familia.
test.use({ extraHTTPHeaders: { [stack.CABECERA_IP]: stack.ipDeFamilia() } });

function anotar(propiedades = {}) {
  const { annotations } = test.info();
  for (const [type, valor] of Object.entries(propiedades)) {
    annotations.push({ type, description: String(valor) });
  }
}

function kitDe(perfil) {
  return vista.kits.find((kit) => kit.perfil === perfil);
}

test.beforeEach(() => {
  anotar({ ensayo_id: "E2E-UI", correlacion_id: stack.CORRELACION });
});

// H-A-01 se corrigio en c57c0b3 (migracion de `kit_canonico`): queda como prueba de no regresion.
test("empezar: el formulario del hogar carga", async ({ page }) => {
  anotar({ hallazgo: "H-A-01" });
  await stack.guardiaDeRed(page.context());
  const respuesta = await page.goto(`${WEB}/empezar`);
  anotar({ codigo_empezar: respuesta.status() });
  expect(respuesta.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Armemos el kit de tu hogar" })).toBeVisible();
});

// El resto es un solo recorrido: cada paso parte de donde dejo el anterior.
test.describe("flujo del acudiente", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(async ({ browser }) => {
    await stack.stackArriba();
    const tokenAdmin = await stack.abrirSesion(stack.ADMIN_DEMO);
    acudiente = await stack.registrarAcudiente();
    const lista = await stack.listaAprobadaDelAcudiente(tokenAdmin, acudiente.usuarioId);
    vista = await stack.trabajoDelAcudiente(acudiente, lista.versionId);
    if (vista.estado !== "publicado") {
      throw new Error(`el trabajo ${vista.trabajo_id} quedo en ${vista.estado}`);
    }

    contexto = await browser.newContext({ extraHTTPHeaders: { [stack.CABECERA_IP]: acudiente.ip } });
    intentos = await stack.guardiaDeRed(contexto);
    pagina = await contexto.newPage();
  });

  test.afterAll(async () => {
    await contexto?.close();
  });

  test("ingresar: el acudiente entra con su correo y su clave y llega a su tablero", async () => {
    await pagina.goto(`${WEB}/ingresar`);
    await pagina.getByLabel("Correo").fill(acudiente.correo);
    await pagina.getByLabel("Clave").fill(acudiente.clave);
    await pagina.getByRole("button", { name: "Entrar" }).click();

    await pagina.waitForURL(`${WEB}/dashboard`);
    await expect(pagina.getByRole("heading", { level: 1 })).toContainText("Hola");
    const cookies = await contexto.cookies(WEB);
    expect(cookies.find((c) => c.name === "tukit_sesion")?.httpOnly).toBe(true);
  });

  test("tablero: la solicitud aprobada lleva a los tres kits", async () => {
    anotar({ trabajo_id: vista.trabajo_id });
    const solicitudes = pagina.locator("#solicitudes");
    await expect(solicitudes.getByText(stack.GRADO, { exact: true })).toBeVisible();
    await solicitudes.getByRole("link", { name: "Ver mis kits" }).click();

    await pagina.waitForURL(`${WEB}/kits/${vista.trabajo_id}`);
    await expect(pagina.getByRole("heading", { name: "Tus kits están listos" })).toBeVisible();
  });

  test("esperando: un trabajo ya publicado salta solo a sus kits", async () => {
    await pagina.goto(`${WEB}/esperando/${vista.trabajo_id}`);
    await pagina.waitForURL(`${WEB}/kits/${vista.trabajo_id}`);
    await expect(pagina.getByRole("heading", { name: "Tus kits están listos" })).toBeVisible();
  });

  test("kits: tres pestañas con los totales del trabajo y una sola recomendada", async () => {
    const pestanas = pagina.getByRole("tablist", { name: "Ver otro kit" }).getByRole("tab");
    // Sin personaje, Ahorrador y Premium (ADR 0030, `optimizador.quiere_fan`).
    expect(vista.kits.map((kit) => kit.perfil).sort()).toEqual(["Ahorrador", "Premium"]);
    await expect(pestanas).toHaveCount(vista.kits.length);

    // La recomendada lleva la estrella con el rotulo como nombre accesible (y como `title`).
    const recomendada = pestanas.filter({ has: pagina.getByLabel("Te recomendamos este") });
    await expect(recomendada).toHaveCount(1);
    await expect(recomendada).toContainText(vista.recomendado.perfil);
    await expect(recomendada).toHaveAttribute("aria-selected", "true");

    const pie = pagina.locator("footer").filter({ hasText: "Total del kit" });
    for (const kit of vista.kits) {
      const pestana = pestanas.filter({ hasText: kit.perfil });
      expect(stack.pesos(await pestana.locator(".cifra").textContent())).toBe(kit.total);
      await pestana.click();
      await expect(pestana).toHaveAttribute("aria-selected", "true");
      await expect(pie).toContainText(`Total del kit ${kit.perfil}`);
      expect(stack.pesos(await pie.locator(".cifra").textContent())).toBe(kit.total);
      anotar({ [`total_${kit.perfil}`]: kit.total });
    }
  });

  test("pago: la entrega crea el pedido del kit recomendado y la pasarela simulada lo deja pagado", async () => {
    const perfil = vista.recomendado.perfil;
    const kit = kitDe(perfil);
    await pagina
      .getByRole("tablist", { name: "Ver otro kit" })
      .getByRole("tab")
      .filter({ hasText: perfil })
      .click();
    await pagina.getByRole("button", { name: "Ir a pagar" }).click();
    await pagina.getByLabel("Nombre de quien recibe").fill(stack.ENTREGA_FICTICIA.destinatario);
    const direccion = pagina.getByLabel("Dirección");
    await direccion.fill(stack.ENTREGA_FICTICIA.direccion);
    // Sin llave de Maps no hay sugerencias de Google (ADR 0044). Desde oe5 el campo es el de
    // OpenStreetMap (ADR 0049): la busqueda es explicita (boton Buscar) y aqui no se pulsa, asi que la
    // direccion queda como texto libre, sin lista de resultados ni pin (decision N-147).
    await expect(pagina.getByRole("listbox", { name: "Direcciones sugeridas" })).toHaveCount(0);
    await expect(pagina.getByRole("listbox", { name: "Direcciones encontradas" })).toBeHidden();
    await expect(pagina.getByText("Ubicación confirmada en el mapa.")).toHaveCount(0);
    await pagina.getByLabel("Ciudad").fill(stack.ENTREGA_FICTICIA.ciudad);
    // Con la ciudad en Bogota se enciende la localidad, que es obligatoria.
    await pagina.getByLabel("Localidad").selectOption(stack.ENTREGA_FICTICIA.localidad);
    // Con sesion no se vuelve a pedir el correo: el comprobante va al de la cuenta.
    await expect(pagina.getByLabel("Correo para el comprobante")).toHaveCount(0);
    await expect(pagina.getByText(`El comprobante va a ${acudiente.correo}`)).toBeVisible();

    // La web navega a la pasarela apenas llega la respuesta, y el navegador suelta su cuerpo: se lee
    // al pasar, sin cambiarla.
    const orden = new Promise((listo) => {
      pagina.route(`**/api/trabajos/${vista.trabajo_id}/ordenar`, async (ruta) => {
        const respuesta = await ruta.fetch();
        listo({ estado: respuesta.status(), cuerpo: await respuesta.json() });
        await ruta.fulfill({ response: respuesta });
      });
    });
    await pagina.getByRole("button", { name: /^Pagar / }).click();
    const respuesta = await orden;
    expect(respuesta.estado).toBe(201);
    pedido = respuesta.cuerpo;
    anotar({ pedido_id: pedido.pedido_id, perfil, total: pedido.total });
    expect([pedido.estado, pedido.total, pedido.widget]).toEqual(["iniciado", kit.total, null]);

    // WOMPI_MODO=falso: la pasarela falsa manda a `/pago/simulado?ref=<referencia>` (pasarela.py,
    // `PasarelaFalsa.crear_transaccion`). Desde oe5 (c54075c) esa pagina es neutra y no tiene boton:
    // aprueba sola y pasa a `/pago/resultado`, que sincroniza (decision N-147).
    const simulado = `${WEB}/pago/simulado?ref=${encodeURIComponent(pedido.referencia_wompi)}`;
    expect(pedido.url_redireccion).toBe(simulado);
    const sincronizada = pagina.waitForResponse(
      (r) => /\/api\/pagos\/[^/]+\/sincronizar$/.test(r.url()) && r.request().method() === "POST",
    );
    await pagina.waitForURL(
      `${WEB}/pago/resultado?id=${encodeURIComponent(`falsa-APPROVED-${pedido.referencia_wompi}`)}`,
    );
    const resultado = await (await sincronizada).json();
    anotar({ estado_pago: resultado.estado_pago, estado_pedido: resultado.estado_pedido });
    expect([resultado.pedido_id, resultado.estado_pago, resultado.estado_pedido, resultado.total]).toEqual([
      pedido.pedido_id,
      "aprobado",
      "pagado",
      kit.total,
    ]);
    await expect(pagina.getByRole("heading", { name: "¡Pago aprobado!" })).toBeVisible();

    // El pedido se lee con la sesion del acudiente: `/v1/ordenes/{id}` ya no se sirve por la puerta (173ee80).
    const pagada = await stack.exigir(200, "GET", `/v1/comercio/mis-pedidos/${pedido.pedido_id}`, {
      token: acudiente.token,
      ip: acudiente.ip,
    });
    expect([pagada.estado, pagada.trabajo_id, pagada.total]).toEqual(["pagado", vista.trabajo_id, kit.total]);
  });

  // ADR 0044: sin llave de Maps la direccion es la que se escribio y el pago no la espera. El pedido
  // guarda lo escrito, la localidad elegida de la lista y ningun lugar de Google.
  test("direccion: sin sugerencias, el pedido guarda la direccion escrita y la localidad elegida", async () => {
    anotar({ nfr: "NFR-DIS-05" });
    const leido = await stack.exigir(200, "GET", `/v1/comercio/mis-pedidos/${pedido.pedido_id}`, {
      token: acudiente.token,
      ip: acudiente.ip,
    });
    const envio = leido.envio ?? {};
    anotar({ localidad: envio.localidad, google_place_id: envio.google_place_id });
    expect([envio.direccion, envio.ciudad, envio.localidad, envio.google_place_id]).toEqual([
      stack.ENTREGA_FICTICIA.direccion,
      stack.ENTREGA_FICTICIA.ciudad,
      stack.ENTREGA_FICTICIA.localidad,
      null,
    ]);
  });

  test("tablero: el pedido pagado aparece en Mis pedidos con su total", async () => {
    await pagina.goto(`${WEB}/dashboard`);
    const fila = pagina
      .locator("#pedidos")
      .getByRole("row")
      .filter({ hasText: pedido.pedido_id.slice(0, 8).toUpperCase() });
    await expect(fila).toHaveCount(1);
    await expect(fila).toContainText("Pagado");
    expect(stack.pesos(await fila.locator(".cifra").textContent())).toBe(pedido.total);
  });

  test("costo: el navegador no hizo ninguna peticion a Gemini", async () => {
    anotar({
      llamadas_reales_gemini: intentos.gemini.length,
      peticiones_externas_abortadas: intentos.externas.length,
    });
    expect(intentos.gemini).toEqual([]);
  });

  test("costo: el navegador no hizo ninguna peticion a Google Places", async () => {
    anotar({ nfr: "NFR-COS-01", intentos_places: intentos.places.length });
    expect(intentos.places).toEqual([]);
  });

  test("costo: el navegador no hizo ninguna peticion a OpenStreetMap", async () => {
    anotar({ nfr: "NFR-COS-01", intentos_osm: intentos.osm.length });
    expect(intentos.osm).toEqual([]);
  });
});
