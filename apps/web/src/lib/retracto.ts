// Lo que el acudiente lee sobre su derecho de retracto (Ley 1480 de 2011, art. 47).
//
// El plazo y la decision de si puede o no los toma Comercio; aqui solo se dicen
// en palabras llanas, separado del componente para probarlo sin pintar nada.

import type { EstadoRetracto } from "@tukit/contrato";

const MENSAJE_SIN_RETRACTO: Record<NonNullable<EstadoRetracto["razon"]>, string> = {
  ya_solicitado: "Ya pediste el retracto de este pedido. Te escribiremos con los pasos.",
  plazo_vencido: "El plazo de 5 días hábiles desde la entrega ya terminó.",
  sin_pagar: "Este pedido no se pagó, así que no hay nada que devolver.",
  cancelado: "Este pedido está cancelado.",
  sin_fecha_de_entrega:
    "No tenemos la fecha de entrega. Escríbenos desde Mis casos y lo resolvemos.",
  estado_no_permite: "Este pedido no admite retracto en su estado actual.",
};

/** "viernes 6 de marzo de 2026", en la hora de Colombia. */
export function fechaLarga(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "America/Bogota",
  });
}

/** "6 mar 2026, 3:05 p. m." para un paso de la linea de tiempo. */
export function fechaYHora(iso: string): string {
  return new Date(iso).toLocaleString("es-CO", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Bogota",
  });
}

/**
 * La frase sobre el retracto de un pedido y si se ofrece el boton. Mientras el
 * pedido no llega no hay fecha limite: el plazo empieza a correr con la entrega.
 */
export function textoDeRetracto(retracto: EstadoRetracto | undefined): {
  frase: string;
  puedePedir: boolean;
} {
  if (!retracto) return { frase: "", puedePedir: false };
  if (!retracto.puede) {
    const base = retracto.razon ? MENSAJE_SIN_RETRACTO[retracto.razon] : "";
    return { frase: base, puedePedir: false };
  }
  if (retracto.antes_de_entrega) {
    return {
      frase:
        "Todavía no te ha llegado. Puedes retractarte ahora y te devolvemos el pago. Cuando te llegue, tendrás 5 días hábiles para hacerlo.",
      puedePedir: true,
    };
  }
  return {
    frase: retracto.vence_en
      ? `Tienes hasta el ${fechaLarga(retracto.vence_en)} (5 días hábiles desde la entrega) para retractarte.`
      : "Tienes 5 días hábiles desde la entrega para retractarte.",
    puedePedir: true,
  };
}
