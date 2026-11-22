import { CreditCard, Landmark, Smartphone } from "lucide-react";

export const MEDIOS_PAGO = {
  tarjeta: { nombre: "Tarjeta", Icono: CreditCard },
  pse: { nombre: "PSE", Icono: Landmark },
  nequi: { nombre: "Nequi", Icono: Smartphone },
} as const;
