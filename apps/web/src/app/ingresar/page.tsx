// Pantalla de ingreso.
//
// El servidor resuelve el origen para decir la verdad sobre que autenticacion
// esta viva: en `simulado` los usuarios son de prueba y no se verifica la
// clave; en `api` se autentica contra identidad a traves del gateway. Si ya
// hay sesion, no tiene sentido volver a pedir credenciales: se redirige al
// destino que corresponde.

import { redirect } from "next/navigation";
import {
  descripcionOrigen,
  destinoDe,
  urlAdmin,
} from "@tukit/contrato/servidor";
import { sesionActual } from "@/lib/sesion";
import FormularioIngreso from "./FormularioIngreso";

export const dynamic = "force-dynamic";
export const metadata = { title: "Ingresar — Tukit" };

export default async function Ingresar() {
  const sesion = await sesionActual();
  if (sesion) {
    const destino = destinoDe(sesion);
    redirect(destino.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino.ruta);
  }

  const origen = descripcionOrigen();
  return <FormularioIngreso modo={origen.nombre} />;
}
