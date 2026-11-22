import { test } from "node:test";
import assert from "node:assert/strict";
import type { OrigenDatos } from "../src/origen.ts";
import {
  FRASE_CONFIRMACION_SUPRESION,
  confirmacionDeSupresionValida,
  nombreArchivoMisDatos,
  totalDeSeccion,
  type ResultadoSupresion,
} from "../src/privacidad.ts";

test("la frase vale sin mayusculas, tildes ni espacios de mas", () => {
  assert.equal(confirmacionDeSupresionValida(FRASE_CONFIRMACION_SUPRESION), true);
  assert.equal(confirmacionDeSupresionValida("  eliminar   mis datos "), true);
  assert.equal(confirmacionDeSupresionValida("Eliminár mis datos"), true);
  assert.equal(confirmacionDeSupresionValida("eliminar"), false);
  assert.equal(confirmacionDeSupresionValida(""), false);
  assert.equal(confirmacionDeSupresionValida(undefined), false);
});

test("el archivo exportado lleva la fecha UTC", () => {
  assert.equal(
    nombreArchivoMisDatos(new Date("2026-11-01T23:30:00-05:00")),
    "tukit-mis-datos-2026-11-02.json",
  );
});

test("una seccion caida no se cuenta como cero", () => {
  assert.equal(totalDeSeccion({ disponible: false }), null);
  assert.equal(totalDeSeccion({ disponible: true, total: 0, elementos: [] }), 0);
});

const origen: Pick<OrigenDatos, "suprimirMisDatos"> = {
  async suprimirMisDatos(_token: string, confirmacion: string): Promise<ResultadoSupresion> {
    if (!confirmacionDeSupresionValida(confirmacion)) throw new Error("confirmacion_requerida");
    return {
      solicitud_id: "s-1",
      estado: "propagando",
      suprimido: [{ dato: "nombre", detalle: "Tu nombre." }],
      conservado: [{ dato: "pedidos_y_facturas", detalle: "x", fundamento: "Estatuto Tributario" }],
      pedidos_conservados: 2,
      mensaje: "ok",
    };
  },
};

test("suprimirMisDatos devuelve lo conservado con su fundamento", async () => {
  const r = await origen.suprimirMisDatos("tok", "eliminar mis datos");
  assert.equal(r.estado, "propagando");
  assert.match(r.conservado[0].fundamento, /Estatuto Tributario/);
  await assert.rejects(origen.suprimirMisDatos("tok", "no"));
});
