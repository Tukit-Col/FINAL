// El panel de privacidad del titular (Ley 1581 de 2012, Decreto 1377 de 2013):
// la forma de `/v1/cuenta/mis-datos`, `/exportar` y `/supresion` en Identidad,
// y la unica regla que la web repite antes de llamar: la frase escrita.
//
// La frase se compara igual que en el servidor (sin mayusculas, sin tildes y con
// los espacios colapsados). La web solo la usa para habilitar el boton; quien
// decide es Identidad, que responde 422 `confirmacion_requerida`.

export const FRASE_CONFIRMACION_SUPRESION = "ELIMINAR MIS DATOS";

function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{Mn}/gu, "")
    .toUpperCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

/** ¿Escribio el titular la frase de confirmacion? */
export function confirmacionDeSupresionValida(texto: string | null | undefined): boolean {
  return typeof texto === "string" && normalizar(texto) === FRASE_CONFIRMACION_SUPRESION;
}

/** Una seccion que viene de otro servicio: si no respondio, `disponible: false`. */
export type SeccionRemota =
  | { disponible: false }
  | { disponible: true; total: number; elementos: Record<string, unknown>[] };

export interface ConsentimientoDelTitular {
  regimen: "registro_titular" | "registro_menor";
  version: string;
  matricula_id: string | null;
  aceptado_en: string;
  revocado_en: string | null;
}

export interface DatoSuprimido {
  dato: string;
  detalle: string;
}

export interface DatoConservado extends DatoSuprimido {
  fundamento: string;
}

export interface MisDatos {
  cuenta: {
    usuario_id: string;
    nombre: string | null;
    // Enmascarados en la vista (`a***@dominio.com`); completos en la exportacion.
    correo: string | null;
    celular: string | null;
    creado_en: string | null;
  };
  hijos: { matricula_id: string; apodo: string | null; grado: string }[];
  matriculas: {
    matricula_id: string;
    colegio_id: string;
    grado: string;
    anio_lectivo: number;
    apodo: string | null;
  }[];
  // En la vista solo etiqueta, ciudad y localidad; la linea va en la exportacion.
  direcciones: {
    direccion_id: string;
    etiqueta: string;
    ciudad: string;
    localidad: string | null;
    tiene_contacto?: boolean;
  }[];
  consentimientos: ConsentimientoDelTitular[];
  pedidos: SeccionRemota;
  casos: SeccionRemota;
  trabajos_kit: SeccionRemota;
  supresion: {
    frase_confirmacion: string;
    suprimido: DatoSuprimido[];
    conservado: DatoConservado[];
  };
}

export interface ResultadoSupresion {
  solicitud_id: string;
  estado: "propagando";
  suprimido: DatoSuprimido[];
  conservado: DatoConservado[];
  // Cuantos pedidos quedaron guardados y desvinculados; null si Comercio no respondio.
  pedidos_conservados: number | null;
  mensaje: string;
}

/** El total de una seccion remota, o null si el servicio no respondio. */
export function totalDeSeccion(seccion: SeccionRemota): number | null {
  return seccion.disponible ? seccion.total : null;
}

/** El nombre del archivo de la exportacion, el mismo que pone Identidad en su
 *  `Content-Disposition`: `tukit-mis-datos-AAAA-MM-DD.json`, por la fecha UTC. */
export function nombreArchivoMisDatos(fecha: Date): string {
  return `tukit-mis-datos-${fecha.toISOString().slice(0, 10)}.json`;
}
