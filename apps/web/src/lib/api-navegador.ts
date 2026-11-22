import type {
  AplicarCanonico,
  CambioDeDescarte,
  CambioDeProducto,
  MiCaso,
  MiCasoDetalle,
  OpcionesDeLinea,
  RetractoSolicitado,
  CasoCreado,
  Checkout,
  Contacto,
  ErrorApi,
  HijoNuevo,
  HijoSubida,
  PagoIniciado,
  Pedido,
  Preferencias,
  RegistroAcudiente,
  ResultadoPago,
  SolicitudMiCaso,
  SolicitudCheckout,
  SolicitudTrabajo,
  SubidaListas,
  Trabajo,
  TrabajoAplicado,
  TrabajoCreado,
  ResultadoSupresion,
} from "@tukit/contrato";
import { conEspera } from "@tukit/contrato";

export class FalloApi extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
  }
}

async function leer<T>(respuesta: Response): Promise<T> {
  const texto = await respuesta.text();
  const cuerpo: unknown = texto ? JSON.parse(texto) : null;
  if (!respuesta.ok) {
    const error = conEspera(
      respuesta.status,
      (cuerpo ?? {}) as ErrorApi & Record<string, unknown>,
      respuesta.headers.get("Retry-After"),
    );
    throw new FalloApi(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salió mal.",
      error,
    );
  }
  return cuerpo as T;
}

export async function crearTrabajo(
  solicitud: SolicitudTrabajo,
  archivos: { referencia: string; archivo: File }[] = [],
): Promise<TrabajoCreado> {
  if (archivos.length === 0) {
    return leer<TrabajoCreado>(
      await fetch("/api/trabajos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(solicitud),
      }),
    );
  }

  const forma = new FormData();
  forma.append("hijos", JSON.stringify(solicitud));
  for (const { referencia, archivo } of archivos) {
    forma.append("archivo", archivo, archivo.name);
    forma.append("referencia", referencia);
  }
  return leer<TrabajoCreado>(await fetch("/api/trabajos", { method: "POST", body: forma }));
}

export async function aplicarCanonico(cuerpo: AplicarCanonico): Promise<TrabajoAplicado> {
  return leer<TrabajoAplicado>(
    await fetch("/api/trabajos/aplicar-canonico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    }),
  );
}

export async function cambiarProductoDeKit(
  trabajoId: string,
  perfil: string,
  itemId: string,
  sku: string,
): Promise<CambioDeProducto> {
  const ruta =
    `/api/trabajos/${encodeURIComponent(trabajoId)}/kits/${encodeURIComponent(perfil)}` +
    `/lineas/${encodeURIComponent(itemId)}/producto`;
  return leer<CambioDeProducto>(
    await fetch(ruta, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sku }),
    }),
  );
}

export async function descartarLineaDeKit(
  trabajoId: string,
  perfil: string,
  itemId: string,
  descartado: boolean,
): Promise<CambioDeDescarte> {
  const ruta =
    `/api/trabajos/${encodeURIComponent(trabajoId)}/kits/${encodeURIComponent(perfil)}` +
    `/lineas/${encodeURIComponent(itemId)}/descarte`;
  return leer<CambioDeDescarte>(
    await fetch(ruta, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ descartado }),
    }),
  );
}

export async function opcionesDeLinea(
  trabajoId: string,
  perfil: string,
  itemId: string,
): Promise<OpcionesDeLinea> {
  const ruta =
    `/api/trabajos/${encodeURIComponent(trabajoId)}/kits/${encodeURIComponent(perfil)}` +
    `/lineas/${encodeURIComponent(itemId)}/opciones`;
  return leer<OpcionesDeLinea>(await fetch(ruta, { cache: "no-store" }));
}

export async function pedirRetracto(pedidoId: string, motivo: string): Promise<RetractoSolicitado> {
  return leer<RetractoSolicitado>(
    await fetch(`/api/pedidos/${encodeURIComponent(pedidoId)}/retracto`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo }),
    }),
  );
}

export async function verMisCasos(): Promise<MiCaso[]> {
  const cuerpo = await leer<{ casos: MiCaso[] }>(await fetch("/api/casos", { cache: "no-store" }));
  return cuerpo.casos;
}

export async function verMiCaso(casoId: string): Promise<MiCasoDetalle> {
  return leer<MiCasoDetalle>(
    await fetch(`/api/casos/${encodeURIComponent(casoId)}`, { cache: "no-store" }),
  );
}

export async function comentarMiCaso(casoId: string, texto: string): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/casos/${encodeURIComponent(casoId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texto }),
    }),
  );
}

export async function iniciarCheckout(
  trabajoId: string,
  cuerpo: SolicitudCheckout,
): Promise<Checkout> {
  return leer<Checkout>(
    await fetch(`/api/trabajos/${encodeURIComponent(trabajoId)}/ordenar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    }),
  );
}

export async function sincronizarPago(transaccionId: string): Promise<ResultadoPago> {
  return leer<ResultadoPago>(
    await fetch(`/api/pagos/${encodeURIComponent(transaccionId)}/sincronizar`, {
      method: "POST",
    }),
  );
}

export async function verPedido(pedidoId: string): Promise<Pedido> {
  return leer<Pedido>(await fetch(`/api/pedidos/${encodeURIComponent(pedidoId)}`));
}

export async function cancelarPedido(pedidoId: string): Promise<Pedido> {
  return leer<Pedido>(
    await fetch(`/api/pedidos/${encodeURIComponent(pedidoId)}/cancelar`, { method: "POST" }),
  );
}

export async function cancelarSolicitud(trabajoId: string): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/solicitudes/${encodeURIComponent(trabajoId)}/cancelar`, { method: "POST" }),
  );
}

