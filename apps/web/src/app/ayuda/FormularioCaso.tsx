"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { CheckCircle2, KeyRound, Send, Ticket } from "lucide-react";
import {
  CATEGORIAS_CASO_ACUDIENTE,
  ETIQUETA_CATEGORIA_CASO,
  type CasoCreado,
  type CategoriaCaso,
} from "@tukit/contrato";
import { crearCaso, FalloApi } from "@/lib/api-navegador";
import { fechaLegible } from "@/lib/panel-cuenta";
import styles from "./Ayuda.module.css";

const PISTA: Partial<Record<CategoriaCaso, string>> = {
  peticion: "Una duda o una solicitud puntual.",
  queja: "Algo en la atención no estuvo bien.",
  reclamo: "Un problema con un pedido o un cobro.",
  sugerencia: "Una idea para mejorar Tukit.",
  pago: "Algo relacionado con un pago.",
  entrega: "Algo relacionado con una entrega.",
};

export default function FormularioCaso({ conSesion }: { conSesion: boolean }) {
  const idCategoria = useId();
  const idAsunto = useId();
  const idDescripcion = useId();
  const idTrabajo = useId();

  const [categoria, setCategoria] = useState<CategoriaCaso>("peticion");
  const [asunto, setAsunto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [trabajoId, setTrabajoId] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [creado, setCreado] = useState<CasoCreado | null>(null);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const caso = await crearCaso({
        categoria,
        asunto,
        descripcion,
        trabajo_id: trabajoId.trim() || null,
      });
      setCreado(caso);
    } catch (causa) {
      setError(
        causa instanceof FalloApi
          ? causa.message
          : "No pudimos enviar tu solicitud. Intenta de nuevo.",
      );
    } finally {
      setEnviando(false);
    }
  }

  if (!conSesion) {
    return (
      <div className={styles.acceso} role="status">
        <span className={styles.accesoIcono} aria-hidden="true">
          <KeyRound size={26} strokeWidth={2.2} />
        </span>
        <div className={styles.accesoTexto}>
          <h3>Ingresa para abrir una solicitud</h3>
          <p>
            Así el caso queda en tu cuenta y puedes seguirlo desde “Mis casos”, sin tener que
            guardar un número.
          </p>
        </div>
        <Link href="/ingresar" className={styles.accesoBoton}>
          Ingresar a mi cuenta
        </Link>
      </div>
    );
  }

  if (creado) {
    return (
      <div className={styles.exito} role="status">
        <span className={styles.exitoIcono} aria-hidden="true">
          <CheckCircle2 size={30} strokeWidth={2.3} />
        </span>
        <h3>Radicamos tu solicitud</h3>
        <p>
          Tu número es{" "}
          <strong className={styles.radicado}>{creado.caso_id}</strong>. Lo ves y le haces
          seguimiento en <Link href="/dashboard#casos">Mis casos</Link>.
        </p>
        {creado.vence_en ? (
          <p className={styles.plazo}>
            Te responderemos a más tardar el <strong>{fechaLegible(creado.vence_en, "long")}</strong>{" "}
            (término de ley para {ETIQUETA_CATEGORIA_CASO[creado.categoria].toLowerCase()}).
          </p>
        ) : (
          <p className={styles.plazo}>
            La tomamos en cuenta. Si necesita respuesta, te escribimos al correo de tu
            cuenta.
          </p>
        )}
        <button
          type="button"
          className={styles.otroBoton}
          onClick={() => {
            setCreado(null);
            setAsunto("");
            setDescripcion("");
            setTrabajoId("");
          }}
        >
          Abrir otra solicitud
        </button>
      </div>
    );
  }

  return (
    <form className={styles.forma} onSubmit={enviar}>
      <div className={styles.campo}>
        <label htmlFor={idCategoria}>Tipo de solicitud</label>
        <select
          id={idCategoria}
          value={categoria}
          onChange={(e) => setCategoria(e.target.value as CategoriaCaso)}
          required
        >
          {CATEGORIAS_CASO_ACUDIENTE.map((c) => (
            <option key={c} value={c}>
              {ETIQUETA_CATEGORIA_CASO[c]}
            </option>
          ))}
        </select>
        {PISTA[categoria] && <p className={styles.pista}>{PISTA[categoria]}</p>}
      </div>

      <div className={styles.campo}>
        <label htmlFor={idAsunto}>Asunto</label>
        <input
          id={idAsunto}
          type="text"
          value={asunto}
          onChange={(e) => setAsunto(e.target.value)}
          placeholder="En una línea, ¿de qué se trata?"
          maxLength={120}
          required
        />
      </div>

      <div className={styles.campo}>
        <label htmlFor={idDescripcion}>Cuéntanos qué pasó</label>
        <textarea
          id={idDescripcion}
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          placeholder="Danos los detalles que creas útiles. Entre más claro, mejor te ayudamos."
          rows={5}
          required
        />
      </div>

      <div className={styles.campo}>
        <label htmlFor={idTrabajo}>
          Número de kit <span className={styles.opcional}>(opcional)</span>
        </label>
        <input
          id={idTrabajo}
          type="text"
          value={trabajoId}
          onChange={(e) => setTrabajoId(e.target.value)}
          placeholder="Si tu duda es sobre un kit, pega su número aquí"
        />
      </div>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <button type="submit" className={styles.enviar} disabled={enviando}>
        <Send size={17} strokeWidth={2.6} aria-hidden="true" />
        {enviando ? "Enviando…" : "Enviar solicitud"}
      </button>

      <p className={styles.notaCanal}>
        <Ticket size={13} strokeWidth={2.4} aria-hidden="true" />
        Tu solicitud entra a la cola de soporte y una persona la atiende.
      </p>
    </form>
  );
}
