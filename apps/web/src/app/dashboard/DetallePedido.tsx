"use client";

// El detalle de un pedido en "Mis pedidos": la línea de tiempo, lo que pagó, a
// dónde va y el derecho de retracto (Ley 1480 de 2011, art. 47) con su fecha
// límite. Pedir el retracto pide confirmación y muestra el resultado; el plazo
// y el dueño los verifica Comercio, esto solo lo dice con palabras claras.

import Link from "next/link";
import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronDown, Undo2 } from "lucide-react";
import {
  ETIQUETA_ESTADO_PEDIDO,
  formatearPesos,
  type Pedido,
  type RetractoSolicitado,
} from "@tukit/contrato";
import { FalloApi, pedirRetracto } from "@/lib/api-navegador";
import { fechaYHora, textoDeRetracto } from "@/lib/retracto";
import styles from "./Dashboard.module.css";

export default function DetallePedido({ pedido }: { pedido: Pedido }) {
  const router = useRouter();
  const idPanel = useId();
  const [abierto, setAbierto] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState<RetractoSolicitado | null>(null);

  const pasos = pedido.seguimiento ?? [];
  const retracto = textoDeRetracto(pedido.retracto);
  const envio = pedido.envio;

  async function pedir() {
    setEnviando(true);
    setError(null);
    try {
      setHecho(await pedirRetracto(pedido.pedido_id, motivo.trim()));
      setConfirmando(false);
      router.refresh();
    } catch (causa) {
      setError(
        causa instanceof FalloApi ? causa.message : "No pudimos registrar tu retracto. Intenta de nuevo.",
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className={styles.detallePedido}>
      <button
        type="button"
        className={styles.verDetalle}
        aria-expanded={abierto}
        aria-controls={idPanel}
        onClick={() => setAbierto((a) => !a)}
      >
        <ChevronDown size={14} aria-hidden="true" className={abierto ? styles.giro : undefined} />
        {abierto ? "Ocultar detalle" : "Ver seguimiento y detalle"}
      </button>

      {abierto && (
        <div id={idPanel} className={styles.panelPedido}>
          <ol className={styles.lineaTiempo} aria-label="Seguimiento del pedido">
            {pasos.map((paso, i) => (
              <li
                key={`${paso.estado}-${i}`}
                className={i === pasos.length - 1 ? styles.pasoActual : styles.pasoHecho}
              >
                <span className={styles.pasoPunto} aria-hidden="true">
                  <Check size={11} strokeWidth={3.5} />
                </span>
                <span className={styles.pasoTexto}>
                  <strong>{paso.etiqueta}</strong>
                  <span>{fechaYHora(paso.en)}</span>
                </span>
              </li>
            ))}
          </ol>

          <dl className={styles.datosPedido}>
            <div>
              <dt>Total pagado</dt>
              <dd className="cifra">{formatearPesos(pedido.total)}</dd>
            </div>
            <div>
              <dt>Estado</dt>
              <dd>{ETIQUETA_ESTADO_PEDIDO[pedido.estado]}</dd>
            </div>
            {envio && (
              <div>
                <dt>Entrega en</dt>
                <dd>
                  {envio.direccion}, {envio.ciudad}
                  {envio.repartidor_nombre ? ` · lo lleva ${envio.repartidor_nombre}` : ""}
                </dd>
              </div>
            )}
          </dl>

          <ul className={styles.productosPedido}>
            {pedido.lineas.map((l) => (
              <li key={l.sku}>
                <span>
                  {l.cantidad} × {l.nombre}
                </span>
                <span className="cifra">{formatearPesos(l.cantidad * l.precio_unitario)}</span>
              </li>
            ))}
          </ul>

          {/* ---- Retracto ---- */}
          {pedido.retracto && (retracto.frase || hecho) && (
            <div className={styles.cajaRetracto}>
              <h3>
                <Undo2 size={15} aria-hidden="true" /> Derecho de retracto
              </h3>
              {hecho ? (
                <p role="status">
                  Listo, registramos tu retracto por {formatearPesos(hecho.monto)}.{" "}
                  {hecho.cancelado
                    ? "El pedido quedó cancelado y te devolvemos el pago."
                    : "Te escribiremos con los pasos para devolver los productos y tu reembolso."}
                </p>
              ) : (
                <p>{retracto.frase}</p>
              )}
              {pedido.retracto.solicitado_en && !hecho && (
                <p className={styles.notaRetracto}>
                  Lo pediste el {fechaYHora(pedido.retracto.solicitado_en)}.
                </p>
              )}

              {retracto.puedePedir && !hecho && !confirmando && (
                <button type="button" className={styles.btnCancelar} onClick={() => setConfirmando(true)}>
                  Quiero retractarme
                </button>
              )}

              {confirmando && !hecho && (
                <div className={styles.confirmaRetracto}>
                  <label>
                    ¿Nos cuentas por qué? (opcional)
                    <textarea
                      value={motivo}
                      maxLength={500}
                      rows={2}
                      onChange={(e) => setMotivo(e.target.value)}
                    />
                  </label>
                  <p className={styles.notaRetracto}>
                    Vas a pedir la devolución de {formatearPesos(pedido.total)}. Esta acción queda
                    registrada y no se puede deshacer.
                  </p>
                  <div className={styles.accionesFila}>
                    <button type="button" className={styles.btnPagar} onClick={pedir} disabled={enviando}>
                      {enviando ? "Registrando…" : "Confirmar retracto"}
                    </button>
                    <button
                      type="button"
                      className={styles.btnCancelar}
                      onClick={() => setConfirmando(false)}
                      disabled={enviando}
                    >
                      Mejor no
                    </button>
                  </div>
                </div>
              )}
              {error && (
                <p className={styles.errorPedido} role="alert">
                  {error}
                </p>
              )}
              <p className={styles.notaRetracto}>
                Más en{" "}
                <Link href="/legal/retracto">derecho de retracto y garantía</Link>.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
