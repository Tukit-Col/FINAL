import { sesionActual } from "@/lib/sesion";
import PantallaEspera from "./PantallaEspera";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Armando tu kit — Tukit",
};

export default async function Esperando({
  params,
}: {
  params: Promise<{ trabajo_id: string }>;
}) {
  const { trabajo_id } = await params;
  // Quien llega con sesion (desde "Mis solicitudes") vuelve a su panel; sin
  // sesion no hay panel al que volver y el pie lleva al inicio.
  const sesion = await sesionActual();
  return <PantallaEspera trabajoId={trabajo_id} conSesion={sesion !== null} />;
}
