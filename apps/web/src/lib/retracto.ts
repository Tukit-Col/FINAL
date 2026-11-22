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

export function fechaLarga(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "America/Bogota",
  });
}

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
