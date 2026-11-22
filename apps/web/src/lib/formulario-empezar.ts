// Reglas del formulario de `/empezar`: qué falta, en qué paso va el acudiente y qué prioridad eligió.
//
// Decisiones:
// - Son funciones puras sobre datos planos (sin React, sin red), para probarlas con `node --test`.
// - Un hijo necesita archivo cuando su colegio no está en Tukit o cuando su grado no tiene lista
//   verificada; con lista verificada se arma el kit sin subir nada.

import type { PerfilKit, Pesos } from "@tukit/contrato";

export interface HijoFormulario {
  referencia: string;
  colegioId: string;
  colegioDane: string;
  colegioNombre: string;
  grado: string;
  apodo: string;
  precargado: boolean;
  archivo: File | null;
  errorArchivo: string | null;
  personajes: string;
}

export type Modo = "elegir" | "existente" | "nuevo" | "autenticado";

export type ClavePrioridad = "precio" | "equilibrio" | "calidad";

export interface Prioridad {
  clave: ClavePrioridad;
  titulo: string;
  detalle: string;
  pesos: Pesos;
  disposicion_sobreprecio: number;
}

export const PRIORIDADES: Prioridad[] = [
  {
    clave: "precio",
    titulo: "Lo más económico",
    detalle: "Gastar lo menos posible. Te marcamos el Ahorrador.",
    pesos: { precio: 0.6, marca_exigida: 0.15, calidad: 0.2, personaje: 0.05 },
    disposicion_sobreprecio: 0,
  },
  {
    clave: "equilibrio",
    titulo: "Un punto medio",
    detalle:
      "Te armamos el kit «A tu Medida»: más marca que el Ahorrador, sin llegar al precio del Premium. Si quieres, ponle un tope.",
    pesos: { precio: 0.35, marca_exigida: 0.3, calidad: 0.25, personaje: 0.1 },
    disposicion_sobreprecio: 0.05,
  },
  {
    clave: "calidad",
    titulo: "Puedo estirarme un poco",
    detalle: "Marcas y acabados de gama alta. Te marcamos el Premium.",
    pesos: { precio: 0.15, marca_exigida: 0.35, calidad: 0.4, personaje: 0.1 },
    disposicion_sobreprecio: 0.1,
  },
];

export function prioridadElegida(clave: ClavePrioridad): Prioridad {
  return PRIORIDADES.find((p) => p.clave === clave) ?? PRIORIDADES[1]!;
}

export function perfilDeSeleccion(prioridad: ClavePrioridad, tienePersonaje: boolean): PerfilKit {
  if (tienePersonaje) return "Fan";
  return prioridad === "calidad" ? "Premium" : "Ahorrador";
}

export function hijoVacio(indice: number): HijoFormulario {
  return {
    referencia: `hijo-${indice}`,
    colegioId: "",
    colegioDane: "",
    colegioNombre: "",
    grado: "",
    apodo: "",
    precargado: false,
    archivo: null,
    errorArchivo: null,
    personajes: "",
  };
}

export function siguienteReferencia(hijos: readonly HijoFormulario[]): number {
  return Math.max(0, ...hijos.map((h) => Number(h.referencia.slice(5)) || 0)) + 1;
}

export function unirEnLista(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

export type ColegiosPorId = ReadonlyMap<string, { grados: readonly string[] }>;

export function gradoVerificado(hijo: HijoFormulario, porId: ColegiosPorId): boolean {
  return porId.get(hijo.colegioId)?.grados.includes(hijo.grado) ?? false;
}

export function necesitaArchivo(hijo: HijoFormulario, porId: ColegiosPorId): boolean {
  if (!hijo.colegioId) return true;
  return hijo.grado !== "" && !gradoVerificado(hijo, porId);
}

export function hijoCompleto(hijo: HijoFormulario, porId: ColegiosPorId): boolean {
  if (!hijo.grado) return false;
  if (!hijo.colegioId) return Boolean(hijo.colegioNombre) && hijo.archivo !== null;
  if (necesitaArchivo(hijo, porId)) return hijo.archivo !== null;
  return true;
}

export interface DatosContacto {
  correo: string;
  celular: string;
  claveOk: boolean;
  aceptaTerminos: boolean;
}

export function contactoCompleto(d: DatosContacto): boolean {
  return d.correo.trim().length > 3 && d.celular.trim().length > 6 && d.claveOk && d.aceptaTerminos;
}

export function faltantesDeContacto(d: DatosContacto): string[] {
  const faltantes: string[] = [];
  if (d.correo.trim().length <= 3) faltantes.push("tu correo");
  if (!d.claveOk) faltantes.push("una contraseña de al menos 8 caracteres");
  if (!d.aceptaTerminos) faltantes.push("aceptar la política de datos y los términos");
  if (d.celular.trim().length <= 6) faltantes.push("tu celular");
  return faltantes;
}

export function faltantesDeHijos(hijos: readonly HijoFormulario[], porId: ColegiosPorId): string[] {
  const faltantes: string[] = [];
  hijos.forEach((hijo, i) => {
    const suf = hijos.length > 1 ? ` del hijo ${i + 1}` : "";
    const tieneColegio = Boolean(hijo.colegioId) || Boolean(hijo.colegioNombre);
    if (!tieneColegio) faltantes.push(`el colegio${suf}`);
    else if (!hijo.grado) faltantes.push(`el grado${suf}`);
    else if (necesitaArchivo(hijo, porId) && hijo.archivo === null) faltantes.push(`la lista${suf}`);
  });
  return faltantes;
}

export type PasoEmpezar = "registro" | "hijos" | "contacto" | "preferencias";
export type EstadoPaso = "completo" | "actual" | "futuro";

export const ORDEN_PASOS: readonly PasoEmpezar[] = ["registro", "hijos", "contacto", "preferencias"];

export interface Faltantes {
  contacto: readonly string[];
  hijos: readonly string[];
}

export function pasoActual(modo: Modo, faltantes: Faltantes): PasoEmpezar | null {
  if (modo !== "nuevo" && modo !== "autenticado") return null;
  if (modo === "nuevo" && faltantes.contacto.length > 0) return "registro";
  if (faltantes.hijos.length > 0) return "hijos";
  return "preferencias";
}

export function estadoDePaso(
  paso: PasoEmpezar,
  actual: PasoEmpezar | null,
  faltantes: Faltantes,
): EstadoPaso {
  if (actual === null) return "futuro";
  if (paso === actual) return "actual";
  if (ORDEN_PASOS.indexOf(paso) > ORDEN_PASOS.indexOf(actual)) return "futuro";
  const pendientes = paso === "hijos" ? faltantes.hijos : paso === "contacto" ? faltantes.contacto : [];
  return pendientes.length === 0 ? "completo" : "futuro";
}

export function pasoEsFuturo(paso: PasoEmpezar, actual: PasoEmpezar | null): boolean {
  return actual !== null && ORDEN_PASOS.indexOf(paso) > ORDEN_PASOS.indexOf(actual);
}

export function faltantesEnOrden(modo: Modo, faltantes: Faltantes): string[] {
  return modo === "nuevo"
    ? [...faltantes.contacto, ...faltantes.hijos]
    : [...faltantes.hijos, ...faltantes.contacto];
}
