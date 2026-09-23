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
import type { Pedido, TableroComercio } from "./comercio";
import type { BandejaOperacion, Caso } from "./operacion";

/** Los roles del sistema (filas de `rol` en identidad, ADR 0013). No es un
 *  enum del dominio: el codigo pregunta `puede(...)`, nunca `if rol in (...)`.
 *  Se listan aqui solo para que la UI enrute por rol sin decidir las reglas. */
export type Rol =
  | "acudiente"
  | "colegio_admin"
  | "colegio_docente"
  | "operador"
  | "admin";

/** El tipo de ambito sobre el que se concede un rol (base.py `AmbitoTipo`). */
export type AmbitoTipo = "global" | "colegio" | "sede" | "matricula";

/** Un rol vigente sobre un ambito, tal como lo resuelve identidad. El `id` es
 *  nulo SOLO para el ambito global, misma regla que `asignacion_ambito_coherente`. */
export interface RolAsignado {
  rol: Rol;
  ambito: { tipo: AmbitoTipo; id: string | null };
}

/** Quien es quien pregunta. Lleva el correo propio (para saludar) y nunca el
 *  de nadie mas ni el nombre de un menor: identidad referencia por
 *  identificador (§12.4). */
export interface Sesion {
  usuario_id: string;
  correo: string;
  nombre: string;
  roles: RolAsignado[];
  // Lo que el gateway compara para revocar la sesion (§1).
  version_permisos: number;
}

/** Lo minimo para autenticar. La clave es opaca al contrato. */
export interface Credenciales {
  correo: string;
  clave: string;
}

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

  // §Identidad — autenticacion y sesion (identidad, ADR 0013).
  //
  // El token es opaco al contrato: en `api` es lo que emite identidad/gateway;
  // en `simulado` es un sello base64 sin firma. `iniciarSesion` devuelve la
  // Sesion, y quien llama (un Route Handler) es quien pone la cookie: el origen
  // no toca cookies, igual que el resto de la interfaz no sabe de HTTP.
  iniciarSesion(credenciales: Credenciales): Promise<{ sesion: Sesion; token: string }>;
  sesionActual(token: string): Promise<Sesion | null>;
  cerrarSesion(token: string): Promise<void>;

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

  // ASUMIDO — superficie de lectura de `comercio` (logistica del back-office).
  // Ver `comercio.ts`: el contrato v1.0 aun no publica esto.
  pedidos(): Promise<TableroComercio>;
  pedido(pedidoId: string): Promise<Pedido>;

  // ASUMIDO — superficie de lectura de `operacion` (tickets del back-office).
  // Ver `operacion.ts`.
  casos(): Promise<BandejaOperacion>;
  caso(casoId: string): Promise<Caso>;
}

/** A donde mandar a alguien despues de entrar, segun sus roles (ADR 0008: tres
 *  apps por rol — web=acudiente, colegio=B2B, admin=personal interno).
 *
 *  La regla vive en UN solo sitio, no en los componentes, igual que el resto
 *  del contrato: "las pantallas no deciden reglas". Precedencia: el equipo
 *  interno gana sobre el colegio y este sobre el acudiente, porque a alguien de
 *  Tukit se le podria sembrar tambien un rol menor. `app` es logico; quien
 *  llama resuelve el origen concreto (:3001, etc.) sin hardcodearlo aqui. */
export function destinoDe(sesion: Sesion): { app: "web" | "colegio" | "admin"; ruta: string } {
  const roles = new Set(sesion.roles.map((r) => r.rol));
  if (roles.has("admin") || roles.has("operador")) return { app: "admin", ruta: "/" };
  if (roles.has("colegio_admin") || roles.has("colegio_docente"))
    return { app: "colegio", ruta: "/portal" };
  return { app: "web", ruta: "/dashboard" };
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
