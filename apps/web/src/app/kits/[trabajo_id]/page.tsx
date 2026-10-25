import { redirect } from "next/navigation";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { matriculasDeLaSesion, sesionActual } from "@/lib/sesion";
import VistaKits from "./VistaKits";

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
  // Las matriculas del portador ponen el apodo de su hijo en cada renglon, en
  // vez de la referencia interna del trabajo. Sin sesion (o si identidad no
  // responde) llegan vacias y el renglon va sin pastilla.
  const [sesion, matriculas] = await Promise.all([sesionActual(), matriculasDeLaSesion()]);

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
    />
  );
}
