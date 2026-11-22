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

export function confirmacionDeSupresionValida(texto: string | null | undefined): boolean {
  return typeof texto === "string" && normalizar(texto) === FRASE_CONFIRMACION_SUPRESION;
}

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
  pedidos_conservados: number | null;
  mensaje: string;
}

export function totalDeSeccion(seccion: SeccionRemota): number | null {
  return seccion.disponible ? seccion.total : null;
}

export function nombreArchivoMisDatos(fecha: Date): string {
  return `tukit-mis-datos-${fecha.toISOString().slice(0, 10)}.json`;
}
