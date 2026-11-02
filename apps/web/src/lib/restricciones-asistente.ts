// Lo que el asistente de /empezar (S4, `PanelEmpezar`) deja al confirmar, traducido
// a los campos del formulario clasico. Funcion pura: el formulario la llama al
// recibir el evento `tukit:asistente-restricciones` o al leer sessionStorage con
// la misma clave, y el acudiente sigue viendo y editando todo antes de enviar.
//
// Del payload solo se usan personajes, tope y prioridad. `pesos` y
// `disposicion_sobreprecio` no se copian: el formulario manda los de la
// prioridad elegida (`PRIORIDADES`), asi que lo que el acudiente ve en pantalla
// es exactamente lo que viaja.

export const CLAVE_RESTRICCIONES = "tukit:asistente-restricciones";

export type PrioridadFormulario = "precio" | "equilibrio" | "calidad";

const PRIORIDADES: readonly PrioridadFormulario[] = ["precio", "equilibrio", "calidad"];

export interface CambiosDelAsistente {
  // Lista separada por comas, el formato del campo `personajes` de cada hijo.
  personajes: string | null;
  prioridad: PrioridadFormulario | null;
  // Solo digitos, como el campo `presupuesto`; "" si no hay tope.
  presupuesto: string;
}

// El payload llega del navegador (evento o sessionStorage): se valida campo a
// campo y lo que no cuadra se ignora. `null` si no hay nada utilizable.
export function cambiosDelAsistente(crudo: unknown): CambiosDelAsistente | null {
  if (!crudo || typeof crudo !== "object") return null;
  const p = crudo as Record<string, unknown>;

  const personajes = Array.isArray(p.personajes)
    ? [
        ...new Set(
          p.personajes
            .filter((x): x is string => typeof x === "string")
            .map((x) => x.trim())
            .filter(Boolean),
        ),
      ]
    : [];

  const tope =
    typeof p.presupuesto_por_hijo === "number" &&
    Number.isFinite(p.presupuesto_por_hijo) &&
    p.presupuesto_por_hijo > 0
      ? Math.round(p.presupuesto_por_hijo)
      : null;

  let prioridad = PRIORIDADES.includes(p.prioridad as PrioridadFormulario)
    ? (p.prioridad as PrioridadFormulario)
    : null;
  // El tope solo existe en el punto medio (`conTope` exige "equilibrio"): si el
  // acudiente le dio una cifra al asistente, esa es la opcion que la respeta.
  if (tope !== null) prioridad = "equilibrio";

  if (personajes.length === 0 && prioridad === null && tope === null) return null;
  return {
    personajes: personajes.length > 0 ? personajes.join(", ") : null,
    prioridad,
    presupuesto: tope !== null ? String(tope) : "",
  };
}

// A que hijos se les ponen los personajes: solo a los que aun no tienen, para no
// pisar lo que el acudiente ya escribio a mano.
export function aplicarPersonajes<H extends { personajes: string }>(
  hijos: readonly H[],
  personajes: string | null,
): H[] {
  if (!personajes) return [...hijos];
  return hijos.map((h) => (h.personajes.trim() ? h : { ...h, personajes }));
}

// sessionStorage puede traer cualquier cosa (o estar bloqueado): nunca lanza.
export function leerRestriccionesGuardadas(almacen: Pick<Storage, "getItem"> | undefined): unknown {
  try {
    const texto = almacen?.getItem(CLAVE_RESTRICCIONES);
    return texto ? JSON.parse(texto) : null;
  } catch {
    return null;
  }
}
