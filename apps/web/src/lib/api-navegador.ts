// El lado del navegador del ciclo asincrono.
//
// Habla solo con los Route Handlers de esta misma app, nunca con el backend:
// asi la URL del backend vive en un solo sitio de servidor y el cliente no
// tiene que saber que existe.

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
    // Un 429 llega con la espera en el mensaje aunque el cuerpo no la traiga.
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

/**
 * Ruta rápida: aplica el nivel + personaje del acudiente a la cache bendita de
 * un (colegio, grado) ya publicado, sin subir PDF ni entrar a la cola. Devuelve
 * el trabajo creado y el total del pedido congelado.
 */
export async function aplicarCanonico(cuerpo: AplicarCanonico): Promise<TrabajoAplicado> {
  return leer<TrabajoAplicado>(
    await fetch("/api/trabajos/aplicar-canonico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    }),
  );
}

/**
 * Checkout: el acudiente paga el kit de un trabajo publicado. Manda solo perfil
 * + correo + dirección; el backend arma la orden en Comercio y devuelve la url
 * de la pasarela a la que redirigir. No viaja ningún id de producto.
 */
/**
 * El acudiente cambia un producto de su kit por el sugerido o una de sus
 * alternativas. El total se recalcula en el servidor: después hay que volver
 * a leer el trabajo (`router.refresh()`).
 */
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

/** Quita un renglón del kit ("ya lo tengo") o lo vuelve a poner. Reversible. */
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

/** Los productos del mismo concepto para un renglón, con la diferencia de precio. */
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

/** Retracto (Ley 1480, art. 47) de uno de mis pedidos. */
export async function pedirRetracto(pedidoId: string, motivo: string): Promise<RetractoSolicitado> {
  return leer<RetractoSolicitado>(
    await fetch(`/api/pedidos/${encodeURIComponent(pedidoId)}/retracto`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo }),
    }),
  );
}

/** Mis casos. */
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

/**
 * Pago: al regresar de la pasarela, pide al servidor que sincronice la
 * transacción con Wompi y devuelve el estado del pago y del pedido.
 */
export async function sincronizarPago(transaccionId: string): Promise<ResultadoPago> {
  return leer<ResultadoPago>(
    await fetch(`/api/pagos/${encodeURIComponent(transaccionId)}/sincronizar`, {
      method: "POST",
    }),
  );
}

/**
 * El detalle de un pedido (productos, medio de pago, entrega) para la pantalla
 * de resultado del pago. El id sale de `sincronizarPago`.
 */
export async function verPedido(pedidoId: string): Promise<Pedido> {
  return leer<Pedido>(await fetch(`/api/pedidos/${encodeURIComponent(pedidoId)}`));
}

/**
 * Paga desde "Mis pedidos" un pedido que quedó pendiente. El servidor verifica
 * con la sesión que sea del acudiente; devuelve el widget de Wompi (o la URL de
 * la pasarela simulada).
 */
export async function cancelarPedido(pedidoId: string): Promise<Pedido> {
  return leer<Pedido>(
    await fetch(`/api/pedidos/${encodeURIComponent(pedidoId)}/cancelar`, { method: "POST" }),
  );
}

/** Cancela una solicitud (un trabajo) del acudiente. ADR 0031. */
export async function cancelarSolicitud(trabajoId: string): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/solicitudes/${encodeURIComponent(trabajoId)}/cancelar`, { method: "POST" }),
  );
}

/** Cancela una lista subida que todavía no tiene kit. ADR 0031. */
export async function cancelarListaSubida(tareaId: string): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/solicitudes/listas/${encodeURIComponent(tareaId)}/cancelar`, {
      method: "POST",
    }),
  );
}

/** Borra los datos del titular (Ley 1581). La cookie se borra en el servidor. */
export async function suprimirMisDatos(confirmacion: string): Promise<ResultadoSupresion> {
  return leer<ResultadoSupresion>(
    await fetch("/api/cuenta/supresion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmacion }),
    }),
  );
}