export async function cancelarListaSubida(tareaId: string): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/solicitudes/listas/${encodeURIComponent(tareaId)}/cancelar`, {
      method: "POST",
    }),
  );
}

export async function suprimirMisDatos(confirmacion: string): Promise<ResultadoSupresion> {
  return leer<ResultadoSupresion>(
    await fetch("/api/cuenta/supresion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmacion }),
    }),
  );
}

export async function revocarConsentimientos(): Promise<{ revocados: number }> {
  return leer<{ revocados: number }>(
    await fetch("/api/cuenta/consentimientos/revocar", { method: "POST" }),
  );
}

export async function quitarHijo(matriculaId: string): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/cuenta/matriculas/${encodeURIComponent(matriculaId)}`, { method: "DELETE" }),
  );
}

export async function cambiarHijo(
  matriculaId: string,
  cambio: { colegio_id: string; grado: string },
): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/cuenta/matriculas/${encodeURIComponent(matriculaId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cambio),
    }),
  );
}

export async function pagarPedido(pedidoId: string): Promise<PagoIniciado> {
  return leer<PagoIniciado>(
    await fetch(`/api/pedidos/${encodeURIComponent(pedidoId)}/pagar`, { method: "POST" }),
  );
}

export async function sugerirColegio(datos: {
  colegioId: string;
  grado: string;
  anioLectivo: number;
  archivo?: File | null;
  contactoReferencia?: string;
}): Promise<{ tarea_id: string; estado: string }> {
  const forma = new FormData();
  forma.append("colegio_id", datos.colegioId);
  forma.append("grado", datos.grado);
  forma.append("anio_lectivo", String(datos.anioLectivo));
  if (datos.contactoReferencia) forma.append("contacto_referencia", datos.contactoReferencia);
  if (datos.archivo) forma.append("archivo", datos.archivo, datos.archivo.name);
  return leer<{ tarea_id: string; estado: string }>(
    await fetch("/api/sugerencias", { method: "POST", body: forma }),
  );
}

export async function subirListas(
  hijos: HijoSubida[],
  archivos: { referencia: string; archivo: File }[],
  contacto?: Contacto,
  preferencias?: Preferencias,
): Promise<SubidaListas> {
  const forma = new FormData();
  forma.append("hijos", JSON.stringify(hijos));
  if (contacto) forma.append("contacto", JSON.stringify(contacto));
  if (preferencias) forma.append("preferencias", JSON.stringify(preferencias));
  for (const { referencia, archivo } of archivos) {
    forma.append("archivo", archivo, archivo.name);
    forma.append("referencia", referencia);
  }
  return leer<SubidaListas>(await fetch("/api/listas/subir", { method: "POST", body: forma }));
}

export async function registrarAcudiente(
  datos: RegistroAcudiente,
): Promise<{ usuario_id: string; creado: boolean }> {
  return leer<{ usuario_id: string; creado: boolean }>(
    await fetch("/api/registro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    }),
  );
}

export async function iniciarSesion(credenciales: { correo: string; clave: string }): Promise<void> {
  await leer<unknown>(
    await fetch("/api/sesion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credenciales),
    }),
  );
}

export async function guardarMatriculas(hijos: HijoNuevo[]): Promise<{ total: number }> {
  return leer<{ total: number }>(
    await fetch("/api/cuenta/matriculas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hijos }),
    }),
  );
}

export async function crearCaso(solicitud: SolicitudMiCaso): Promise<CasoCreado> {
  return leer<CasoCreado>(
    await fetch("/api/casos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(solicitud),
    }),
  );
}

export async function consultarTrabajo(trabajoId: string): Promise<Trabajo> {
  return leer<Trabajo>(
    await fetch(`/api/trabajos/${encodeURIComponent(trabajoId)}`, { cache: "no-store" }),
  );
}

export function sondear(
  trabajoId: string,
  alCambiar: (trabajo: Trabajo) => void,
  alFallar: (fallo: FalloApi) => void,
): () => void {
  let vivo = true;
  let intervalo = 1000;

  async function ciclo(): Promise<void> {
    if (!vivo) return;
    try {
      const trabajo = await consultarTrabajo(trabajoId);
      if (!vivo) return;
      alCambiar(trabajo);
      if (trabajo.estado === "publicado" || trabajo.estado === "fallido") return;
    } catch (causa) {
      if (!vivo) return;
      if (causa instanceof FalloApi) {
        alFallar(causa);
        if (causa.estado === 401 || causa.estado === 404 || causa.estado === 429) return;
      }
    }
    intervalo = Math.min(intervalo * 1.4, 8000);
    setTimeout(() => void ciclo(), intervalo);
  }

  void ciclo();
  return () => {
    vivo = false;
  };
}
