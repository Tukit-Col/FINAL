// Punto de montaje del asistente conversacional en /empezar.
// No renderiza nada salvo que NEXT_PUBLIC_TUKIT_ASISTENTE=1.
import PanelEmpezar from "@/components/asistente/PanelEmpezar";

export default function AsistenteSlot() {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE !== "1") return null;
  return <PanelEmpezar />;
}
