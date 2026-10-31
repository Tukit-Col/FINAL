// Pantalla de ingreso.
//
// Se autentica contra identidad a traves del gateway. Si ya hay sesion, no
// tiene sentido volver a pedir credenciales: se redirige al destino que
// corresponde por rol.

import { redirect } from "next/navigation";
import { destinoDe, urlAdmin } from "@tukit/contrato/servidor";
import { sesionActual } from "@/lib/sesion";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
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
  // Con el cupo agotado (429) no se ofrece entrar de nuevo: la sesion sigue
  // viva y otro intento gastaria el cupo de entrar de la IP.
  return conAvisoDeLimite(() => formulario(searchParams));
}

async function formulario(searchParams: Promise<{ destino?: string }>) {
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

  return <FormularioIngreso destino={destinoSeguro} />;
}
