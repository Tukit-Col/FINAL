import { test } from "node:test";
import assert from "node:assert/strict";
import type { VersionListaAdmin, ResumenComercio } from "@tukit/contrato";
import {
  actividadReciente,
  agruparPorDia,
  flujoDePedidos,
  listasPorColegio,
  pedidosPorDia,
  tituloDia,
  TONO_PEDIDO,
} from "../src/lib/panel-vivo.ts";
import { proporcion } from "../src/lib/graficos.ts";
import { construirPanel } from "../src/lib/panel-accionable.ts";

const v = (colegio_id: string, items = 2, extra = {}): VersionListaAdmin =>
  ({ colegio_id, items, revisada: false, colegio_nombre: null, ...extra }) as VersionListaAdmin;

test("listas por colegio: agrupa, ordena y topa", () => {
  const r = listasPorColegio(
    [v("a"), v("b"), v("b"), v("c"), v("d"), v("e"), v("f"), v("a", 1, { revisada: true })],
    new Map([["b", "Colegio B"]]),
  );
  assert.equal(r.grupos[0].nombre, "Colegio B");
  assert.equal(r.grupos.length, 5);
  assert.equal(r.total, 7);
  assert.equal(r.colegios, 6);
});

test("flujo: cada etapa enlaza a su estado", () => {
  const f = flujoDePedidos({ por_estado: { pagado: 3 } } as unknown as ResumenComercio);
  assert.equal(f.etapas[1].cantidad, 3);
  assert.equal(f.etapas[1].enlace, "/logistica?estado=pagado");
  assert.equal(f.etapas[0].cantidad, 0);
});

test("actividad: mezcla, ordena y recorta a n; no muestra asunto", () => {
  const casos = [{ caso_id: "c1xxxxxxxx", categoria: "pago", prioridad: "alta", abierto_en: "2026-11-02T10:00:00Z", asunto: "Mi hija Sofía" }];
  const pedidos = [{ pedido_id: "p1xxxxxxxx", estado: "pagado", total: 100, creado_en: "2026-11-03T10:00:00Z" }];
  const a = actividadReciente({
    pedidos, casos, cola: null,
    etiquetaPedido: (e) => e, etiquetaCategoria: (c) => c, etiquetaPrioridad: (p) => p,
    dinero: String, nombreColegio: () => "",
  } as never, 1);
  assert.equal(a.length, 1);
  assert.equal(a[0].tipo, "pedido");
  assert.ok(!JSON.stringify(a).includes("Sofía"));
});

test("panel: los widgets en cero quedan en enCero", () => {
  const r = construirPanel({ pedidos: null, casos: { abiertos: 0, urgentes: 0, vencen_hoy: 0, resueltos_semana: 0, sin_asignar: 0, vencidos: 2 }, cola: null });
  assert.equal(r.widgets.length, 1);
  assert.equal(r.enCero.length, 1);
});

test("listas: acudiente esperando primero, 'otros N' y conteo por grado", () => {
  const r = listasPorColegio(
    [
      v("a", 2, { grado: "Primero" }),
      v("b", 2, { grado: "Primero" }),
      v("b", 2, { grado: "Once" }),
      v("c", 2, { grado: "Transicion", tiene_contacto: true }),
      v("d", 2, { grado: "Primero" }),
      v("e", 2, { grado: "Rarito" }),
      v("f", 2, { grado: "Primero" }),
      v("g", 2, { grado: "Primero" }),
    ],
    new Map(),
    3,
    ["Transicion", "Primero", "Once"],
  );
  assert.equal(r.grupos[0].clave, "c");
  assert.equal(r.grupos[0].esperando, 1);
  assert.equal(r.grupos[1].clave, "b");
  assert.equal(r.esperando, 1);
  assert.deepEqual(r.otros, { colegios: 4, listas: 4 });
  assert.equal(r.total, 8);
  assert.deepEqual(r.porGrado.map((g) => g.grado), ["Transicion", "Primero", "Once", "Rarito"]);
  assert.equal(r.porGrado[1].listas, 5);
  assert.equal(r.uniforme, false);
});

test("listas: sin resto no hay 'otros'; barras iguales marcan uniforme", () => {
  const r = listasPorColegio([v("a"), v("b")], new Map());
  assert.equal(r.otros, null);
  assert.equal(r.uniforme, true);
});

test("proporcion: piso para positivos, 0 para cero y tope en 100", () => {
  assert.equal(proporcion(0, 10), 0);
  assert.equal(proporcion(1, 1000), 4);
  assert.equal(proporcion(5, 10), 50);
  assert.equal(proporcion(20, 10), 100);
  assert.equal(proporcion(3, 0), 100);
});

const ahora = Date.parse("2026-11-12T15:00:00Z");

test("agruparPorDia: Hoy / Ayer / Hace N días en hora de Bogota", () => {
  const a = (clave: string, instante: string) => ({ clave, instante }) as never;
  const g = agruparPorDia(
    [
      a("1", "2026-11-12T14:00:00Z"),
      a("2", "2026-11-12T06:00:00Z"),
      a("3", "2026-11-12T03:00:00Z"),
      a("4", "2026-11-05T15:00:00Z"),
      a("5", "2026-10-01T15:00:00Z"),
      a("6", "basura"),
    ],
    ahora,
  );
  assert.deepEqual(g.map((d) => d.titulo).slice(0, 2), ["Hoy", "Ayer"]);
  assert.equal(g[0].items.length, 2);
  assert.equal(g[1].items.length, 1);
  assert.equal(tituloDia("2026-11-06", "2026-11-12"), "Hace 6 días");
  assert.equal(g[2].titulo, "Hace 7 días");
  assert.match(g[3].titulo, /octubre/);
  assert.equal(g[4].titulo, "Sin fecha");
});

test("pedidosPorDia: 7 columnas, hoy al final, cuenta por dia de Bogota", () => {
  const c = pedidosPorDia(
    [
      { creado_en: "2026-11-12T14:00:00Z" },
      { creado_en: "2026-11-12T03:00:00Z" },
      { creado_en: "2026-11-06T15:00:00Z" },
      { creado_en: "2026-11-01T15:00:00Z" },
    ],
    ahora,
  );
  assert.equal(c.length, 7);
  assert.equal(c[6].etiqueta, "Hoy");
  assert.equal(c[6].valor, 1);
  assert.equal(c[5].valor, 1);
  assert.equal(c[0].clave, "2026-11-06");
  assert.equal(c[0].valor, 1);
  assert.equal(c.reduce((t, x) => t + x.valor, 0), 3);
});

test("actividad: tono por estado y monto aparte", () => {
  const [p, t] = actividadReciente({
    pedidos: [{ pedido_id: "p1xxxxxxxx", estado: "incidencia", total: 100, creado_en: "2026-11-03T10:00:00Z" }],
    casos: [{ caso_id: "c1xxxxxxxx", categoria: "pago", prioridad: "urgente", abierto_en: "2026-11-02T10:00:00Z" }],
    cola: null,
    etiquetaPedido: (e: string) => e, etiquetaCategoria: (x: string) => x, etiquetaPrioridad: (x: string) => x,
    dinero: (n: number) => `$ ${n}`, nombreColegio: () => "",
  } as never);
  assert.equal(p.tono, "peligro");
  assert.equal(p.monto, "$ 100");
  assert.equal(t.tono, "peligro");
  assert.equal(t.nota, "pago");
  assert.equal(TONO_PEDIDO.pagado, "exito");
});
