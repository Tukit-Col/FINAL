// La linea de tiempo del acudiente: Comercio la arma y el contrato solo le pone
// nombre a cada paso. La forma del JSON la prueba Comercio
// (`test_dominio_linea_de_tiempo.py` y `test_logistica.py`).
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/linea-de-tiempo.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { PasoPedido } from "../src/comercio.ts";
import { ETIQUETA_PASO_PEDIDO } from "../src/comercio.ts";

const PASOS: PasoPedido[] = ["creado", "pagado", "en_preparacion", "despachado", "en_reparto", "entregado"];

test("cada paso de la linea de tiempo tiene su nombre, en el orden de Comercio", () => {
  assert.deepEqual(Object.keys(ETIQUETA_PASO_PEDIDO), PASOS);
  assert.equal(ETIQUETA_PASO_PEDIDO.creado, "Pedido creado");
  assert.equal(ETIQUETA_PASO_PEDIDO.pagado, "Pago confirmado");
  assert.equal(ETIQUETA_PASO_PEDIDO.en_preparacion, "En preparación");
});
