// Punto de montaje del asistente conversacional en /empezar.
//
// Va apagado por omisión aunque el asistente esté activo: en la ronda 2 de
// OE5 el equipo prefirió que el acudiente arranque con el formulario guiado y
// que el chat quede solo en la página del kit, para pedir cambios sobre algo
// que ya ve. Se enciende aparte con NEXT_PUBLIC_TUKIT_ASISTENTE_EMPEZAR=1.
import PanelEmpezar from "@/components/asistente/PanelEmpezar";

export default function AsistenteSlot() {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE !== "1") return null;
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE_EMPEZAR !== "1") return null;
  return <PanelEmpezar />;
}
