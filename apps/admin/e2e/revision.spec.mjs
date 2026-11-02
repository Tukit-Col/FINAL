// La revision humana en la consola, en el navegador: el administrador entra por la web, encuentra en
// la cola el trabajo que espera, cambia un producto en un solo kit, marca sin coincidencia el renglon
// que el sistema no entendio y publica.
//
// Lo que el navegador no puede hacer queda por el gateway, en `stack.mjs`: la lista del colegio
// ficticio (sin revisar, con un renglon que nadie reconoce) y el pedido del acudiente ficticio, que
// corre el pipeline y deja el trabajo en `espera_revision`.
//
// Cada prueba lee el trabajo de nuevo y abre su propia pagina, asi que no depende de las anteriores:
// con `QA_RUNXFAIL=1`, una que falla no deja a las demas sin correr.
//
// Desde `d4ea7cb` la cola pone en tarjetas los trabajos de acudiente que esperan (`af8db6b`) y la
// matriz saca de la tabla los renglones sin producto en ningun kit: los pendientes van arriba, en
// «Resolver» (`MatrizComparacion`, panel de avisos).
//
// El navegador del administrador llega a la puerta con la IP del equipo (`extraHTTPHeaders`; el
// servidor de Next la reenvia), la misma de sus llamadas por el gateway, porque el limite de tasa
// cuenta por IP (ADR 0047, decision N-120).

import { expect, test } from "@playwright/test";

import * as stack from "./stack.mjs";

const WEB = process.env.TUKIT_WEB_URL ?? "http://localhost:3000";
const ADMIN = process.env.TUKIT_ADMIN_URL ?? "http://localhost:3001";
const XFAIL = !process.env.QA_RUNXFAIL;
// El orden de las columnas de la matriz (`MatrizComparacion.ORDEN_PERFIL`).
const ORDEN_PERFIL = ["Ahorrador", "Fan", "A tu Medida", "Premium"];

let contexto;
let pagina;
let intentos;
let tokenAdmin;
let trabajoId;

function anotar(propiedades = {}) {
  const { annotations } = test.info();
  for (const [type, valor] of Object.entries(propiedades)) {
    annotations.push({ type, description: String(valor) });
  }
}

function kitDe(vista, perfil) {
  return vista.kits.find((kit) => kit.perfil === perfil);
}

function lineaDe(vista, perfil, itemId) {
  return kitDe(vista, perfil).lineas.find((linea) => linea.item_id === itemId);
}

function sumaDeSubtotales(kit) {
  return kit.lineas.reduce((suma, linea) => suma + (linea.subtotal_linea ?? 0), 0);
}

/** La fila de la matriz de ese renglon: el bloque con su descripcion y una celda por perfil. */
function filaDe(descripcion) {
  return pagina
    .locator('[class*="matrizConcepto"]')
    .getByText(descripcion, { exact: true })
    .locator("xpath=ancestor::div[.//button][1]");
}

/** Abre la celda (renglon, perfil) de la matriz y despliega su linea. Devuelve el panel de edicion. */
async function abrirCelda(vista, descripcion, perfil) {
  const perfiles = ORDEN_PERFIL.filter((p) => kitDe(vista, p));
  await filaDe(descripcion).getByRole("button").nth(perfiles.indexOf(perfil)).click();
  const detalle = pagina
    .locator('[class*="matrizDetalleNota"]')
    .filter({ hasText: `Editando ${perfil}.` })
    .locator("xpath=..");
  await expect(detalle).toBeVisible();
  // Lo resuelto nace plegado y lo pendiente abierto (`LineaRevision`).
  const linea = detalle.locator("details");
  if (!(await linea.evaluate((elemento) => elemento.open))) await linea.locator("summary").click();
  // El cuerpo de la linea se pinta solo cuando esta abierta.
  await expect(detalle.getByRole("button", { name: "Sin coincidencia" })).toBeVisible();
  return detalle;
}

