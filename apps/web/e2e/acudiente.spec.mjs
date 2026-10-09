// El flujo del acudiente en el navegador, de punta a punta: entrar, ver la solicitud aprobada, los
// tres kits, pagar el recomendado y ver el pedido pagado en el tablero.
//
// Lo que el navegador no puede hacer queda por el gateway, en `stack.mjs`:
//   - el registro: vive en `/empezar`, que hoy responde 500 (H-A-01, primera prueba);
//   - la subida de la lista: la percepcion necesita el modelo. Se escribe lo mismo que deja la subida
//     tras percibir (una lista `sugerencia_padre` con el `usuario_id` del acudiente) y un administrador
//     la cierra; el poller arma el trabajo por la ruta rapida (decision N-45);
//   - el webhook de la pasarela falsa, firmado como `PasarelaFalsa.emitir_evento`.

import { expect, test } from "@playwright/test";

import * as stack from "./stack.mjs";

const WEB = process.env.TUKIT_WEB_URL ?? "http://localhost:3000";
const XFAIL = !process.env.QA_RUNXFAIL;

let contexto;
let pagina;
let intentos;
let acudiente;
let vista;
let pedido;

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

test("empezar: el formulario del hogar carga", async ({ page }) => {
  test.fail(
    XFAIL,
    "H-A-01: /empezar pide GET /v1/grados-canonicos y la tabla kit_canonico no existe; la pagina responde 500",
  );
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
    vista = await stack.trabajoDelAcudiente(acudiente.token, lista.versionId);
    if (vista.estado !== "publicado") {
      throw new Error(`el trabajo ${vista.trabajo_id} quedo en ${vista.estado}`);
    }

    contexto = await browser.newContext();
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
    await expect(pagina.getByRole("heading", { name: "Tus tres kits están listos" })).toBeVisible();
  });

  test("esperando: un trabajo ya publicado salta solo a sus kits", async () => {
    await pagina.goto(`${WEB}/esperando/${vista.trabajo_id}`);
    await pagina.waitForURL(`${WEB}/kits/${vista.trabajo_id}`);
    await expect(pagina.getByRole("heading", { name: "Tus tres kits están listos" })).toBeVisible();
  });

  test("kits: tres pestañas con los totales del trabajo y una sola recomendada", async () => {
    const pestanas = pagina.getByRole("tablist", { name: "Los tres kits" }).getByRole("tab");
    await expect(pestanas).toHaveCount(3);
    expect(vista.kits.map((kit) => kit.perfil).sort()).toEqual(["Ahorrador", "Fan", "Premium"]);

    const recomendada = pestanas.filter({ hasText: "Te recomendamos este" });
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

  test("pago: la entrega crea el pedido del kit recomendado y el webhook aprobado lo deja pagado", async () => {
    const perfil = vista.recomendado.perfil;
    const kit = kitDe(perfil);
    await pagina
      .getByRole("tablist", { name: "Los tres kits" })
      .getByRole("tab")
      .filter({ hasText: perfil })
      .click();
    await pagina.getByRole("button", { name: "Ir a pagar" }).click();
    await pagina.getByLabel("Nombre de quien recibe").fill(stack.ENTREGA_FICTICIA.destinatario);
    await pagina.getByLabel("Dirección").fill(stack.ENTREGA_FICTICIA.direccion);
    await pagina.getByLabel("Ciudad").fill(stack.ENTREGA_FICTICIA.ciudad);
    // Con sesion no se vuelve a pedir el correo: el comprobante va al de la cuenta.
    await expect(pagina.getByLabel("Correo para el comprobante")).toHaveCount(0);
    await expect(pagina.getByText(`El comprobante va a ${acudiente.correo}`)).toBeVisible();

    const orden = pagina.waitForResponse(
      (r) => r.url().endsWith(`/api/trabajos/${vista.trabajo_id}/ordenar`) && r.request().method() === "POST",
    );
    // La pasarela falsa no redirige: la web avisa con un alert que el pedido quedo creado. Se acepta
    // en cuanto aparece; mientras esta abierto, la pagina no entrega el cuerpo de la respuesta.
    const dialogo = new Promise((listo) => {
      pagina.once("dialog", async (aviso) => {
        const texto = aviso.message();
        await aviso.accept();
        listo(texto);
      });
    });
    await pagina.getByRole("button", { name: /^Pagar / }).click();

    const respuesta = await orden;
    const mensaje = await dialogo;
    expect(respuesta.status()).toBe(201);
    pedido = await respuesta.json();
    anotar({ pedido_id: pedido.pedido_id, perfil, total: pedido.total });
    expect(mensaje).toContain(`Pedido ${pedido.pedido_id} creado por`);
    expect(stack.pesos(mensaje.split("creado por")[1])).toBe(kit.total);
    expect([pedido.estado, pedido.total]).toEqual(["iniciado", kit.total]);

    const webhook = await stack.api("POST", "/v1/webhooks/wompi", {
      cuerpo: stack.eventoAprobado(pedido.referencia_wompi, pedido.transaccion_wompi),
    });
    expect(webhook.estado).toBe(200);
    expect(webhook.json.pedido_transicionado).toBe(true);
    const pagada = await stack.exigir(200, "GET", `/v1/ordenes/${pedido.pedido_id}`, {
      token: acudiente.token,
    });
    expect([pagada.estado, pagada.trabajo_id, pagada.total]).toEqual(["pagado", vista.trabajo_id, kit.total]);
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
});
