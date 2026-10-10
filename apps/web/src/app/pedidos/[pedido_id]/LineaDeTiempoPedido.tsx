// La linea de tiempo del pedido, vertical. Comercio decide en que paso va, que
// fechas hay y si hubo un desvio (`linea_de_tiempo`); aqui solo se pinta. Las
// fechas son las que Comercio tiene: un paso alcanzado sin fecha lo dice, no
// se inventa una.

import { AlertTriangle, Check, XCircle } from "lucide-react";
import {
  ETIQUETA_PASO_PEDIDO,
  ETIQUETA_TIPO_INCIDENCIA,
  type LineaDeTiempoPedido as Linea,
  type SituacionPaso,
  type TipoIncidencia,
} from "@tukit/contrato";
import AccionesPedido from "@/app/dashboard/AccionesPedido";
import { diaBogota, fechaHoraBogota } from "@/lib/pedido-vista";
import styles from "./PaginaPedido.module.css";

const CLASE_PASO: Record<SituacionPaso, string> = {
  hecho: styles.pasoHecho,
  actual: styles.pasoActual,
  futuro: styles.pasoFuturo,
};

const PARA_LECTORES: Record<SituacionPaso, string> = {
  hecho: "Completado",
  actual: "Paso actual",
  futuro: "Pendiente",
};

// `tipo_incidencia` es texto en el contrato: uno nuevo de Comercio que aun no
// tiene etiqueta se nombra en generico, no con su clave tecnica.
function nombreIncidencia(tipo: string | null): string {
  return (tipo && ETIQUETA_TIPO_INCIDENCIA[tipo as TipoIncidencia]) || "Otro inconveniente";
}

export default function LineaDeTiempoPedido({
  linea,
  pedidoId,
  trabajoId,
}: {
  linea: Linea;
  pedidoId: string;
  trabajoId: string | null;
}) {
  const { especial, pago_pendiente: pendiente } = linea;
  const entregado = linea.pasos.some((p) => p.paso === "entregado" && p.estado !== "futuro");
  const mostrarEstimada = linea.entrega_estimada && !entregado && especial?.tipo !== "cancelado";

  return (
    <section className={styles.tarjeta} aria-labelledby="seguimiento-titulo">
      <h2 id="seguimiento-titulo" className={styles.subtitulo}>
        Seguimiento
      </h2>

      {especial?.tipo === "incidencia" && (
        <div className={`${styles.desvio} ${styles.desvioIncidencia}`}>
          <AlertTriangle size={20} aria-hidden className={styles.desvioIcono} />
          <p>
            <strong>Tuvimos un inconveniente: {nombreIncidencia(especial.tipo_incidencia).toLowerCase()}.</strong>
            {especial.fecha && (
              <>
                {" "}
                <time dateTime={especial.fecha}>{fechaHoraBogota(especial.fecha)}</time>.
              </>
            )}{" "}
            Te contactaremos para resolverlo.
          </p>
        </div>
      )}
      {especial?.tipo === "cancelado" && (
        <div className={`${styles.desvio} ${styles.desvioCancelado}`}>
          <XCircle size={20} aria-hidden className={styles.desvioIcono} />
          <p>
            <strong>Este pedido fue cancelado.</strong>
            {especial.fecha && (
              <>
                {" "}
                <time dateTime={especial.fecha}>{fechaHoraBogota(especial.fecha)}</time>.
              </>
            )}
          </p>
        </div>
      )}

      <ol className={styles.linea}>
        {linea.pasos.map((p, i) => (
          <li
            key={p.paso}
            className={`${styles.paso} ${CLASE_PASO[p.estado]}`}
            aria-current={p.estado === "actual" ? "step" : undefined}
          >
            <span className={styles.pasoMarca} aria-hidden>
              {p.estado === "hecho" ? <Check size={16} strokeWidth={3} /> : i + 1}
            </span>
            <span className={styles.pasoTexto}>
              <span className={styles.pasoNombre}>
                {ETIQUETA_PASO_PEDIDO[p.paso]}
                <span className={styles.paraLectores}> ({PARA_LECTORES[p.estado]})</span>
              </span>
              {p.fecha ? (
                <time dateTime={p.fecha} className={styles.pasoFecha}>
                  {fechaHoraBogota(p.fecha)}
                </time>
              ) : p.estado !== "futuro" ? (
                <span className={styles.pasoFecha}>Sin fecha registrada</span>
              ) : null}
              {p.paso === "despachado" && p.repartidor_nombre && (
                <span className={styles.pasoDetalle}>Lo lleva {p.repartidor_nombre}</span>
              )}
            </span>
          </li>
        ))}
      </ol>

      {mostrarEstimada && (
        <p className={styles.estimada}>
          Entrega estimada: <strong>{diaBogota(linea.entrega_estimada!)}</strong>
        </p>
      )}

      {pendiente && (
        <div className={styles.pendiente}>
          {!pendiente.vencido && (
            <p className={styles.tenue}>
              Puedes pagarlo hasta el{" "}
              <time dateTime={pendiente.vence_en}>{fechaHoraBogota(pendiente.vence_en)}</time>.
            </p>
          )}
          <AccionesPedido pedidoId={pedidoId} trabajoId={trabajoId} vencido={pendiente.vencido} />
        </div>
      )}
    </section>
  );
}
