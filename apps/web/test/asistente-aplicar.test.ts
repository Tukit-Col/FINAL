// Lo que confirma el padre en /kits va a los endpoints de S3, nunca a otro lado.
// `npm test` en apps/web.

import { test } from "node:test";
import assert from "node:assert/strict";
import { aplicacionDePropuesta, type PropuestaAplicable } from "../src/components/asistente/aplicar.ts";

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
