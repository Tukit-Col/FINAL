// Filtros y paginas del padron de /clientes.
// Correr:  node --test test/clientes.test.ts

import { test } from "node:test";
import assert from "node:assert/strict";
import type { AcudienteAdmin } from "@tukit/contrato";
import {
  filtrarClientes,
  hrefClientes,
  leerFiltrosClientes,
  opcionesClientes,
  paginar,
} from "../src/lib/clientes.ts";

const hijo = (colegio_id: string, grado = "3") => ({ colegio_id, colegio_nombre: `Col ${colegio_id}`, grado });
const fam = (n: number, extra: Partial<AcudienteAdmin> = {}): AcudienteAdmin => ({
  usuario_id: `u${n}`,
  correo: `fam${n}@mail.co`,
  celular: null,
  creado_en: `2026-10-${String(n).padStart(2, "0")}T12:00:00Z`,
  hijos: [],
  ...extra,
});

const datos = [
  fam(1, { hijos: [hijo("a")] }),
  fam(2, { correo: "qa-carga-2@example.test", hijos: [hijo("a", "5"), hijo("b")] }),
  fam(3, { hijos: [hijo("b"), hijo("b"), hijo("c")] }),
  fam(4),
];

test("leerFiltrosClientes sanea valores raros", () => {
  const f = leerFiltrosClientes({ hijos: "9", pagina: "-3", orden: "x", sinprueba: "1" });
  assert.deepEqual(f, { q: "", colegio: "", grado: "", hijos: "", orden: "nuevo", sinPrueba: true, pagina: 1 });
});

test("filtra por correo, colegio, grado, nº de hijos y cuentas de prueba", () => {
  const f = (p: Record<string, string>) => filtrarClientes(datos, leerFiltrosClientes(p)).map((a) => a.usuario_id);
  assert.deepEqual(f({}), ["u4", "u3", "u2", "u1"]);
  assert.deepEqual(f({ orden: "antiguo" }), ["u1", "u2", "u3", "u4"]);
  assert.deepEqual(f({ q: "QA-CARGA" }), ["u2"]);
  assert.deepEqual(f({ colegio: "b" }), ["u3", "u2"]);
  assert.deepEqual(f({ grado: "5" }), ["u2"]);
  assert.deepEqual(f({ hijos: "0" }), ["u4"]);
  assert.deepEqual(f({ hijos: "3+" }), ["u3"]);
  assert.deepEqual(f({ sinprueba: "1" }), ["u4", "u3", "u1"]);
});

test("opcionesClientes junta colegios y grados sin repetir", () => {
  const o = opcionesClientes(datos);
  assert.deepEqual(o.colegios.map((c) => c.id), ["a", "b", "c"]);
  assert.deepEqual(o.grados, ["3", "5"]);
});

test("paginar: 130 en paginas de 25 y pagina fuera de rango", () => {
  const todos = Array.from({ length: 130 }, (_, i) => i);
  const ultima = paginar(todos, 99);
  assert.equal(ultima.paginas, 6);
  assert.equal(ultima.pagina, 6);
  assert.deepEqual([ultima.desde, ultima.hasta], [126, 130]);
  assert.deepEqual(paginar([], 1), { items: [], pagina: 1, paginas: 1, total: 0, desde: 0, hasta: 0 });
});

test("hrefClientes conserva filtros y omite lo que es por defecto", () => {
  const f = leerFiltrosClientes({ q: "a@b", sinprueba: "1" });
  assert.equal(hrefClientes(f, { pagina: 2 }), "/clientes?q=a%40b&sinprueba=1&pagina=2");
  assert.equal(hrefClientes(leerFiltrosClientes({})), "/clientes");
});
