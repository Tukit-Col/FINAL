import { test } from "node:test";
import assert from "node:assert/strict";
import {
  agruparPorColegio, filtrarVersiones, hrefCola, leerFiltrosCola, paginar,
} from "../src/lib/cola.ts";

const mk = (id: string, col: string, grado: string, contacto = false, anio = 2026) => ({
  version_id: id, colegio_id: col, grado, anio_lectivo: anio, items: 10, tiene_contacto: contacto,
});
const V = [mk("a", "c1", "Segundo"), mk("b", "c1", "Primero", true), mk("c", "c2", "Primero"), mk("d", "c3", "Primero", false, 2025)];
const nombres: Record<string, string> = { c1: "Gimnasio Bogotá", c2: "Colegio Ficticio QA", c3: "Anglo" };
const nombreDe = (v: { colegio_id: string }) => nombres[v.colegio_id]!;
const orden = (a: string, b: string) => ["Primero", "Segundo"].indexOf(a) - ["Primero", "Segundo"].indexOf(b);

test("leerFiltrosCola valida y descarta basura", () => {
  const f = leerFiltrosCola({ q: " x ", anio: "abc", origen: "raro", pagina: "-3" });
  assert.deepEqual(f, { q: "x", grado: "", anio: null, origen: "todos", pagina: 1 });
  assert.equal(leerFiltrosCola({ anio: "2026", origen: "acudiente" }).anio, 2026);
});

test("filtra por texto sin tildes, origen, grado y anio", () => {
  const base = leerFiltrosCola({});
  assert.equal(filtrarVersiones(V, { ...base, q: "bogota" }, nombreDe).length, 2);
  assert.equal(filtrarVersiones(V, { ...base, origen: "acudiente" }, nombreDe).length, 1);
  assert.equal(filtrarVersiones(V, { ...base, origen: "colegio" }, nombreDe).length, 3);
  assert.equal(filtrarVersiones(V, { ...base, grado: "Primero", anio: 2025 }, nombreDe).length, 1);
});

test("agrupa: acudiente primero, grados en orden pedagogico", () => {
  const g = agruparPorColegio(V, nombreDe, orden);
  assert.deepEqual(g.map((x) => x.colegio_id), ["c1", "c3", "c2"]);
  assert.deepEqual(g[0]!.versiones.map((v) => v.version_id), ["b", "a"]);
  assert.equal(g[0]!.esperando, 1);
});

test("paginar acota la pagina", () => {
  const r = paginar(Array.from({ length: 60 }, (_, i) => i), 99, 25);
  assert.equal(r.pagina, 3);
  assert.equal(r.items.length, 10);
  assert.equal(paginar([], 1).paginas, 1);
});

test("hrefCola omite valores por defecto", () => {
  assert.equal(hrefCola(leerFiltrosCola({})), "/cola");
  assert.equal(hrefCola(leerFiltrosCola({ q: "a b", origen: "colegio" }), 2), "/cola?q=a+b&origen=colegio&pagina=2");
});
