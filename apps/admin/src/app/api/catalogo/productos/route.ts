import { origenDeDatos } from "@tukit/contrato/servidor";
import type { FiltrosProductos, Nivel } from "@tukit/contrato";
import { NIVELES } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";

function bandera(valor: string | null): boolean | undefined {
  if (valor === null) return undefined;
  return valor === "true";
}

function enteroPositivo(valor: string | null): number | undefined {
  if (valor === null) return undefined;
  const n = Number(valor);
  return Number.isInteger(n) && n > 0 ? n : undefined;
}

export async function GET(peticion: Request): Promise<Response> {
  const params = new URL(peticion.url).searchParams;

  const nivelCrudo = params.get("nivel");
  const nivel: Nivel | undefined =
    nivelCrudo && (NIVELES as readonly string[]).includes(nivelCrudo)
      ? (nivelCrudo as Nivel)
      : undefined;

  const filtros: FiltrosProductos = {
    busqueda: params.get("busqueda") ?? undefined,
    concepto: params.get("concepto") ?? undefined,
    nivel,
    personaje: params.get("personaje") ?? undefined,
    con_personaje: bandera(params.get("con_personaje")),
    con_precio: bandera(params.get("con_precio")),
    con_ofertas: bandera(params.get("con_ofertas")),
    pagina: enteroPositivo(params.get("pagina")),
    por_pagina: enteroPositivo(params.get("por_pagina")),
  };

  try {
    const pagina = await origenDeDatos().buscarProductos(filtros);
    return Response.json(pagina, { status: 200 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
