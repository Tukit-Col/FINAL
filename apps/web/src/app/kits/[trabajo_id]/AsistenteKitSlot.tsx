// Punto de montaje del asistente en /kits: un chat flotante sobre el kit que
// el acudiente esta mirando. No renderiza nada salvo que NEXT_PUBLIC_TUKIT_ASISTENTE=1.
import PanelKit from "@/components/asistente/PanelKit";

export default function AsistenteKitSlot({ trabajoId, perfil }: { trabajoId: string; perfil: string }) {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE !== "1") return null;
  return <PanelKit key={perfil} trabajoId={trabajoId} perfil={perfil} />;
}
