// `POST /api/logistica/lote` — el operador mueve varios pedidos al mismo destino simple.
// Comercio responde por pedido (`avanzados` y `fallidos`); aqui solo se valida la forma.

import { origenDeDatos } from "@tukit/contrato/servidor";
import { validarLote } from "@/lib/cuerpos-admin";
import { ejecutarPost } from "@/lib/ruta-admin";

export const dynamic = "force-dynamic";

export async function POST(peticion: Request): Promise<Response> {
  return ejecutarPost(peticion, validarLote, (token, cuerpo) => origenDeDatos().avanzarLote(token, cuerpo));
}
