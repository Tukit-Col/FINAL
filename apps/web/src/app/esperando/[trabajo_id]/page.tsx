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
  return <PantallaEspera trabajoId={trabajo_id} />;
}
