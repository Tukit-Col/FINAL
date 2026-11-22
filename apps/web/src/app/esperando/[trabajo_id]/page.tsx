import { esLimiteDeTasa } from "@/lib/limite";
import { sesionActual, tokenDeSesion } from "@/lib/sesion";
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
  let conSesion: boolean;
  let correo: string | null = null;
  try {
    const sesion = await sesionActual();
    conSesion = sesion !== null;
    correo = sesion?.correo || null;
  } catch (causa) {
    if (!esLimiteDeTasa(causa)) throw causa;
    conSesion = Boolean(await tokenDeSesion());
  }
  return <PantallaEspera trabajoId={trabajo_id} conSesion={conSesion} correo={correo} />;
}
