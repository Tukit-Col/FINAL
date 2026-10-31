// Qué hijos de la cuenta se precargan en /empezar cuando el acudiente entra por
// "Ya tengo cuenta". Separado del formulario para probarlo sin navegador.
//
// Solo se precarga un hijo que se puede usar tal cual: su colegio tiene la
// lista de ese grado verificada, así que va directo a armar el kit. Uno de un
// colegio sin lista (o de un grado sin verificar) pediría subir el archivo y,
// precargado, dejaba el buscador vacío y el botón bloqueado sin explicar por
// qué. Esos quedan fuera con su motivo, y el formulario lo dice.

// Lo que el formulario deja agregar: precargar más dejaría hijos que no se
// pueden quitar y volver a poner.
export const MAX_HIJOS = 4;

export interface ColegioPrecarga {
  colegio_id: string;
  nombre: string;
  // Los grados con lista verificada.
  grados: string[];
}

export interface MatriculaPrecarga {
  colegio_id: string;
  grado: string;
  apodo: string | null;
}

export interface HijoSinPrecargar {
  // El apodo, o `null` si no tiene.
  nombre: string | null;
  // El nombre del colegio, o `null` si no se conoce (nunca el id).
  colegio: string | null;
  grado: string;
  motivo: "sin_lista" | "tope";
}

export function precargarHijos<M extends MatriculaPrecarga>(
  matriculas: readonly M[],
  colegios: readonly ColegioPrecarga[],
  maximo: number = MAX_HIJOS,
): { precargados: M[]; fuera: HijoSinPrecargar[] } {
  const porId = new Map(colegios.map((c) => [c.colegio_id, c]));
  const precargados: M[] = [];
  const fuera: HijoSinPrecargar[] = [];
  for (const matricula of matriculas) {
    const colegio = porId.get(matricula.colegio_id);
    const usable = colegio?.grados.includes(matricula.grado) ?? false;
    if (usable && precargados.length < maximo) {
      precargados.push(matricula);
      continue;
    }
    fuera.push({
      nombre: matricula.apodo?.trim() || null,
      colegio: colegio?.nombre ?? null,
      grado: matricula.grado,
      motivo: usable ? "tope" : "sin_lista",
    });
  }
  return { precargados, fuera };
}

function quien(hijo: HijoSinPrecargar): string {
  const donde = hijo.colegio ? `${hijo.colegio} · ${hijo.grado}` : null;
  if (hijo.nombre) return donde ? `${hijo.nombre} (${donde})` : hijo.nombre;
  return hijo.colegio ? `tu hijo de ${hijo.grado} (${hijo.colegio})` : `tu hijo de ${hijo.grado}`;
}

function unir(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

// Un aviso por motivo, en palabras de papá y con lo que puede hacer. Con
// `cargados` en el tope, el formulario ya no muestra «Agregar otro hijo»: el
// aviso no puede mandar a un botón que no está.
export function avisosDePrecarga(fuera: readonly HijoSinPrecargar[], cargados = 0): string[] {
  const sinLista = fuera.filter((h) => h.motivo === "sin_lista").map(quien);
  const tope = fuera.filter((h) => h.motivo === "tope").map(quien);
  const avisos: string[] = [];
  if (sinLista.length > 0) {
    avisos.push(
      `No cargamos a ${unir(sinLista)}: su colegio todavía no tiene la lista de ese grado. ` +
        (cargados >= MAX_HIJOS
          ? "Puedes subir su lista y armar su kit en otro pedido."
          : "Si quieres su kit, usa «Agregar otro hijo» y sube la lista."),
    );
  }
  if (tope.length > 0) {
    avisos.push(
      `Un pedido arma hasta ${MAX_HIJOS} hijos, así que dejamos fuera a ${unir(tope)}. ` +
        "Puedes armar su kit en otro pedido.",
    );
  }
  return avisos;
}
