import PanelKit from "@/components/asistente/PanelKit";

export default function AsistenteKitSlot({ trabajoId, perfil }: { trabajoId: string; perfil: string }) {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE === "0") return null;
  return <PanelKit key={perfil} trabajoId={trabajoId} perfil={perfil} />;
}
