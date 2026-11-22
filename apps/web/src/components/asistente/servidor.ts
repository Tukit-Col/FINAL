import { cabecerasReenviadas, origenDeDatos, urlApi } from "@tukit/contrato/servidor";
import { tokenDeSesion } from "@/lib/sesion";
import { validarEspec, type EspecUi } from "./espec";

const ESPERA_MS = 20_000;

export interface Resultado {
  estado: number;
  cuerpo: Record<string, unknown>;
}

export const NO_DISPONIBLE: Resultado = {
  estado: 503,
  cuerpo: {
    error: "asistente_no_disponible",
    mensaje: "El asistente no está disponible ahora. Puedes llenar el formulario como siempre.",
  },
};

export const DESACTIVADO: Resultado = {
  estado: 503,
  cuerpo: {
    error: "asistente_desactivado",
    mensaje: "El asistente no está activo en este entorno.",
  },
};

export async function reenviar(ruta: string, cuerpo: unknown): Promise<Resultado> {
  const token = await tokenDeSesion();
  const reenviadas = await cabecerasReenviadas(ruta);
  let respuesta: Response;
  try {
    respuesta = await fetch(`${urlApi()}${ruta}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...reenviadas,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(cuerpo),
      signal: AbortSignal.timeout(ESPERA_MS),
      cache: "no-store",
    });
  } catch {
    return NO_DISPONIBLE;
  }
  let json: unknown = null;
  try {
    json = await respuesta.json();
  } catch {
    json = null;
  }
  if (typeof json !== "object" || json === null || Array.isArray(json)) {
    return respuesta.ok ? NO_DISPONIBLE : { estado: respuesta.status, cuerpo: { error: "error_desconocido" } };
  }
  const objeto = json as Record<string, unknown>;
  if (respuesta.status === 404 && objeto["error"] === "asistente_desactivado") return DESACTIVADO;
  if (respuesta.status === 503) return NO_DISPONIBLE;
  return { estado: respuesta.status, cuerpo: objeto };
}

export function especSegura(v: unknown): EspecUi | null {
  return validarEspec(v);
}

export async function imagenDePersonaje(nombre: string): Promise<string | null> {
  try {
    const pagina = await origenDeDatos().buscarProductos({
      personaje: nombre,
      con_precio: true,
      por_pagina: 12,
    });
    for (const producto of pagina.productos) {
      const url = producto.imagen_url;
      if (typeof url !== "string") continue;
      try {
        if (new URL(url).protocol === "https:") return url;
      } catch {
      }
    }
  } catch {
  }
  return null;
}

export async function estadoDelAsistente(): Promise<"activo" | "apagado" | "sin_modelo" | "caido"> {
  try {
    const r = await fetch(`${urlApi()}/v1/nl2c/estado`, {
      signal: AbortSignal.timeout(4_000),
      cache: "no-store",
    });
    if (!r.ok) return r.status === 404 ? "apagado" : "caido";
    const j = (await r.json()) as { activo?: unknown; modelo_configurado?: unknown };
    if (j.activo !== true) return "apagado";
    return j.modelo_configurado === false ? "sin_modelo" : "activo";
  } catch {
    return "caido";
  }
}
