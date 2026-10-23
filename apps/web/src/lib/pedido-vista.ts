// Lo que la pantalla de un pedido muestra y se puede probar sin React: los
// productos agrupados y las fechas en la hora de Bogota. Las reglas del pedido
// (en que paso va, si vencio) NO viven aqui: llegan hechas de Comercio en la
// `linea_de_tiempo`.

import type { LineaPedido } from "@tukit/contrato";

export interface ProductoAgrupado {
  clave: string;
  nombre: string;
  cantidad: number;
  precioUnitario: number;
  subtotal: number;
}

// Un kit repite el mismo producto por hijo: se agrupan por sku y precio para
// que la lista diga "x 3" y no lo mismo tres veces. El precio entra en la
// clave porque es el congelado de cada linea: dos precios no se suman en uno.
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

// Siempre en la hora de Bogota, aunque el servidor corra en UTC: el render no
// depende de la zona de la maquina.
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
