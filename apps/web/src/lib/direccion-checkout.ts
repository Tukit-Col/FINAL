// Las reglas puras del campo de dirección del checkout (ADR 0044), separadas
// del componente para probarlas sin navegador ni Google.

// Programar y cancelar la espera; en las pruebas, un reloj a mano.
export interface Reloj {
  programar(fn: () => void, ms: number): unknown;
  cancelar(id: unknown): void;
}

const RELOJ_DEL_NAVEGADOR: Reloj = {
  programar: (fn, ms) => setTimeout(fn, ms),
  cancelar: (id) => clearTimeout(id as ReturnType<typeof setTimeout>),
};

// Los turnos deciden qué respuesta de Google todavía vale. Cada tecla y cada
// elección abren un turno nuevo, y una respuesta solo se aplica si su turno
// sigue siendo el último:
// - lo que el acudiente escribe gana a los detalles de un lugar que eligió
//   antes y que todavía no llegan;
// - elegir cancela la búsqueda que esperaba su turno: si venciera después,
//   abriría una sesión de Google de más y descartaría la selección.
export interface TurnosDireccion {
  // Una tecla. Con `buscar`, la búsqueda sale tras la espera con el turno de
  // esta tecla; sin él (pocas letras, o Google apagado) solo vence lo anterior.
  teclear(buscar?: (turno: number) => void): void;
  // Elegir una sugerencia; devuelve el turno de sus detalles.
  elegir(): number;
  vigente(turno: number): boolean;
  // Al desmontar el campo.
  cerrar(): void;
}

export function crearTurnos(esperaMs: number, reloj: Reloj = RELOJ_DEL_NAVEGADOR): TurnosDireccion {
  let actual = 0;
  let espera: unknown = null;
  const cancelarEspera = () => {
    if (espera !== null) reloj.cancelar(espera);
    espera = null;
  };
  return {
    teclear(buscar) {
      cancelarEspera();
      const turno = ++actual;
      if (!buscar) return;
      espera = reloj.programar(() => {
        espera = null;
        buscar(turno);
      }, esperaMs);
    },
    elegir() {
      cancelarEspera();
      return ++actual;
    },
    vigente: (turno) => turno === actual,
    cerrar: cancelarEspera,
  };
}

// Los errores de Google que no se arreglan reintentando: la API no está
// habilitada, la llave no la permite o no vale. Con ellos el campo pasa a
// manual y vuelve el autocompletado del navegador. Google los rechaza con un
// `MapsRequestError` cuyo `code` es el estado del servicio.
const CODIGOS_DE_PERMISO = new Set(["PERMISSION_DENIED", "REQUEST_DENIED", "UNAUTHENTICATED"]);

export function esRechazoDePermisos(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const codigo = (error as { code?: unknown }).code;
  return typeof codigo === "string" && CODIGOS_DE_PERMISO.has(codigo);
}

// Editar a mano la dirección la desliga del lugar que se eligió (de Google o del
// pin de OpenStreetMap). Si venía de uno, la localidad y el pin también se
// sueltan: los derivó el servicio de esa dirección, y el acudiente los vuelve a
// elegir para la que está escribiendo. Sin lugar elegido, solo cambia el texto.
export function escribirDireccionAMano<
  D extends {
    direccion: string;
    google_place_id: string;
    localidad: string;
    latitud?: number | null;
    longitud?: number | null;
  },
>(datos: D, direccion: string): D {
  const conPin = datos.latitud != null || datos.longitud != null;
  if (!datos.google_place_id && !conPin) return { ...datos, direccion };
  const suelto = { ...datos, direccion, google_place_id: "", localidad: "" };
  // Solo se tocan las coordenadas si el formulario las lleva (el de Google no).
  return "latitud" in datos ? { ...suelto, latitud: null, longitud: null } : suelto;
}
