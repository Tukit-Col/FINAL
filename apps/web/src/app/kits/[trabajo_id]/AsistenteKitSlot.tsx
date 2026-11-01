// Punto de montaje del panel del asistente en /kits.
// No renderiza nada salvo que NEXT_PUBLIC_TUKIT_ASISTENTE=1.
export default function AsistenteKitSlot() {
  if (process.env.NEXT_PUBLIC_TUKIT_ASISTENTE !== "1") return null;
  return null;
}
