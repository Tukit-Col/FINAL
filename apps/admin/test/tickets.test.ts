// Bandeja de tickets: filtros nuevos, paginación, SLA, asignación.
// Correr:  node --test test/tickets.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { Caso } from "@tukit/contrato";
import {
  estaVencido,
  etiquetaSla,
  filtrarCasos,
  hayFiltrosTickets,
  hrefTickets,
  leerFiltrosTickets,
  paginar,
  puedeSoltar,
  textoAsignacion,
  textoVencimiento,
} from "../src/lib/tickets.ts";

const AHORA = new Date("2026-11-12T12:00:00Z").getTime();

function caso(extra: Partial<Caso>): Caso {
  return {
    caso_id: "11111111-0000-4000-8000-000000000000",
    origen: "acudiente",
    categoria: "reclamo",
    estado: "abierto",
    prioridad: "alta",
    asunto: "Llegó incompleto",
    abierto_en: "2026-11-01T00:00:00Z",
    vence_en: "2026-11-20T00:00:00Z",
    trabajo_id: null,
    pedido_id: null,
    asignado_a: null,
    ...extra,
  };
}

test("paginar: 45 items -> 3 páginas, la última con 5; fuera de rango se acota; vacío = 1", () => {
  const items = Array.from({ length: 45 }, (_, i) => i);
  assert.equal(paginar(items, 1).items.length, 20);
  const ultima = paginar(items, 3);
  assert.equal(ultima.items.length, 5);
  assert.equal(ultima.paginas, 3);
  assert.equal(paginar(items, 9).pagina, 3);
  assert.equal(paginar(items, 0).pagina, 1);
  const vacia = paginar([], 4);
  assert.deepEqual([vacia.paginas, vacia.pagina, vacia.items.length], [1, 1, 0]);
});

test("leerFiltrosTickets sanea página y los filtros nuevos", () => {
  assert.equal(leerFiltrosTickets({ pagina: "abc" }).pagina, 1);
  assert.equal(leerFiltrosTickets({ pagina: "-2" }).pagina, 1);
  assert.equal(leerFiltrosTickets({ pagina: "3" }).pagina, 3);
  const f = leerFiltrosTickets({ vencidos: "1", asignado: "ninguno", prioridad: "urgente" });
  assert.deepEqual([f.vencidos, f.asignado, f.prioridad], [true, "ninguno", "urgente"]);
  const raro = leerFiltrosTickets({ asignado: "x", prioridad: "critica" });
  assert.deepEqual([raro.asignado, raro.prioridad], ["", ""]);
  assert.equal(hayFiltrosTickets(leerFiltrosTickets({ pagina: "2" })), false);
});

test("filtrarCasos: vencidos solo activos; sin asignar; míos", () => {
  const vencido = caso({ caso_id: "a", vence_en: "2026-11-10T00:00:00Z" });
  const resueltoVencido = caso({ caso_id: "b", vence_en: "2026-11-10T00:00:00Z", estado: "resuelto" });
  const mio = caso({ caso_id: "c", asignado_a: "u1" });
  const todos = [vencido, resueltoVencido, mio];
  const base = leerFiltrosTickets({});
  assert.deepEqual(
    filtrarCasos(todos, { ...base, vencidos: true }, AHORA).map((c) => c.caso_id),
    ["a"],
  );
  assert.deepEqual(
    filtrarCasos(todos, { ...base, asignado: "ninguno" }, AHORA).map((c) => c.caso_id),
    ["a", "b"],
  );
  assert.deepEqual(
    filtrarCasos(todos, { ...base, asignado: "mios" }, AHORA, "u1").map((c) => c.caso_id),
    ["c"],
  );
  assert.equal(filtrarCasos(todos, { ...base, asignado: "mios" }, AHORA, null).length, 0);
});

test("etiquetaSla: sin vence_en no inventa fecha", () => {
  const sin = etiquetaSla(caso({ vence_en: null }), AHORA);
  assert.deepEqual(sin, { texto: "", tono: "sin" });
  assert.ok(!JSON.stringify(sin).includes("Invalid"));
  assert.equal(etiquetaSla(caso({ vence_en: "2026-11-10T00:00:00Z" }), AHORA).tono, "vencido");
  assert.equal(etiquetaSla(caso({ vence_en: "2026-11-12T20:00:00Z" }), AHORA).tono, "hoy");
  assert.equal(etiquetaSla(caso({ vence_en: "2026-11-20T00:00:00Z" }), AHORA).tono, "ok");
  assert.equal(etiquetaSla(caso({ vence_en: "basura" }), AHORA).tono, "sin");
  assert.equal(etiquetaSla(caso({ estado: "cerrado" }), AHORA).tono, "sin");
});

test("hrefTickets conserva los demás filtros", () => {
  const f = leerFiltrosTickets({ vencidos: "1", q: "x" });
  assert.equal(hrefTickets(f, { pagina: 2 }), "/tickets?q=x&vencidos=1&pagina=2");
  assert.equal(hrefTickets(f, { pagina: 1, vencidos: false, q: "" }), "/tickets");
});

test("la asignacion se dice desde quien mira, y solo el dueño o un supervisor la sueltan", () => {
  assert.equal(textoAsignacion(null, "u1"), "Sin asignar");
  assert.equal(textoAsignacion("u1", "u1"), "Asignado a ti");
  assert.equal(textoAsignacion("u2", "u1"), "Asignado a otra persona");
  assert.equal(puedeSoltar("u2", "u1", false), false);
  assert.equal(puedeSoltar("u2", "u1", true), true);
  assert.equal(puedeSoltar("u1", "u1", false), true);
  assert.equal(puedeSoltar(null, "u1", true), false);
});

test("leerFiltrosTickets ignora un estado desconocido y limpia el texto", () => {
  const f = leerFiltrosTickets({ estado: "volando", categoria: "pago", q: [" hola "] });
  assert.deepEqual(f, {
    estado: "",
    categoria: "pago",
    q: "hola",
    prioridad: "",
    asignado: "",
    vencidos: false,
    pagina: 1,
  });
  assert.equal(hayFiltrosTickets(f), true);
});

test("filtra por estado, categoria y texto (prefijo de id o asunto)", () => {
  const casos = [caso({}), caso({ caso_id: "22222222-0", estado: "resuelto", categoria: "pago", asunto: "Cobro doble" })];
  assert.equal(filtrarCasos(casos, { estado: "resuelto", categoria: "", q: "" }).length, 1);
  assert.equal(filtrarCasos(casos, { estado: "", categoria: "", q: "2222" }).length, 1);
  assert.equal(filtrarCasos(casos, { estado: "", categoria: "", q: "cobro" }).length, 1);
});

test("vencimiento: solo cuenta en tickets activos", () => {
  const ahora = new Date("2026-11-20T00:00:00Z").getTime();
  const vencidoEl14 = caso({ vence_en: "2026-11-14T00:00:00Z" });
  assert.equal(estaVencido(vencidoEl14, ahora), true);
  assert.equal(estaVencido(caso({ estado: "resuelto" }), ahora), false);
  assert.match(textoVencimiento(vencidoEl14, ahora) ?? "", /vencido hace 6 d/);
  assert.equal(textoVencimiento(caso({ estado: "cerrado" }), ahora), null);
});
