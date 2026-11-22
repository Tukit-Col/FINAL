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
  searchParams: Promise<{ destino?: string }>;
}) {
  return conAvisoDeLimite(() => formulario(searchParams));
}

async function formulario(searchParams: Promise<{ destino?: string }>) {
  const sesion = await sesionActual();
  if (sesion) {
    const destino = destinoDe(sesion);
    redirect(destino.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino.ruta);
  }

  const { destino } = await searchParams;
  const destinoSeguro =
    destino && destino.startsWith("/") && !destino.startsWith("//") ? destino : undefined;

  return <FormularioIngreso destino={destinoSeguro} />;
}
