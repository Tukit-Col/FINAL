import { redirect } from "next/navigation";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { sesionActual } from "@/lib/sesion";
import VistaKits from "./VistaKits";
import AsistenteKitSlot from "./AsistenteKitSlot";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Tus tres kits — Tukit",
};

export default async function PaginaKits({
  params,
}: {
  params: Promise<{ trabajo_id: string }>;
}) {
  const { trabajo_id } = await params;
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
  const sesion = await sesionActual();

  return (
    <>
      <AsistenteKitSlot />
      <VistaKits trabajo={trabajo} correo={sesion?.correo ?? ""} />
    </>
  );
}
