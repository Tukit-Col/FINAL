// Correr:  node --test test/panel-vivo.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import type { VersionListaAdmin, ResumenComercio } from "@tukit/contrato";
import { actividadReciente, flujoDePedidos, listasPorColegio } from "../src/lib/panel-vivo.ts";
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
