import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
import { idAnclaLinea } from "@/lib/kit-vista";

const ATRIBUTO = "data-asistente";

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

export function irARenglon(itemId: string): void {
  const el = document.getElementById(idAnclaLinea(itemId));
  if (!el) return;
  el.scrollIntoView({ behavior: prefiereMenosMovimiento() ? "auto" : "smooth", block: "center" });
  el.setAttribute("data-asistente-foco", "");
  window.setTimeout(() => el.removeAttribute("data-asistente-foco"), 1600);
}
