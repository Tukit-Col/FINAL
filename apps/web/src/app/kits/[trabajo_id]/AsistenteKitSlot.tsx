// Punto de montaje del panel del asistente en /kits.
// No renderiza nada salvo que NEXT_PUBLIC_TUKIT_ASISTENTE=1.
import PanelKit from "@/components/asistente/PanelKit";

export default function AsistenteKitSlot({ trabajoId }: { trabajoId: string }) {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE !== "1") return null;
  return <PanelKit trabajoId={trabajoId} />;
}
