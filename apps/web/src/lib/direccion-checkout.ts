export function escribirDireccionAMano<
  D extends {
    direccion: string;
    localidad: string;
    latitud?: number | null;
    longitud?: number | null;
  },
>(datos: D, direccion: string): D {
  const conPin = datos.latitud != null || datos.longitud != null;
  if (!conPin) return { ...datos, direccion };
  const suelto = { ...datos, direccion, localidad: "" };
  return "latitud" in datos ? { ...suelto, latitud: null, longitud: null } : suelto;
}
