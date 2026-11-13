// Lo que el panel muestra: solo lo que pide una acción, cada cosa con su enlace.
//
// Pura (solo tipos del contrato) para probarse con `node --test`. Un widget con
// cantidad 0 no existe; si todo está en cero, la página dice "Todo al día" una
// sola vez. Una fuente que no se pudo leer se reporta en `caidos` sin esconder
// las demás. Un resumen de un servicio que aún no se reinició (sin los conteos
// nuevos) cuenta como 0 y se anota en `sinActivar`, para no decir "todo al día"
// con datos que faltan.

import type {
  ColaAdmin,
  ResumenComercio,
  ResumenOperacion,
} from "@tukit/contrato";

export type FuentePanel = "pedidos" | "casos" | "cola";

export interface WidgetPanel {
  id: string;
  titulo: string;
  cantidad: number;
  urgencia: "alta" | "media";
  ayuda: string;
  enlace: string;
  textoEnlace: string;
}

export interface EntradaPanel {
  pedidos: ResumenComercio | null;
  casos: ResumenOperacion | null;
  cola: ColaAdmin | null;
}

export interface SalidaPanel {
  widgets: WidgetPanel[];
  caidos: FuentePanel[];
  /** Conteos que el servicio todavía no entrega (se activan al reiniciarlo). */
  sinActivar: FuentePanel[];
}

export function construirWidgets(entrada: EntradaPanel): SalidaPanel {
  const caidos: FuentePanel[] = [];
  const sinActivar: FuentePanel[] = [];
  const todos: WidgetPanel[] = [];

  const agregar = (w: WidgetPanel) => {
    if (w.cantidad > 0) todos.push(w);
  };

  if (!entrada.pedidos) {
    caidos.push("pedidos");
  } else {
    const alertas = entrada.pedidos.alertas;
    if (!alertas) sinActivar.push("pedidos");
    agregar({
      id: "pagado_sin_avanzar",
      titulo: "Pagados sin avanzar",
      cantidad: alertas?.pagado_sin_avanzar ?? 0,
      urgencia: "alta",
      ayuda:
        "Pagaron hace más de 24 h y nadie los movió. Es el reclamo más probable.",
      enlace: "/logistica?alerta=pagado_sin_avanzar",
      textoEnlace: "Avanzar pedidos",
    });
    agregar({
      id: "pago_atascado",
      titulo: "Pagos atascados",
      cantidad: alertas?.pago_atascado ?? 0,
      urgencia: "alta",
      ayuda: "Pago iniciado hace más de 30 min sin confirmación de Wompi.",
      enlace: "/logistica?alerta=pago_atascado",
      textoEnlace: "Reconciliar con Wompi",
    });
    agregar({
      id: "incidencias",
      titulo: "Incidencias abiertas",
      // Sin el conteo nuevo, el de siempre (`por_estado`) da la misma cifra.
      cantidad:
        alertas?.incidencia_abierta ??
        entrada.pedidos.por_estado?.incidencia ??
        0,
      urgencia: "alta",
      ayuda: "Entregas detenidas que esperan una decisión.",
      enlace: "/logistica?estado=incidencia",
      textoEnlace: "Reprogramar o cancelar",
    });
  }

  if (!entrada.casos) {
    caidos.push("casos");
  } else {
    if (
      entrada.casos.vencidos === undefined ||
      entrada.casos.sin_asignar === undefined
    )
      sinActivar.push("casos");
    agregar({
      id: "tickets_vencidos",
      titulo: "Tickets vencidos",
      cantidad: entrada.casos.vencidos ?? 0,
      urgencia: "alta",
      ayuda: "El plazo de respuesta (Ley 1755) ya se cumplió.",
      enlace: "/tickets?vencidos=1",
      textoEnlace: "Responder",
    });
    agregar({
      id: "tickets_sin_asignar",
      titulo: "Tickets sin asignar",
      cantidad: entrada.casos.sin_asignar ?? 0,
      urgencia: "media",
      ayuda: "Nadie es dueño de estos casos.",
      enlace: "/tickets?asignado=ninguno",
      textoEnlace: "Asignarme",
    });
  }

  if (!entrada.cola) {
    caidos.push("cola");
  } else {
    const entradas = entrada.cola.entradas;
    const enEspera = entradas.filter((e) => e.estado === "espera_revision");
    const lineas = enEspera.reduce((t, e) => t + e.lineas_pendientes, 0);
    agregar({
      id: "listas_en_revision",
      titulo: "Listas esperando revisión",
      cantidad: enEspera.length,
      urgencia: "media",
      ayuda: `${lineas} ${lineas === 1 ? "línea" : "líneas"} por validar antes de publicar los kits.`,
      enlace: "/cola",
      textoEnlace: "Revisar",
    });
    agregar({
      id: "procesos_fallidos",
      titulo: "Procesos fallidos",
      cantidad: entradas.filter((e) => e.estado === "fallido").length,
      urgencia: "media",
      ayuda: "Una lista que no se procesó no llega sola al catálogo.",
      enlace: "/cola",
      textoEnlace: "Reintentar o descartar",
    });
  }

  const rango = { alta: 0, media: 1 } as const;
  const widgets = todos
    .map((w, i) => ({ w, i }))
    .sort(
      (a, b) =>
        rango[a.w.urgencia] - rango[b.w.urgencia] ||
        b.w.cantidad - a.w.cantidad ||
        a.i - b.i,
    )
    .map(({ w }) => w);
  return { widgets, caidos, sinActivar };
}
