// La regla pura del campo de dirección del checkout (ADR 0049), separada del
// componente para probarla sin navegador.

// Editar a mano la dirección la desliga del lugar que se eligió (el pin de
// OpenStreetMap). Si venía de uno, la localidad y el pin también se sueltan: los
// derivó el servicio de esa dirección, y el acudiente los vuelve a elegir para la
// que está escribiendo. Sin lugar elegido, solo cambia el texto.
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
  // Solo se tocan las coordenadas si el formulario las lleva.
  return "latitud" in datos ? { ...suelto, latitud: null, longitud: null } : suelto;
}