/** Retira la autorizacion de tratamiento sin borrar la cuenta. */
export async function revocarConsentimientos(): Promise<{ revocados: number }> {
  return leer<{ revocados: number }>(
    await fetch("/api/cuenta/consentimientos/revocar", { method: "POST" }),
  );
}

/** Quita a un hijo de la cuenta (cierra el vínculo; no borra datos). */
export async function quitarHijo(matriculaId: string): Promise<void> {
  await leer<unknown>(
    await fetch(`/api/cuenta/matriculas/${encodeURIComponent(matriculaId)}`, { method: "DELETE" }),
  );
}

/** Cambia a un hijo de colegio o de grado, conservando su apodo. */
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

/**
 * Sugiere un (colegio, grado) al backlog del administrador cuando aún no es
 * aliado. El PDF que el acudiente subió viaja como semilla de onboarding; la
 * única traza al acudiente es `contacto_referencia` —correo y celular nunca
 * salen del navegador por aquí—.
 */
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

/**
 * Sube el PDF de cada hijo para que se importe como una versión PENDIENTE de su
 * (colegio, grado). NO crea un trabajo: el acudiente espera la verificación de
 * un administrador. El contacto viaja para que Identidad lo registre una vez;
 * su correo y celular nunca se guardan en catálogo —solo baja el
 * `contacto_referencia` (un id) para poder avisarle cuando aprueben la lista—.
 */
export async function subirListas(
  hijos: HijoSubida[],
  archivos: { referencia: string; archivo: File }[],
  contacto?: Contacto,
  preferencias?: Preferencias,
): Promise<SubidaListas> {
  const forma = new FormData();
  forma.append("hijos", JSON.stringify(hijos));
  if (contacto) forma.append("contacto", JSON.stringify(contacto));
  // El paso 3 es del hogar: las preferencias viajan una vez y quedan con cada
  // versión, para que el kit que se arme al aprobar use lo que el padre pidió.
  if (preferencias) forma.append("preferencias", JSON.stringify(preferencias));
  for (const { referencia, archivo } of archivos) {
    forma.append("archivo", archivo, archivo.name);
    forma.append("referencia", referencia);
  }
  return leer<SubidaListas>(await fetch("/api/listas/subir", { method: "POST", body: forma }));
}

/**
 * Da de alta al acudiente y sus hijos en el camino "soy nuevo usuario". Habla
 * con el Route Handler local, no con el backend: correo, clave y celular no
 * salen del navegador hacia otro origen. La clave viaja una sola vez aqui y
 * nunca vuelve al cliente.
 */
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

/**
 * Entra con correo y clave: `/api/sesion` pone la cookie httpOnly. Lo usa
 * `/empezar` cuando el registro creó la cuenta pero su login dio 429 (H-R-01):
 * al reintentar no se vuelve a registrar, solo se entra.
 */
export async function iniciarSesion(credenciales: { correo: string; clave: string }): Promise<void> {
  await leer<unknown>(
    await fetch("/api/sesion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credenciales),
    }),
  );
}

/**
 * Guarda en la cuenta del acudiente autenticado las matrículas de sus hijos
 * NUEVOS (camino "ya tengo cuenta"). Habla con el Route Handler local, que pone
 * el Bearer desde la cookie httpOnly: el token nunca toca el navegador. Es
 * idempotente en el backend, así que reintentar es inocuo.
 */
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

/**
 * Sondea hasta que el trabajo termine.
 *
 * Con intervalo creciente y no fijo: el pipeline tarda minutos, y preguntar
 * cada segundo durante tres minutos son ciento ochenta peticiones para saber
 * lo mismo. Empieza rapido porque los primeros segundos es cuando el
 * acudiente esta mirando la pantalla.
 */
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
        // Un 404 no se arregla esperando; una caida momentanea si. Un 429
        // tampoco se reintenta solo: seguir preguntando gasta el cupo que lo
        // levanta, y la persona ya ve cuanto esperar. Un 401 (el kit es de una
        // cuenta con clave y no hay sesion, o caduco) tampoco: la pantalla manda
        // a ingresar en vez de dejar el spinner para siempre.
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
