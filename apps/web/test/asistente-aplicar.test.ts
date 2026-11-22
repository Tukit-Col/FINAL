import { test } from "node:test";
import assert from "node:assert/strict";
import { aplicacionDePropuesta, pendientesDelTurno, renglonesPorDecidir, type PropuestaAplicable } from "../src/components/asistente/aplicar.ts";

const tarjeta = (sku: string) => ({ sku, nombre: sku, marca: null, nivel: "economico", precio_cop: 1000, imagen_url: null });
const base = { trabajo_id: "t-1", perfil: "A tu Medida", item_id: "i/2", descripcion: "Colores", aplicable: true };

test("confirmar un descarte quita el renglon por el endpoint de descarte de S3", () => {
  const c = {
    tipo: "PropuestaDescarte",
    props: { ...base, motivo_texto: "Ya lo tienes", producto: tarjeta("CO-1"), ahorro_cop: 8000 },
  } as unknown as PropuestaAplicable;
  assert.deepEqual(aplicacionDePropuesta(c), {
    url: "/api/trabajos/t-1/kits/A%20tu%20Medida/lineas/i%2F2/descarte",
    metodo: "PUT",
    cuerpo: { descartado: true },
    tipo: "descarte",
  });
});

test("confirmar un cambio fija el sku propuesto por el endpoint de producto", () => {
  const c = {
    tipo: "PropuestaCambio",
    props: { ...base, antes: tarjeta("CU-1"), despues: tarjeta("CU-2"), unidades: 2, delta_cop: -8000 },
  } as unknown as PropuestaAplicable;
  const a = aplicacionDePropuesta(c);
  assert.equal(a?.url, "/api/trabajos/t-1/kits/A%20tu%20Medida/lineas/i%2F2/producto");
  assert.deepEqual(a?.cuerpo, { sku: "CU-2" });
  assert.equal(a?.tipo, "cambio");
});

test("lo que el servidor marco no aplicable no se aplica", () => {
  const c = {
    tipo: "PropuestaDescarte",
    props: { ...base, aplicable: false, motivo_texto: "x", producto: tarjeta("CO-1"), ahorro_cop: 0 },
  } as unknown as PropuestaAplicable;
  assert.equal(aplicacionDePropuesta(c), null);
});

test("Aceptar todos solo toma las propuestas aplicables que siguen pendientes", () => {
  const cambio = (aplicable: boolean) =>
    ({
      tipo: "PropuestaCambio",
      props: { ...base, antes: tarjeta("A"), despues: tarjeta("B"), unidades: 1, delta_cop: -1000, aplicable },
    }) as unknown as PropuestaAplicable;
  const comps = [{ tipo: "ResumenLote" }, cambio(true), cambio(true), cambio(false), cambio(true)] as never;
  const pend = pendientesDelTurno(comps, 2, { "2-2": "aplicada" });
  assert.deepEqual(pend.map((p) => p.clave), ["2-1", "2-4"]);
});

test("se iluminan los renglones de las propuestas sin decidir, en orden y sin repetir", () => {
  const cambio = (item: string) =>
    ({
      tipo: "PropuestaCambio",
      props: { ...base, item_id: item, antes: tarjeta("A"), despues: tarjeta("B"), unidades: 1, delta_cop: -100 },
    }) as unknown as PropuestaAplicable;
  const resumen = { tipo: "ResumenLote", props: {} } as never;
  const turnos = [[resumen, cambio("c1"), cambio("c2")], null, [cambio("c2"), cambio("c3")]];
  assert.deepEqual(renglonesPorDecidir(turnos, {}), ["c1", "c2", "c3"]);
  assert.deepEqual(renglonesPorDecidir(turnos, { "0-1": "aplicada", "2-1": "rechazada" }), ["c2"]);
});
