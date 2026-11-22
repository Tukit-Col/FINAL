import type { LineaPedido } from "@tukit/contrato";

export interface ProductoAgrupado {
  clave: string;
  nombre: string;
  cantidad: number;
  precioUnitario: number;
  subtotal: number;
}

export function agruparLineas(lineas: readonly LineaPedido[]): ProductoAgrupado[] {
  const agrupados = new Map<string, ProductoAgrupado>();
  for (const l of lineas) {
    const clave = `${l.sku}@${l.precio_unitario}`;
    const previo = agrupados.get(clave);
    if (previo) {
      previo.cantidad += l.cantidad;
      previo.subtotal += l.cantidad * l.precio_unitario;
    } else {
      agrupados.set(clave, {
        clave,
        nombre: l.nombre,
        cantidad: l.cantidad,
        precioUnitario: l.precio_unitario,
        subtotal: l.cantidad * l.precio_unitario,
      });
    }
  }
  return [...agrupados.values()];
}

const ZONA = "America/Bogota";

export function fechaHoraBogota(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: ZONA,
  });
}

export function diaBogota(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: ZONA,
  });
}

export function fechaCortaBogota(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: ZONA,
  });
}
