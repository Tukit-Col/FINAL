import type {
  ColegioDetalle,
  ColegioEditable,
  ColegioNuevoEditable,
  DatosColegioNuevo,
  ErrorApi,
  ItemListaEditable,
} from "@tukit/contrato";
import { conEspera } from "@tukit/contrato";

export class FalloListas extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
    this.name = "FalloListas";
  }
}

async function pedir<T>(ruta: string, init: RequestInit): Promise<T> {
  const respuesta = await fetch(ruta, init);
  const texto = await respuesta.text();
  const leido: unknown = texto ? JSON.parse(texto) : null;

  if (!respuesta.ok) {
    const error = conEspera(
      respuesta.status,
      (leido ?? {}) as ErrorApi & Record<string, unknown>,
      respuesta.headers.get("Retry-After"),
    );
    throw new FalloListas(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salió mal al guardar el cambio.",
      error,
    );
  }
  return leido as T;
}

const id = encodeURIComponent;

export function editarItemLista(
  versionId: string,
  itemId: string,
  cambios: ItemListaEditable,
): Promise<void> {
  return pedir<void>(`/api/listas/${id(versionId)}/items/${id(itemId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cambios),
  });
}

export function agregarItemLista(
  versionId: string,
  item: ItemListaEditable,
): Promise<{ item_id: string }> {
  return pedir<{ item_id: string }>(`/api/listas/${id(versionId)}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item),
  });
}

export function quitarItemLista(versionId: string, itemId: string): Promise<void> {
  return pedir<void>(`/api/listas/${id(versionId)}/items/${id(itemId)}`, { method: "DELETE" });
}

export function eliminarVersionLista(versionId: string): Promise<void> {
  return pedir<void>(`/api/listas/${id(versionId)}`, { method: "DELETE" });
}

export function cerrarLista(versionId: string): Promise<void> {
  return pedir<void>(`/api/listas/${id(versionId)}/cerrar`, { method: "POST" });
}

export function previsualizarVersion(
  versionId: string,
  destino: { colegio_id: string; grado: string; anio_lectivo: number },
): Promise<{ trabajo_id: string }> {
  return pedir<{ trabajo_id: string }>(`/api/listas/${id(versionId)}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(destino),
  });
}

export function completarColegioDeVersion(
  versionId: string,
  cambios: ColegioNuevoEditable,
): Promise<DatosColegioNuevo> {
  return pedir<DatosColegioNuevo>(`/api/listas/${id(versionId)}/colegio`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cambios),
  });
}

export function editarColegio(colegioId: string, cambios: ColegioEditable): Promise<ColegioDetalle> {
  return pedir<ColegioDetalle>(`/api/colegios/${id(colegioId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cambios),
  });
}

export function nuevaVersion(
  colegioId: string,
  grado: string,
  anioLectivo: number,
): Promise<{ version_id: string }> {
  return pedir<{ version_id: string }>(
    `/api/colegios/${id(colegioId)}/${id(grado)}/nueva-version`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anio_lectivo: anioLectivo }),
    },
  );
}

export function descartarAviso(versionId: string, itemId: string, clave: string): Promise<void> {
  return pedir<void>(`/api/listas/${id(versionId)}/avisos/descartar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: itemId, clave }),
  });
}

export function noComprarRepetido(
  versionId: string,
  itemId: string,
  repiteA: number,
): Promise<{ version_id: string }> {
  return pedir<{ version_id: string }>(`/api/listas/${id(versionId)}/items/${id(itemId)}/no-comprar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repite_a: repiteA }),
  });
}