/** Abre en el panel de avisos el renglon pendiente sin producto en ningun kit. Devuelve su panel. */
async function abrirAviso(descripcion) {
  const aviso = pagina
    .locator('[class*="avisoItem"]')
    .filter({ has: pagina.locator('[class*="avisoConcepto"]').getByText(descripcion, { exact: true }) });
  await aviso.getByRole("button", { name: "Resolver" }).click();
  await expect(aviso.getByText("Resolver este renglón lo deja igual en todos los kits.")).toBeVisible();
  const linea = aviso.locator("details");
  if (!(await linea.evaluate((elemento) => elemento.open))) await linea.locator("summary").click();
  await expect(aviso.getByRole("button", { name: "Sin coincidencia" })).toBeVisible();
  return aviso;
}

/** La etiqueta de estado de resolucion que pinta el resumen de la linea abierta. */
async function estadoEnPantalla(detalle) {
  const estados = ["RESUELTO_AUTO", "AMBIGUO", "SIN_MATCH", "HUECO_CATALOGO"];
  const etiquetas = await detalle.locator("summary").locator("span span").allTextContents();
  return etiquetas.filter((texto) => estados.includes(texto));
}

/** El total que pinta la cabecera de la matriz para ese perfil. */
async function totalEnCabecera(perfil) {
  const columna = pagina.locator('[class*="matrizColTitulo"]').filter({ hasText: perfil });
  return stack.pesos(await columna.locator(".cifra").textContent());
}

test.beforeAll(async ({ browser }) => {
  await stack.stackArriba();
  tokenAdmin = await stack.abrirSesion(stack.ADMIN_DEMO);
  const acudiente = await stack.registrarAcudiente();
  const lista = await stack.listaSinRevisar(tokenAdmin);
  const trabajo = await stack.trabajoEnRevision(acudiente, lista.colegioId);
  trabajoId = trabajo.trabajo_id;
  if (trabajo.estado !== "espera_revision") {
    throw new Error(`el trabajo ${trabajoId} quedo en ${trabajo.estado}`);
  }

  contexto = await browser.newContext({ extraHTTPHeaders: { [stack.CABECERA_IP]: stack.IP_DEL_EQUIPO } });
  intentos = await stack.guardiaDeRed(contexto);
  pagina = await contexto.newPage();
  // El back-office no tiene login propio: se entra por el de la web, que pone la cookie de sesion y
  // manda al administrador a la consola.
  await pagina.goto(`${WEB}/ingresar`);
  await pagina.getByLabel("Correo").fill(stack.ADMIN_DEMO.correo);
  await pagina.getByLabel("Clave").fill(stack.ADMIN_DEMO.clave);
  await pagina.getByRole("button", { name: "Entrar" }).click();
  await pagina.waitForURL(`${ADMIN}/`);
});

test.afterAll(async () => {
  await contexto?.close();
});

test.beforeEach(() => {
  anotar({ ensayo_id: "E2E-UI", correlacion_id: stack.CORRELACION, trabajo_id: trabajoId });
});

test("ingresar: el administrador entra por la web y queda en el panel de la consola", async () => {
  await pagina.goto(`${ADMIN}/`);
  await expect(pagina.getByRole("heading", { level: 1, name: "Panel" })).toBeVisible();
  const cookies = await contexto.cookies(ADMIN);
  expect(cookies.find((c) => c.name === "tukit_sesion")?.httpOnly).toBe(true);
});

