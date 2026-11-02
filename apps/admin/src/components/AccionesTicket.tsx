"use client";

// Lo que el operador hace en un ticket: responder al acudiente, moverlo de
// estado y ligarlo a un pedido. Las reglas (transiciones, texto vacio o largo,
// ticket cerrado) las decide operacion; aqui solo se pinta su mensaje y se
// marca el `campo` culpable, para no tener dos reglas que se desalineen. La
// tabla de transiciones del contrato solo decide que botones se ofrecen.

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { EstadoCaso } from "@tukit/contrato";
import { LONGITUD_MAXIMA_RESPUESTA, TRANSICIONES_CASO } from "@tukit/contrato";
import {
  FalloApi,
  cambiarEstadoTicket,
  responderTicket,
  vincularPedidoTicket,
} from "@/lib/api-navegador";
import { ETIQUETA_ESTADO_TICKET } from "@/lib/tickets";
import styles from "./AccionesTicket.module.css";

interface Props {
  casoId: string;
  estado: EstadoCaso;
  pedidoId: string | null;
  // Sin titular resuelto la respuesta se guarda pero no hay a quien avisar.
  puedeAvisar: boolean;
}

interface Fallo {
  mensaje: string;
  campo: string | null;
}

export default function AccionesTicket({ casoId, estado, pedidoId, puedeAvisar }: Props) {
  const router = useRouter();
  const [texto, setTexto] = useState("");
  const [pedido, setPedido] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const destinos = TRANSICIONES_CASO[estado];
  const cerrado = estado === "cerrado";

  async function ejecutar(accion: () => Promise<unknown>, exito: string, despues?: () => void): Promise<void> {
    setFallo(null);
    setAviso(null);
    setEnviando(true);
    try {
      await accion();
      setAviso(exito);
      despues?.();
      router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        const campo = typeof causa.detalle.campo === "string" ? causa.detalle.campo : null;
        setFallo({ mensaje: causa.message, campo });
        // 409: otro operador lo movio; el refresco trae el estado real.
        if (causa.estado === 409) router.refresh();
      } else {
        setFallo({ mensaje: "No pudimos completar la acción. Intenta de nuevo.", campo: null });
      }
    } finally {
      setEnviando(false);
    }
  }

  function responder(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    void ejecutar(
      () => responderTicket(casoId, texto),
      puedeAvisar ? "Respuesta guardada. Le avisamos al acudiente." : "Respuesta guardada. No hay a quién avisar: el caso no tiene titular.",
      () => setTexto(""),
    );
  }

  function vincular(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    void ejecutar(() => vincularPedidoTicket(casoId, pedido.trim()), "Pedido vinculado.", () => setPedido(""));
  }

  const invalido = (campo: string) => (fallo?.campo === campo ? true : undefined);

  return (
    <section className={styles.acciones} aria-labelledby="acciones-ticket-titulo">
      <h2 id="acciones-ticket-titulo">Gestionar</h2>

      {cerrado ? (
        <p className={styles.ayuda}>El ticket está cerrado: ya no admite respuestas ni cambios.</p>
      ) : (
        <form className={styles.formulario} onSubmit={responder}>
          <div className={styles.campo}>
            <label htmlFor="respuesta">Respuesta al acudiente</label>
            <textarea
              id="respuesta"
              rows={4}
              required
              maxLength={LONGITUD_MAXIMA_RESPUESTA}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              aria-invalid={invalido("texto")}
              aria-describedby="respuesta-ayuda"
            />
            <span id="respuesta-ayuda" className={styles.ayuda}>
              {texto.length}/{LONGITUD_MAXIMA_RESPUESTA}. Queda en la historia del ticket y al acudiente le llega un
              aviso; el texto se lee dentro de Tukit, no sale por correo ni WhatsApp.
              {puedeAvisar ? "" : " Este caso no tiene titular: se guarda sin aviso."}
            </span>
          </div>
          <div className={styles.botonera}>
            <button type="submit" className={styles.principal} disabled={enviando || texto.trim() === ""}>
              Responder
            </button>
          </div>
        </form>
      )}

      {destinos.length > 0 ? (
        <div className={styles.fila}>
          <span className={styles.etiqueta}>Pasar a</span>
          <div className={styles.botonera}>
            {destinos.map((destino) => (
              <button
                key={destino}
                type="button"
                className={styles.secundario}
                disabled={enviando}
                onClick={() =>
                  void ejecutar(() => cambiarEstadoTicket(casoId, destino), `Ticket: ${ETIQUETA_ESTADO_TICKET[destino]}.`)
                }
              >
                {ETIQUETA_ESTADO_TICKET[destino]}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {pedidoId === null && !cerrado ? (
        <form className={styles.fila} onSubmit={vincular}>
          <label className={styles.etiqueta} htmlFor="pedido-vinculo">
            Vincular pedido
          </label>
          <input
            id="pedido-vinculo"
            value={pedido}
            onChange={(e) => setPedido(e.target.value)}
            placeholder="Id completo del pedido"
            autoComplete="off"
            aria-invalid={invalido("pedido_id")}
          />
          <button type="submit" className={styles.secundario} disabled={enviando || pedido.trim() === ""}>
            Vincular
          </button>
        </form>
      ) : null}

      {fallo ? (
        <p className={styles.error} role="alert">
          {fallo.mensaje}
        </p>
      ) : null}
      {aviso ? (
        <p className={styles.exito} role="status">
          {aviso}
        </p>
      ) : null}
    </section>
  );
}
