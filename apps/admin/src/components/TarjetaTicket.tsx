import Link from "next/link";
import type { Caso } from "@tukit/contrato";
import {
  casoActivo,
  ETIQUETA_CATEGORIA_CASO,
  ETIQUETA_PRIORIDAD,
} from "@tukit/contrato";
import {
  claseDePrioridad,
  ETIQUETA_ESTADO_TICKET,
  etiquetaSla,
  textoAsignacion,
} from "@/lib/tickets";
import styles from "./TarjetaTicket.module.css";

export default function TarjetaTicket({
  caso,
  ahora,
  yo,
}: {
  caso: Caso;
  ahora: number;
  yo: string | null;
}) {
  const sla = etiquetaSla(caso, ahora);
  const activo = casoActivo(caso);
  return (
    <li
      className={`${styles.tarjeta} ${styles[claseDePrioridad(caso.prioridad)]} ${activo ? "" : styles.cerrada}`}
    >
      <Link href={`/tickets/${caso.caso_id}`} className={styles.enlace}>
        <div className={styles.cabecera}>
          <span className={styles.prioridad}>
            {ETIQUETA_PRIORIDAD[caso.prioridad]}
          </span>
          <span className={styles.categoria}>
            {ETIQUETA_CATEGORIA_CASO[caso.categoria]}
          </span>
          <code className={styles.codigo}>
            {caso.caso_id.slice(0, 8).toUpperCase()}
          </code>
        </div>
        <p className={styles.asunto}>{caso.asunto}</p>
      </Link>
      <div className={styles.pie}>
        {sla.tono !== "sin" ? (
          <span className={`${styles.sla} ${styles[`sla_${sla.tono}`]}`}>
            {sla.texto}
          </span>
        ) : null}
        <span
          className={
            caso.asignado_a === null && activo ? styles.sinDueno : styles.dueno
          }
        >
          {textoAsignacion(caso.asignado_a, yo)}
        </span>
        <span className={styles.estado}>
          {ETIQUETA_ESTADO_TICKET[caso.estado]}
        </span>
        {caso.pedido_id ? (
          <Link
            href={`/logistica/${caso.pedido_id}`}
            className={styles.vinculo}
          >
            pedido <code>{caso.pedido_id.slice(0, 8).toUpperCase()}</code>
          </Link>
        ) : null}
      </div>
    </li>
  );
}
