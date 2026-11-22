// Cuerpos de las peticiones que arma `/empezar` al enviar el formulario.
//
// Decisiones:
// - Son funciones puras: el orden de las llamadas (registro, matrículas, trabajo, subida) y los
//   reintentos por firma siguen en el componente.
// - Una lista subida viaja por el colegio de Tukit, por el DANE del directorio o, si el acudiente
//   escribió el colegio a mano, solo por su nombre.

import type {
  HijoNuevo,
  HijoSolicitud,
  GradoCanonico,
  PerfilKit,
  SolicitudTrabajo,
} from "@tukit/contrato";
import {
  gradoVerificado,
  necesitaArchivo,
  prioridadElegida,
  type ClavePrioridad,
  type ColegiosPorId,
  type HijoFormulario,
} from "./formulario-empezar.ts";
import { filtrosDePreferencias } from "./restricciones-asistente.ts";

const MAX_APODO = 40;

function apodoDe(hijo: HijoFormulario, recortar: boolean): { apodo?: string } {
  const apodo = hijo.apodo.trim();
  if (!apodo) return {};
  return { apodo: recortar ? apodo.slice(0, MAX_APODO) : apodo };
}

export function personajesPorHijo(hijos: readonly HijoFormulario[]): Record<string, string[]> {
  const porHijo: Record<string, string[]> = {};
  for (const hijo of hijos) {
    const lista = hijo.personajes
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    if (lista.length > 0) porHijo[hijo.referencia] = lista;
  }
  return porHijo;
}

export interface EntradaPreferencias {
  prioridad: ClavePrioridad;
  presupuesto: string;
  conTope: boolean;
  personajePorHijo: Record<string, string[]>;
  marcasExcluidas: readonly string[];
  soloDisponibles: boolean;
}

export function construirPreferencias(e: EntradaPreferencias) {
  const elegida = prioridadElegida(e.prioridad);
  return {
    pesos: elegida.pesos,
    disposicion_sobreprecio: elegida.disposicion_sobreprecio,
    prioridad: elegida.clave,
    ...(e.conTope ? { presupuesto_por_hijo: Number.parseInt(e.presupuesto, 10) } : {}),
    ...(Object.keys(e.personajePorHijo).length > 0 ? { personaje_por_hijo: e.personajePorHijo } : {}),
    ...filtrosDePreferencias(e.marcasExcluidas, e.soloDisponibles),
  };
}

export function construirRegistro(
  datos: { correo: string; clave: string; aceptaTerminos: boolean; celular: string },
  hijos: readonly HijoFormulario[],
) {
  return {
    correo: datos.correo,
    clave: datos.clave,
    acepta_terminos: datos.aceptaTerminos,
    celular: datos.celular,
    hijos: hijos
      .filter((hijo) => hijo.colegioId)
      .map((hijo) => ({
        colegio_id: hijo.colegioId,
        grado: hijo.grado,
        ...apodoDe(hijo, false),
      })),
  };
}

export function matriculasNuevas(hijos: readonly HijoFormulario[]): HijoNuevo[] {
  return hijos
    .filter((hijo) => !hijo.precargado && hijo.colegioId)
    .map((hijo) => ({
      colegio_id: hijo.colegioId,
      grado: hijo.grado,
      ...apodoDe(hijo, false),
    }));
}

export function hijosConListaVerificada(
  hijos: readonly HijoFormulario[],
  porId: ColegiosPorId,
): HijoFormulario[] {
  return hijos.filter((hijo) => hijo.colegioId && gradoVerificado(hijo, porId));
}

export function hijosParaSubir(hijos: readonly HijoFormulario[], porId: ColegiosPorId): HijoFormulario[] {
  return hijos.filter((hijo) => necesitaArchivo(hijo, porId) && hijo.archivo);
}

export function canonicoDelUnicoHijo(
  hijos: readonly HijoFormulario[],
  canonicos: readonly GradoCanonico[],
  porId: ColegiosPorId,
): { soloHijo: HijoFormulario; canonico: GradoCanonico } | null {
  const soloHijo = hijos.length === 1 ? hijos[0]! : null;
  if (!soloHijo || !soloHijo.colegioId || !gradoVerificado(soloHijo, porId)) return null;
  const canonico = canonicos.find(
    (c) => c.colegio_id === soloHijo.colegioId && c.grado === soloHijo.grado,
  );
  return canonico ? { soloHijo, canonico } : null;
}

export function cuerpoCanonico(
  soloHijo: HijoFormulario,
  canonico: GradoCanonico,
  perfil: PerfilKit,
  personaje: string | undefined,
) {
  return {
    colegio_id: canonico.colegio_id,
    grado: canonico.grado,
    anio_lectivo: canonico.anio_lectivo,
    perfil,
    ...(personaje ? { personaje } : {}),
    ...apodoDe(soloHijo, true),
  };
}

export function construirSolicitud(
  hijos: readonly HijoFormulario[],
  preferencias: SolicitudTrabajo["preferencias"],
): SolicitudTrabajo {
  return {
    hijos: hijos.map<HijoSolicitud>((hijo) => ({
      referencia: hijo.referencia,
      colegio_id: hijo.colegioId,
      grado: hijo.grado,
      ...apodoDe(hijo, true),
    })),
    preferencias,
  };
}

export function destinoDeSubida(hijo: HijoFormulario) {
  return {
    referencia: hijo.referencia,
    ...(hijo.colegioId
      ? { colegio_id: hijo.colegioId }
      : hijo.colegioDane
        ? { colegio_dane: hijo.colegioDane, colegio_nombre: hijo.colegioNombre }
        : { colegio_nombre: hijo.colegioNombre }),
    grado: hijo.grado,
    ...apodoDe(hijo, true),
  };
}

export function archivosDeSubida(hijos: readonly HijoFormulario[]) {
  return hijos.map((hijo) => ({ referencia: hijo.referencia, archivo: hijo.archivo as File }));
}
