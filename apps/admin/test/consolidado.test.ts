import { test } from "node:test";
import assert from "node:assert/strict";
import type { Pedido } from "@tukit/contrato";
import {
  agruparPorColegio,
  contarPorSalon,
  esEntregaPendiente,
  marcadoresDe,
  type EntregaPendiente,
} from "../src/lib/consolidado.ts";

function entrega(id: string, colegios: string[], punto: EntregaPendiente["punto"], hijos = 1): EntregaPendiente {
  return { pedido_id: id, estado: "pagado", destinatario: "X", direccion: "d", ciudad: "Bogotá", departamento: null, colegios, hijos, punto };
}

test("solo los pedidos pagados y sin entregar con envio son entregas pendientes", () => {
  const base = { pedido_id: "p", usuario_id: "u", trabajo_id: null, creado_en: "x", total: 1, hijos: 1, colegios: [], lineas: [], pago: null } as const;
  const envio = { destinatario: "a", direccion: "b", ciudad: "c" } as Pedido["envio"];
  assert.equal(esEntregaPendiente({ ...base, estado: "en_reparto", envio }), true);
  assert.equal(esEntregaPendiente({ ...base, estado: "entregado", envio }), false);
  assert.equal(esEntregaPendiente({ ...base, estado: "pendiente_pago", envio }), false);
  assert.equal(esEntregaPendiente({ ...base, estado: "pagado", envio: null }), false);
});

test("agrupa por colegio, cuenta con y sin marcador y ordena por volumen", () => {
  const p = { lat: 4.6, lon: -74.1 };
  const grupos = agruparPorColegio([
    entrega("1", ["Gimnasio"], p),
    entrega("2", ["San José"], null),
    entrega("3", ["San José"], "pendiente", 2),
    entrega("4", [], p),
  ]);
  assert.equal(grupos[0].colegio, "San José");
  assert.deepEqual([grupos[0].entregas.length, grupos[0].hijos, grupos[0].conMarcador, grupos[0].sinMarcador], [2, 3, 0, 2]);
  assert.ok(grupos.some((g) => g.colegio === "Sin colegio"));
});

test("pedidos al mismo sitio se apilan en un marcador; sin punto no hay marcador", () => {
  const p = { lat: 4.60971, lon: -74.08171 };
  const grupos = agruparPorColegio([entrega("1", ["A"], p), entrega("2", ["A"], { lat: 4.60972, lon: -74.08172 }), entrega("3", ["A"], null)]);
  const m = marcadoresDe(grupos);
  assert.equal(m.length, 1);
  assert.equal(m[0].entregas.length, 2);
});

test("cuenta hijos por colegio y salon con grados en orden natural", () => {
  const filas = contarPorSalon([
    { colegio_nombre: "A", grado: "10" },
    { colegio_nombre: "A", grado: "2" },
    { colegio_nombre: "A", grado: "2" },
  ]);
  assert.deepEqual(filas.map((f) => [f.grado, f.hijos]), [["2", 2], ["10", 1]]);
});
