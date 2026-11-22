"use client";

import { useId, useRef, useState } from "react";
import type { EstadoPedido, VistaPreviaPedido } from "@tukit/contrato";
import { FalloApi, vistaPrevia } from "@/lib/api-navegador";
import {
  destinosParaSelector,
  ETIQUETA_PASO_ACUDIENTE,
  rutaSinActivar,
  textoAviso,
  type AccionLogistica,
} from "@/lib/logistica";
import { formatearFecha } from "@/lib/formato";
import styles from "./SelectorFase.module.css";

interface Props {
  pedidoId: string;
  estado: EstadoPedido;
  deshabilitado: boolean;
  onAvanzar: (accion: AccionLogistica) => void;
}

type Carga =
  | { tipo: "nada" }
  | { tipo: "cargando" }
  | { tipo: "lista"; previa: VistaPreviaPedido }
  | { tipo: "sin_activar" }
  | { tipo: "error"; mensaje: string };

export default function SelectorFase({
  pedidoId,
  estado,
  deshabilitado,
  onAvanzar,
}: Props) {
  const opciones = destinosParaSelector(estado);
  const [elegido, setElegido] = useState<string>("");
  const [carga, setCarga] = useState<Carga>({ tipo: "nada" });
  const solicitud = useRef(0);
  const idSelect = useId();

  async function cargar(destino: string): Promise<void> {
    const mia = ++solicitud.current;
    setCarga({ tipo: "cargando" });
    try {
      const previa = await vistaPrevia(pedidoId, destino);
      if (mia === solicitud.current) setCarga({ tipo: "lista", previa });
    } catch (causa) {
      if (mia !== solicitud.current) return;
      if (causa instanceof FalloApi && rutaSinActivar(causa.estado)) {
        setCarga({ tipo: "sin_activar" });
      } else {
        setCarga({
          tipo: "error",
          mensaje:
            causa instanceof FalloApi
              ? causa.message
              : "No pudimos cargar la vista previa.",
        });
      }
    }
  }

  if (opciones.length === 0) return null;
  const accion = opciones.find((o) => o.destino === elegido) ?? null;

  return (
    <div className={styles.selector}>
      <div className={styles.campo}>
        <label htmlFor={idSelect}>Mover a la fase</label>
        <select
          id={idSelect}
          value={elegido}
          disabled={deshabilitado}
          onChange={(e) => {
            const destino = e.target.value;
            setElegido(destino);
            if (destino) void cargar(destino);
            else setCarga({ tipo: "nada" });
          }}
        >
          <option value="">Elige la fase…</option>
          {opciones.map((o) => (
            <option key={o.destino} value={o.destino}>
              {o.etiqueta}
            </option>
          ))}
        </select>
      </div>

      {elegido ? (
        <div className={styles.previa} aria-live="polite">
          <h3>Lo que verá el acudiente</h3>
          {carga.tipo === "cargando" ? (
            <p className={styles.tenue}>Cargando la vista previa…</p>
          ) : null}
          {carga.tipo === "sin_activar" ? (
            <p className={styles.tenue}>
              La vista previa se activa al reiniciar el servicio. Puedes
              confirmar igual: el paso funciona sin ella.
            </p>
          ) : null}
          {carga.tipo === "error" ? (
            <p className={styles.errorLinea}>
              {carga.mensaje}{" "}
              <button
                type="button"
                className={styles.reintentar}
                onClick={() => void cargar(elegido)}
              >
                Reintentar
              </button>
            </p>
          ) : null}
          {carga.tipo === "lista" ? <Previa previa={carga.previa} /> : null}

          <div className={styles.botonera}>
            <button
              type="button"
              className={styles.confirmar}
              disabled={
                deshabilitado ||
                carga.tipo === "cargando" ||
                (carga.tipo === "lista" && !carga.previa.legal)
              }
              onClick={() => accion && onAvanzar(accion)}
            >
              {accion?.forma === "simple"
                ? `Confirmar: ${accion.etiqueta}`
                : accion
                  ? `Continuar: ${accion.etiqueta}`
                  : "Confirmar"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Previa({ previa }: { previa: VistaPreviaPedido }) {
  if (!previa.legal || !previa.despues) {
    return (
      <p className={styles.errorLinea}>
        Desde el estado actual no se puede pasar a esa fase.
      </p>
    );
  }
  const linea = previa.despues;
  return (
    <>
      <ol className={styles.pasos}>
        {linea.pasos.map((p) => (
          <li
            key={p.paso}
            className={styles[`paso_${p.estado}`]}
            aria-current={p.estado === "actual" ? "step" : undefined}
          >
            <span className={styles.marca} aria-hidden="true" />
            <span className={styles.nombre}>
              {ETIQUETA_PASO_ACUDIENTE[p.paso] ?? p.paso}
            </span>
            <span className={styles.fecha}>
              {p.fecha
                ? formatearFecha(p.fecha)
                : p.estado === "futuro"
                  ? ""
                  : "—"}
            </span>
          </li>
        ))}
      </ol>
      {linea.especial ? (
        <p className={styles.especial}>
          {linea.especial.tipo === "incidencia"
            ? "El acudiente verá una incidencia en su pedido."
            : "El pedido figura cancelado."}
        </p>
      ) : null}
      <p className={styles.aviso}>{textoAviso(previa.aviso)}</p>
    </>
  );
}
