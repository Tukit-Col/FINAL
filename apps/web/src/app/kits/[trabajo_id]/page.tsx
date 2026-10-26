import { redirect } from "next/navigation";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import { entregaParaReintento, type EntregaPrevia } from "@/lib/pagar-pedido";
import { matriculasDeLaSesion, pedidosDeLaSesion, sesionActual } from "@/lib/sesion";
import VistaKits from "./VistaKits";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Tus tres kits — Tukit",
};

// La entrega del pedido que quedo pendiente de este kit (pago rechazado o
// pasarela cerrada), para que el reintento no pida otra vez la direccion. Es
// un adorno: sin sesion o si comercio no responde, el formulario va vacio.
async function entregaPrevia(trabajoId: string): Promise<EntregaPrevia | null> {
  try {
    return entregaParaReintento(await pedidosDeLaSesion(), trabajoId, Date.now());
  } catch {
    return null;
  }
}

export default async function PaginaKits({
  params,
  searchParams,
}: {
  params: Promise<{ trabajo_id: string }>;
  searchParams: Promise<{ pagar?: string }>;
}) {
  const { trabajo_id } = await params;
  return conAvisoDeLimite(() => kits(trabajo_id, searchParams));
}

async function kits(trabajo_id: string, searchParams: Promise<{ pagar?: string }>) {
  const trabajo = await origenDeDatos().consultarTrabajo(trabajo_id);

  // Mientras no este publicado, `kits` viene vacio y no hay nada que pintar:
  // el acudiente nunca ve un kit sin revisar. La pantalla de espera es la que
  // sabe contar esa historia.
  if (trabajo.estado !== "publicado") {
    redirect(`/esperando/${trabajo_id}`);
  }

  // El correo de la sesion prellena el comprobante del pago: al acudiente ya
  // identificado no se le vuelve a pedir. Anonimo (sin cookie) => "" y el campo
  // queda editable, como estaba.
  // Las matriculas del portador ponen el apodo de su hijo en cada renglon, en
  // vez de la referencia interna del trabajo. Sin sesion (o si identidad no
  // responde) llegan vacias y el renglon va sin pastilla.
  const [sesion, matriculas, entrega, consulta] = await Promise.all([
    sesionActual(),
    matriculasDeLaSesion(),
    entregaPrevia(trabajo_id),
    searchParams,
  ]);

  // La llave de Google Places es de servidor (sin `NEXT_PUBLIC_`) y llega por
  // props. Vacia o solo espacios => sin llave: el checkout pide la direccion a
  // mano (ADR 0044).
  const llaveMaps = process.env.GOOGLE_MAPS_API_KEY?.trim() || null;

  return (
    <VistaKits
      trabajo={trabajo}
      correo={sesion?.correo ?? ""}
      llaveMaps={llaveMaps}
      matriculas={matriculas.map(({ colegio_id, grado, apodo }) => ({ colegio_id, grado, apodo }))}
      entregaPrevia={entrega}
      // "Intentar de nuevo" (pago rechazado) llega con `?pagar=1`: el
      // formulario de entrega ya abierto y lleno.
      abrirPago={consulta.pagar === "1"}
    />
  );
}
