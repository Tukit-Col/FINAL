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

export interface DatosDeEntrega {
  destinatario: string;
  direccion: string;
  indicaciones: string;
  localidad: string;
  departamento: string;
  latitud: number | null;
  longitud: number | null;
  ciudad: string;
}

export function aplicarLugarElegido<
  D extends Pick<DatosDeEntrega, "direccion" | "latitud" | "longitud" | "localidad" | "departamento">,
>(
  datos: D,
  lugar: { direccion: string; latitud?: number; longitud?: number; localidad: string; departamento?: string },
): D {
  return {
    ...datos,
    direccion: lugar.direccion,
    latitud: lugar.latitud ?? null,
    longitud: lugar.longitud ?? null,
    localidad: lugar.localidad,
    departamento: lugar.departamento || datos.departamento,
  };
}

export function entregaDeCheckout(datos: DatosDeEntrega) {
  const { destinatario, direccion, ciudad } = datos;
  const conPin = datos.latitud !== null && datos.longitud !== null;
  const opcionales = {
    indicaciones: datos.indicaciones.trim(),
    localidad: datos.localidad,
    departamento: datos.departamento.trim(),
    latitud: conPin ? datos.latitud : undefined,
    longitud: conPin ? datos.longitud : undefined,
  };
  return {
    destinatario,
    direccion,
    ciudad,
    ...Object.fromEntries(Object.entries(opcionales).filter(([, valor]) => valor)),
  };
}