test("cola: el trabajo en espera aparece con sus pendientes y lleva a su detalle", async () => {
  const vista = await stack.vistaAdmin(tokenAdmin, trabajoId);
  const pendientes = vista.lineas_pendientes.length;
  anotar({ lineas_pendientes: pendientes });
  expect(pendientes).toBeGreaterThan(0);

  await pagina.goto(`${ADMIN}/cola`);
  // Una tarjeta por trabajo de acudiente en espera; el enlace con el colegio lleva el id como `title`.
  const tarjeta = pagina.locator("article").filter({ has: pagina.locator(`a[title="${trabajoId}"]`) });
  await expect(tarjeta).toHaveCount(1);
  await expect(tarjeta.getByText(`${pendientes} por resolver`, { exact: true })).toBeVisible();
  await tarjeta.getByRole("link", { name: "Revisar" }).click();

  await pagina.waitForURL(`${ADMIN}/trabajos/${trabajoId}`);
  await expect(pagina.getByRole("heading", { level: 1 })).toContainText(trabajoId);
  await expect(pagina.getByText(`${pendientes} líneas pendientes`, { exact: true })).toBeVisible();
});

test("matriz: una columna por kit con el total del trabajo y la recomendada marcada", async () => {
  const vista = await stack.vistaAdmin(tokenAdmin, trabajoId);
  await pagina.goto(`${ADMIN}/trabajos/${trabajoId}`);
  for (const kit of vista.kits) {
    expect(await totalEnCabecera(kit.perfil)).toBe(kit.total);
    expect(kit.total).toBe(sumaDeSubtotales(kit));
    anotar({ [`total_${kit.perfil}`]: kit.total });
  }
  const recomendada = pagina.locator('[class*="matrizColReco"]');
  await expect(recomendada).toHaveCount(1);
  await expect(recomendada).toContainText(vista.recomendado.perfil);
  await expect(recomendada).toContainText("recomendado");
});

test("alternativa: elegir otra opcion cambia el producto solo en ese kit y recalcula su total", async () => {
  const antes = await stack.vistaAdmin(tokenAdmin, trabajoId);
  const perfil = antes.recomendado.perfil;
  // Un renglon resuelto con una alternativa de otro precio, para que el cambio se vea en el total.
  const candidatas = kitDe(antes, perfil).lineas.flatMap((linea) =>
    linea.estado_resolucion === "RESUELTO_AUTO" && linea.producto_elegido
      ? (linea.alternativas ?? [])
          .filter((alt) => alt.precio_cop != null && alt.precio_cop !== linea.producto_elegido.precio)
          .map((alternativa) => ({ linea, alternativa }))
      : [],
  );
  expect(candidatas.length, "ningun renglon tiene una alternativa de otro precio").toBeGreaterThan(0);
  const { linea, alternativa } = candidatas[0];
  anotar({
    perfil,
    renglon: linea.descripcion,
    sku_antes: linea.producto_elegido.sku,
    sku_despues: alternativa.sku,
  });

  await pagina.goto(`${ADMIN}/trabajos/${trabajoId}`);
  const detalle = await abrirCelda(antes, linea.descripcion, perfil);
  // Toda la tarjeta es la opcion: el radio va oculto y se elige pulsando la tarjeta.
  const tarjeta = detalle.locator("label").filter({ has: pagina.getByText(alternativa.sku, { exact: true }) });
  await tarjeta.click();
  await expect(tarjeta.getByRole("radio")).toBeChecked();
  await detalle.getByRole("button", { name: `Usar este producto en ${perfil}` }).click();
  await expect(detalle.getByText("Producto cambiado en este kit.")).toBeVisible();

  const despues = await stack.vistaAdmin(tokenAdmin, trabajoId);
  const cambiada = lineaDe(despues, perfil, linea.item_id);
  expect(cambiada.producto_elegido.sku).toBe(alternativa.sku);
  const kit = kitDe(despues, perfil);
  expect(kit.total).toBe(sumaDeSubtotales(kit));
  const totalAntes = kitDe(antes, perfil).total;
  expect(kit.total).toBe(totalAntes - (linea.subtotal_linea ?? 0) + (cambiada.subtotal_linea ?? 0));
  anotar({ total_antes: totalAntes, total_despues: kit.total });
  // Los otros dos kits no se tocan: el cambio de producto es por nivel.
  for (const otro of antes.kits.filter((k) => k.perfil !== perfil)) {
    expect(kitDe(despues, otro.perfil).total).toBe(otro.total);
    expect(lineaDe(despues, otro.perfil, linea.item_id).producto_elegido?.sku).toBe(
      lineaDe(antes, otro.perfil, linea.item_id).producto_elegido?.sku,
    );
  }
  // La pantalla se refresca con el total nuevo.
  await expect.poll(() => totalEnCabecera(perfil)).toBe(kit.total);
});

