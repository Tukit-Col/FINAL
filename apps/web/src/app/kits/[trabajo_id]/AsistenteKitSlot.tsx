// Punto de montaje del asistente en /kits: un chat flotante sobre el kit que
// el acudiente esta mirando. Siempre se ve el boton "Pregúntale a Tukit"; solo se oculta con
// NEXT_PUBLIC_TUKIT_ASISTENTE=0. Si el servidor tiene el asistente apagado
// (TUKIT_ASISTENTE sin 1), el chat lo dice en vez de desaparecer.
import PanelKit from "@/components/asistente/PanelKit";

export default function AsistenteKitSlot({ trabajoId, perfil }: { trabajoId: string; perfil: string }) {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE === "0") return null;
  return <PanelKit key={perfil} trabajoId={trabajoId} perfil={perfil} />;
}
