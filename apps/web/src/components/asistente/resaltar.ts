// El asistente señala en la pagina del kit los renglones que esta proponiendo cambiar.
// No toca React: marca el <li> del renglon (`idAnclaLinea`) con `data-asistente` y el CSS
// del kit lo ilumina. Si un `router.refresh()` vuelve a montar un renglon, se vuelve a marcar.

import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
import { idAnclaLinea } from "@/lib/kit-vista";

const ATRIBUTO = "data-asistente";

/** Ilumina los renglones de `itemIds` y apaga los demas. Devuelve la funcion que los apaga. */
export function iluminarRenglones(itemIds: readonly string[]): () => void {
  const ids = new Set(itemIds.map(idAnclaLinea));
  const aplicar = () => {
    document.querySelectorAll(`[${ATRIBUTO}]`).forEach((el) => {
      if (!ids.has(el.id)) el.removeAttribute(ATRIBUTO);
    });
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el && !el.hasAttribute(ATRIBUTO)) el.setAttribute(ATRIBUTO, "propone");
    });
  };
  aplicar();
  if (ids.size === 0) return () => {};
  const observador = new MutationObserver(aplicar);
  observador.observe(document.body, { childList: true, subtree: true });
  return () => {
    observador.disconnect();
    document.querySelectorAll(`[${ATRIBUTO}]`).forEach((el) => el.removeAttribute(ATRIBUTO));
  };
}

/** Lleva la pagina al renglon y lo hace destellar una vez. */
export function irARenglon(itemId: string): void {
  const el = document.getElementById(idAnclaLinea(itemId));
  if (!el) return;
  el.scrollIntoView({ behavior: prefiereMenosMovimiento() ? "auto" : "smooth", block: "center" });
  el.setAttribute("data-asistente-foco", "");
  window.setTimeout(() => el.removeAttribute("data-asistente-foco"), 1600);
}
