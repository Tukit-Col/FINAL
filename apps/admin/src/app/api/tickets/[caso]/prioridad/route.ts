import { origenDeDatos } from "@tukit/contrato/servidor";
import { validarPrioridad } from "@/lib/cuerpos-admin";
import { ejecutarPost } from "@/lib/ruta-admin";

export const dynamic = "force-dynamic";

export async function POST(
  peticion: Request,
  contexto: { params: Promise<{ caso: string }> },
): Promise<Response> {
  const { caso } = await contexto.params;
  return ejecutarPost(peticion, validarPrioridad, (token, valor) => origenDeDatos().cambiarPrioridadCaso(token, caso, valor));
}
