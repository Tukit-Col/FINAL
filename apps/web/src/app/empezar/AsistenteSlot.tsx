import PanelEmpezar from "@/components/asistente/PanelEmpezar";

export default function AsistenteSlot() {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE !== "1") return null;
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE_EMPEZAR !== "1") return null;
  return <PanelEmpezar />;
}