test("sin coincidencia: la consola exige el motivo y confirma la marca del renglon que nadie entendio", async () => {
  const antes = await stack.vistaAdmin(tokenAdmin, trabajoId);
  const perfil = antes.recomendado.perfil;
  const linea = kitDe(antes, perfil).lineas.find((l) => l.descripcion === stack.RENGLON_DESCONOCIDO);
  expect(linea.estado_resolucion).toBe("SIN_MATCH");
  expect(antes.lineas_pendientes).toContain(linea.item_id);

  // Sin producto en ningun kit, el renglon no tiene celdas: se resuelve desde el panel de avisos.
  expect(antes.kits.every((kit) => !lineaDe(antes, kit.perfil, linea.item_id).producto_elegido)).toBe(true);

  await pagina.goto(`${ADMIN}/trabajos/${trabajoId}`);
  const detalle = await abrirAviso(linea.descripcion);
  expect(await estadoEnPantalla(detalle)).toEqual(["SIN_MATCH"]);
  await detalle.getByRole("button", { name: "Sin coincidencia" }).click();
  // Sin motivo no se marca: la consola lo pide antes de llamar al backend.
  const marcar = pagina.waitForResponse(
    (r) => r.url().endsWith(`/lineas/${linea.item_id}/sin-coincidencia`) && r.request().method() === "POST",
    { timeout: 2_000 },
  );
  await detalle.getByRole("button", { name: "Marcar sin coincidencia" }).click();
  await expect(
    detalle.getByText("Escribe el motivo: una marca sin motivo no se puede revisar después."),
  ).toBeVisible();
  await expect(marcar).rejects.toThrow();

  await detalle
    .getByLabel("Motivo de la marca sin coincidencia (obligatorio)")
    .fill("El catalogo ficticio de QA no trae chaquiras ni un equivalente.");
  const marcada = pagina.waitForResponse(
    (r) => r.url().endsWith(`/lineas/${linea.item_id}/sin-coincidencia`) && r.request().method() === "POST",
  );
  await detalle.getByRole("button", { name: "Marcar sin coincidencia" }).click();
  expect((await marcada).ok()).toBe(true);
  await expect(detalle.getByText("Línea marcada sin coincidencia.")).toBeVisible();

  // "Te entendi y no lo tengo" sigue siendo un hueco: el renglon no sale de los pendientes.
  const despues = await stack.vistaAdmin(tokenAdmin, trabajoId);
  expect(despues.lineas_pendientes).toContain(linea.item_id);
  anotar({
    pendientes_antes: antes.lineas_pendientes.length,
    pendientes_despues: despues.lineas_pendientes.length,
  });
});

