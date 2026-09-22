// La frontera entre "de donde salen los datos" y "como se ven".
//
// Hay dos implementaciones: el cliente HTTP contra el backend real y el origen
// simulado que lee las semillas del repositorio. Las pantallas no saben cual
// tienen delante, y por eso el dia que el backend responda no hay que tocar
// ninguna: se cambia una variable de entorno.
//
// La interfaz esta partida en tres a proposito. `catalogo`, `colegios` y
// `listaOficial` son la parte ASUMIDA (ver `catalogo.ts`): si la 1.1 del
// contrato llega distinta, lo que hay que reescribir son tres metodos y no
// el cliente entero.

import type {
  AltaProducto,
  ColaAdmin,
  DecisionRevision,
  MarcarNoDisponible,
  ProductoDadoDeAlta,
  SinCoincidencia,
  SolicitudTrabajo,
  Trabajo,
  TrabajoAdmin,
  TrabajoCreado,
  ValidarLinea,
} from "./contrato";
import type { Catalogo, Colegio, ListaOficial } from "./catalogo";

/** Un archivo de lista, ya leido, con el hijo al que pertenece. */
export interface ArchivoLista {
  referencia: string;
  nombre: string;
  tipo: string;
  tamano: number;
  contenido: Blob;
}

export interface OrigenDatos {
  readonly nombre: "api" | "simulado";

  // §2 y §4 — el ciclo asincrono.
  crearTrabajo(solicitud: SolicitudTrabajo, archivos?: ArchivoLista[]): Promise<TrabajoCreado>;
  consultarTrabajo(trabajoId: string): Promise<Trabajo>;

  // ASUMIDO — superficie de lectura de catalogo (1.1).
  catalogo(): Promise<Catalogo>;
  colegios(): Promise<Colegio[]>;
  listaOficial(colegioId: string, grado: string): Promise<ListaOficial>;

  // §7 — revision humana.
  cola(): Promise<ColaAdmin>;
  trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin>;
  validarLinea(trabajoId: string, itemId: string, cuerpo: ValidarLinea): Promise<void>;
  marcarSinCoincidencia(
    trabajoId: string,
    itemId: string,
    cuerpo: SinCoincidencia,
  ): Promise<void>;
  altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta>;
  marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void>;
  decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void>;
}

/** Error de dominio con la forma del §11, para que la UI no invente mensajes. */
export class ErrorTukit extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
    this.name = "ErrorTukit";
  }
}
