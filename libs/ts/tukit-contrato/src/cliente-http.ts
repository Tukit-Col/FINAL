// Cliente HTTP contra el backend real, sobre `/v1`.
//
// Corre SOLO en el servidor de Next: la URL del backend no sale al navegador
// y el tiempo de espera largo que el pipeline necesita no se puede pedir desde
// un `rewrite`, que corta a los 30 s. Es la misma razon que ya estaba escrita
// en el proxy del prototipo, y se conserva.

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
import {
  ErrorTukit,
  type ArchivoLista,
  type Credenciales,
  type OrigenDatos,
  type Sesion,
} from "./origen";

// El pipeline tarda minutos, no segundos, y eso es deliberado (§0).
const TIEMPO_MAXIMO_MS = 300_000;

export interface OpcionesCliente {
  urlBase: string;
  tiempoMaximoMs?: number;
}

export class ClienteApi implements OrigenDatos {
  readonly nombre = "api" as const;
  private readonly urlBase: string;
  private readonly tiempoMaximoMs: number;

  constructor(opciones: OpcionesCliente) {
    this.urlBase = opciones.urlBase.replace(/\/+$/, "");
    this.tiempoMaximoMs = opciones.tiempoMaximoMs ?? TIEMPO_MAXIMO_MS;
  }

  private async pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
    let respuesta: Response;
    try {
      respuesta = await fetch(`${this.urlBase}${ruta}`, {
        ...init,
        signal: AbortSignal.timeout(this.tiempoMaximoMs),
        cache: "no-store",
      });
    } catch (causa) {
      const nombre = (causa as { name?: string }).name;
      if (nombre === "TimeoutError") {
        throw new ErrorTukit(
          504,
          "tiempo_agotado",
          "El backend tardo mas de cinco minutos en responder.",
        );
      }
      throw new ErrorTukit(
        503,
        "backend_no_disponible",
        `No pudimos hablar con el backend en ${this.urlBase}. Levantalo o pon TUKIT_ORIGEN_DATOS=simulado.`,
      );
    }

    if (respuesta.status === 204) return undefined as T;

    const texto = await respuesta.text();
    let cuerpo: unknown = null;
    try {
      cuerpo = texto ? JSON.parse(texto) : null;
    } catch {
      cuerpo = null;
    }

    if (!respuesta.ok) {
      const detalle = (cuerpo ?? {}) as Record<string, unknown>;
      throw new ErrorTukit(
        respuesta.status,
        typeof detalle["error"] === "string" ? detalle["error"] : "error_desconocido",
        typeof detalle["mensaje"] === "string"
          ? detalle["mensaje"]
          : `El backend respondio ${respuesta.status}.`,
        detalle,
      );
    }

    return cuerpo as T;
  }

  private json(ruta: string, cuerpo: unknown, metodo = "POST"): Promise<void> {
    return this.pedir<void>(ruta, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  // ------------------------------------------------------------ §Identidad
  //
  // El cliente NO habla con identidad directamente: pega al gateway
  // (`urlBase`), y el gateway rutea a identidad `/v1/sesiones*`, valida el
  // token y compara `version_permisos` (§1, edges C4 web→gateway→identidad).
  // El error 503 de `pedir` ("levantalo o pon TUKIT_ORIGEN_DATOS=simulado")
  // cubre el login cuando el backend esta caido, gratis.
  async iniciarSesion(cred: Credenciales): Promise<{ sesion: Sesion; token: string }> {
    return this.pedir<{ sesion: Sesion; token: string }>("/v1/sesiones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cred),
    });
  }

  sesionActual(token: string): Promise<Sesion | null> {
    return this.pedir<Sesion | null>("/v1/sesiones/actual", {
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  cerrarSesion(token: string): Promise<void> {
    return this.pedir<void>("/v1/sesiones/cierre", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  // ------------------------------------------------------------------ §2, §4
  async crearTrabajo(
    solicitud: SolicitudTrabajo,
    archivos: ArchivoLista[] = [],
  ): Promise<TrabajoCreado> {
    if (archivos.length === 0) {
      return this.pedir<TrabajoCreado>("/v1/trabajos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(solicitud),
      });
    }

    // Entrada (b): `multipart/form-data` con el JSON en el campo `hijos` y un
    // `archivo` por hijo, tal como lo escribe el §2.
    const forma = new FormData();
    forma.append("hijos", JSON.stringify(solicitud));
    for (const archivo of archivos) {
      forma.append("archivo", archivo.contenido, archivo.nombre);
      forma.append("referencia", archivo.referencia);
    }
    return this.pedir<TrabajoCreado>("/v1/trabajos", { method: "POST", body: forma });
  }

  consultarTrabajo(trabajoId: string): Promise<Trabajo> {
    return this.pedir<Trabajo>(`/v1/trabajos/${encodeURIComponent(trabajoId)}`);
  }

  // ------------------------------------------------------- ASUMIDO (v1.1)
  catalogo(): Promise<Catalogo> {
    return this.pedir<Catalogo>("/v1/catalogo");
  }

  colegios(): Promise<Colegio[]> {
    return this.pedir<Colegio[]>("/v1/catalogo/colegios");
  }

  listaOficial(colegioId: string, grado: string): Promise<ListaOficial> {
    return this.pedir<ListaOficial>(
      `/v1/catalogo/colegios/${encodeURIComponent(colegioId)}/listas/${encodeURIComponent(grado)}`,
    );
  }

  // ------------------------------------------------------------------ §7
  cola(): Promise<ColaAdmin> {
    return this.pedir<ColaAdmin>("/v1/admin/cola");
  }

  trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin> {
    return this.pedir<TrabajoAdmin>(`/v1/admin/trabajos/${encodeURIComponent(trabajoId)}`);
  }

  validarLinea(trabajoId: string, itemId: string, cuerpo: ValidarLinea): Promise<void> {
    return this.json(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/lineas/${encodeURIComponent(itemId)}/validar`,
      cuerpo,
    );
  }

  marcarSinCoincidencia(
    trabajoId: string,
    itemId: string,
    cuerpo: SinCoincidencia,
  ): Promise<void> {
    return this.json(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/lineas/${encodeURIComponent(itemId)}/sin-coincidencia`,
      cuerpo,
    );
  }

  altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta> {
    return this.pedir<ProductoDadoDeAlta>("/v1/admin/productos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void> {
    return this.json(`/v1/admin/productos/${encodeURIComponent(sku)}/no-disponible`, cuerpo);
  }

  decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void> {
    return this.json(`/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/revision`, cuerpo);
  }

  // ------------------------------------------------- ASUMIDO (comercio 1.x)
  pedidos(): Promise<TableroComercio> {
    return this.pedir<TableroComercio>("/v1/comercio/pedidos");
  }

  pedido(pedidoId: string): Promise<Pedido> {
    return this.pedir<Pedido>(`/v1/comercio/pedidos/${encodeURIComponent(pedidoId)}`);
  }

  // ------------------------------------------------ ASUMIDO (operacion 1.x)
  casos(): Promise<BandejaOperacion> {
    return this.pedir<BandejaOperacion>("/v1/operacion/casos");
  }

  caso(casoId: string): Promise<Caso> {
    return this.pedir<Caso>(`/v1/operacion/casos/${encodeURIComponent(casoId)}`);
  }
}
