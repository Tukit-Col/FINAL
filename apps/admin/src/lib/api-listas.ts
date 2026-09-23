// El lado del navegador de las escrituras de P4: revisión de listas, edición del
// perfil de un colegio y "editar" (nueva versión) de un grado.
//
// Igual que `api-navegador.ts` y `api-catalogo.ts`: habla solo con los Route
// Handlers de esta misma app (`/api/listas/**`, `/api/colegios/**`), nunca con
// el backend. La URL del backend y el token se quedan en el servidor. Módulo
// propio del slice para no pisar `api-navegador.ts`.

import type { ColegioDetalle, ColegioEditable, ErrorApi, ItemListaEditable } from "@tukit/contrato";

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
    const error = (leido ?? {}) as ErrorApi & Record<string, unknown>;
    // El mensaje que se muestra es el del backend, no uno inventado aquí: es el
    // único que sabe por qué rechazó (lista_ya_revisada, concepto_no_existe…).
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

/** PATCH — editar un renglón de la revisión (concepto, modo de adquisición…). */
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

/** POST — dar de alta un renglón que el modelo no itemizó. Devuelve su item_id. */
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

/** POST — aprobar y publicar la versión. Deja el par (colegio, grado) disponible. */
export function cerrarLista(versionId: string): Promise<void> {
  return pedir<void>(`/api/listas/${id(versionId)}/cerrar`, { method: "POST" });
}

/** POST — armar la vista previa de los tres kits de una versión curada. Devuelve
 *  el `trabajo_id` de un trabajo de preview (no el del acudiente) que la pantalla
 *  lee luego con `trabajoAdmin`. No aprueba nada: preview y publicar son distintos.
 *  El destino (colegio, grado, año) va en el cuerpo: es lo que la revisión ya trae. */
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

/** PATCH — editar la identidad/marca de un colegio. Devuelve el detalle ya actualizado. */
export function editarColegio(colegioId: string, cambios: ColegioEditable): Promise<ColegioDetalle> {
  return pedir<ColegioDetalle>(`/api/colegios/${id(colegioId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cambios),
  });
}

/** POST — clonar la lista vigente en una versión nueva sin revisar. Devuelve su version_id. */
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