test("sin coincidencia: la marca se ve en la linea de los tres kits", async () => {
  // H-A-47 se corrigio en 390966b (`trabajos.decidir_linea` copia el estado a las LINEA del item en
  // todos los kits): queda como prueba de no regresion.
  anotar({ hallazgo: "H-A-47" });
  const antes = await stack.vistaAdmin(tokenAdmin, trabajoId);
  const perfil = antes.recomendado.perfil;
  const linea = kitDe(antes, perfil).lineas.find((l) => l.descripcion === stack.RENGLON_DESCONOCIDO);
  // La misma marca que hace la consola, por el gateway: esta prueba mira lo que se ve despues.
  const ruta = `/v1/admin/trabajos/${trabajoId}/lineas/${linea.item_id}/sin-coincidencia`;
  await stack.exigir(200, "POST", ruta, {
    token: tokenAdmin,
    cuerpo: { motivo: "El catalogo ficticio de QA no trae chaquiras ni un equivalente." },
  });

  await pagina.goto(`${ADMIN}/trabajos/${trabajoId}`);
  const detalle = await abrirAviso(linea.descripcion);
  const enPantalla = await estadoEnPantalla(detalle);
  const despues = await stack.vistaAdmin(tokenAdmin, trabajoId);
  const enLosKits = despues.kits.map((kit) => lineaDe(despues, kit.perfil, linea.item_id).estado_resolucion);
  anotar({ estado_en_pantalla: enPantalla.join(","), estado_en_los_kits: enLosKits.join(",") });

  // "Te entendi y no lo tengo" (HUECO_CATALOGO), no "no te entendi" (SIN_MATCH), y en los tres kits:
  // el estado de resolucion es del renglon, no del kit.
  expect(enLosKits).toEqual(despues.kits.map(() => "HUECO_CATALOGO"));
  expect(enPantalla).toEqual(["HUECO_CATALOGO"]);
});

test("confianza: cada producto trae la confianza del emparejamiento y la consola la muestra", async () => {
  test.fail(
    XFAIL,
    "H-A-46: la API no manda `confianza` (ni `ofertas`) en los productos del kit; el cliente pone 1 y la consola muestra 100 % en todos",
  );
  anotar({ hallazgo: "H-A-46" });
  const vista = await stack.vistaAdmin(tokenAdmin, trabajoId);
  const perfil = vista.recomendado.perfil;
  const linea = kitDe(vista, perfil).lineas.find((l) => l.producto_elegido && l.alternativas?.length);
  const productos = vista.kits.flatMap((kit) =>
    kit.lineas.flatMap((l) => [l.producto_elegido, ...(l.alternativas ?? [])].filter(Boolean)),
  );

  await pagina.goto(`${ADMIN}/trabajos/${trabajoId}`);
  const detalle = await abrirCelda(vista, linea.descripcion, perfil);
  const insignias = await detalle.getByTitle("Confianza del emparejamiento").allTextContents();
  anotar({
    productos: productos.length,
    productos_con_confianza: productos.filter((p) => typeof p.confianza === "number").length,
    insignias_en_pantalla: [...new Set(insignias)].join(" | "),
  });

  // CONTRATO_API.md: `producto_elegido` y cada alternativa llevan `confianza` (0..1) y sus `ofertas`.
  for (const producto of productos) {
    expect(typeof producto.confianza, `confianza de ${producto.sku}`).toBe("number");
    expect(Array.isArray(producto.ofertas), `ofertas de ${producto.sku}`).toBe(true);
  }
  const esperadas = [linea.producto_elegido, ...linea.alternativas].map(
    (p) => `confianza ${Math.round(p.confianza * 100)} %`,
  );
  expect(insignias).toEqual(esperadas);
});

test("publicar: aprobar el trabajo lo publica al acudiente", async () => {
  // H-A-01 se corrigio en c57c0b3 (migracion de `kit_canonico`): queda como prueba de no regresion.
  anotar({ hallazgo: "H-A-01" });
  await pagina.goto(`${ADMIN}/trabajos/${trabajoId}`);
  const decision = pagina.getByRole("region", { name: "Decisión de revisión" });
  await decision.getByRole("button", { name: "Aprobar y publicar" }).click();
  const revision = pagina.waitForResponse(
    (r) => r.url().endsWith(`/api/trabajos/${trabajoId}/revision`) && r.request().method() === "POST",
  );
  await decision.getByRole("button", { name: "Sí, publicar y avisar" }).click();
  const respuesta = await revision;
  anotar({ codigo_revision: respuesta.status(), cuerpo_revision: (await respuesta.text()).slice(0, 200) });

  expect(respuesta.ok()).toBe(true);
  await expect(decision.getByText(/Este trabajo ya se publicó/)).toBeVisible();
  expect((await stack.vistaAdmin(tokenAdmin, trabajoId)).estado).toBe("publicado");
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
