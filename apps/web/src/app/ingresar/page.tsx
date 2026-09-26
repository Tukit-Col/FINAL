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

export default async function Ingresar({
  searchParams,
}: {
  // En Next 16 `searchParams` llega como promesa; se lee en el servidor y el
  // destino viaja como prop, para no usar `useSearchParams` (que exigiria
  // envolver el formulario en <Suspense>).
  searchParams: Promise<{ destino?: string }>;
}) {
  const sesion = await sesionActual();
  if (sesion) {
    const destino = destinoDe(sesion);
    redirect(destino.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino.ruta);
  }

  const { destino } = await searchParams;
  // Solo ruta interna: "/algo" pero no "//host". El Route Handler lo revalida
  // igual (defensa en profundidad), pero saneamos ya aqui para no pasar basura.
  const destinoSeguro =
    destino && destino.startsWith("/") && !destino.startsWith("//") ? destino : undefined;

  const origen = descripcionOrigen();
  return <FormularioIngreso modo={origen.nombre} destino={destinoSeguro} />;
}
