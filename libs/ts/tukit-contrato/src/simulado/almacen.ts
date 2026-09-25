// Donde viven los trabajos simulados.
//
// En un fichero y no en memoria porque `apps/web` y `apps/admin` son dos
// procesos de Next distintos, y la pausa humana del §7 solo se puede
// demostrar si el trabajo que el acudiente esta esperando es el mismo que el
// admin aprueba. Con un objeto en memoria, aprobar en admin no movia nada en
// web y el flujo completo no se podia ver.
//
// El directorio va en el temporal del sistema para no ensuciar el repositorio
// ni pelear con el `.gitignore`, que es de otro equipo. Se puede mover con
// `TUKIT_SIMULADO_DIR`.

import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { SolicitudTrabajo } from "../contrato";
import type { Caso } from "../operacion";

export interface RegistroTrabajo {
  trabajo_id: string;
  solicitud: SolicitudTrabajo;
  /** Desde cuando corre el reloj. `devolver` lo reinicia: el §7 reabre el trabajo. */
  base_ms: number;
  creado_ms: number;
  origen_entrada: "lista_oficial" | "archivo";
  archivos: string[];
  aprobado: boolean;
  nota_revision: string | null;
  validadas: string[];
  sin_coincidencia: Record<string, string>;
  skus_no_disponibles: string[];
  productos_manuales: Record<string, { sku: string; nombre: string; precio: number }>;
}

interface Contenido {
  trabajos: Record<string, RegistroTrabajo>;
  // Casos abiertos por una persona desde el centro de ayuda. Los casos del
  // §Procesos (fallas de la saga) NO viven aqui: esos se derivan de los
  // trabajos en `back-office.ts`. Aqui solo lo que un acudiente escribio.
  casos?: Record<string, Caso>;
}

const DIRECTORIO = process.env["TUKIT_SIMULADO_DIR"] ?? join(tmpdir(), "tukit-simulado");
const FICHERO = join(DIRECTORIO, "trabajos.json");

function leer(): Contenido {
  try {
    return JSON.parse(readFileSync(FICHERO, "utf8")) as Contenido;
  } catch {
    return { trabajos: {} };
  }
}

function escribir(contenido: Contenido): void {
  mkdirSync(DIRECTORIO, { recursive: true });
  // Escritura por temporal y renombre: dos procesos escribiendo a la vez no
  // dejan el fichero a medias, que con un `writeFileSync` directo si pasa.
  const temporal = `${FICHERO}.${process.pid}.tmp`;
  writeFileSync(temporal, JSON.stringify(contenido), "utf8");
  renameSync(temporal, FICHERO);
}

export function guardar(registro: RegistroTrabajo): void {
  const contenido = leer();
  contenido.trabajos[registro.trabajo_id] = registro;
  escribir(contenido);
}

export function obtener(trabajoId: string): RegistroTrabajo | undefined {
  return leer().trabajos[trabajoId];
}

export function listar(): RegistroTrabajo[] {
  return Object.values(leer().trabajos).sort((a, b) => a.creado_ms - b.creado_ms);
}

export function actualizar(
  trabajoId: string,
  cambio: (registro: RegistroTrabajo) => void,
): RegistroTrabajo | undefined {
  const contenido = leer();
  const registro = contenido.trabajos[trabajoId];
  if (!registro) return undefined;
  cambio(registro);
  escribir(contenido);
  return registro;
}

/** Borra un trabajo del almacen. Devuelve `false` si no existia. */
export function eliminar(trabajoId: string): boolean {
  const contenido = leer();
  if (!(trabajoId in contenido.trabajos)) return false;
  delete contenido.trabajos[trabajoId];
  escribir(contenido);
  return true;
}

// --------------------------------------------------------------- Casos

/** Anexa un caso abierto por una persona. `operacion` es "solo anexar"
 *  (ARQUITECTURA.md §5): un caso no se borra, se cierra cambiando su estado. */
export function guardarCaso(caso: Caso): void {
  const contenido = leer();
  (contenido.casos ??= {})[caso.caso_id] = caso;
  escribir(contenido);
}

/** Los casos abiertos por personas, del mas reciente al mas antiguo. */
export function listarCasos(): Caso[] {
  return Object.values(leer().casos ?? {}).sort((a, b) =>
    a.abierto_en < b.abierto_en ? 1 : -1,
  );
}

export function rutaDelAlmacen(): string {
  return FICHERO;
}
