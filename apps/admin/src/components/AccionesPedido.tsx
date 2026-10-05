"use client";

// Los botones del detalle de un pedido: uno por transicion que el back-office
// puede hacer desde su estado (la matriz vive en `lib/logistica.ts`, espejo de
// la de comercio).
//
// Los pasos simples van directo porque se deshacen con el siguiente (un
// "Salio a reparto" equivocado se corrige con una incidencia). Despachar e
// incidencia abren su formulario porque comercio exige datos (repartidor;
// tipo y nota). Cancelar pide confirmacion en dos pasos: es terminal y marca el
// pago para reembolso. La validacion la hace comercio; aqui solo se pinta su
// mensaje y se marca el `campo` culpable, para no tener dos reglas que se
// desalineen.

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { EstadoPedido, SolicitudAvancePedido, TipoIncidencia } from "@tukit/contrato";
import { ETIQUETA_TIPO_INCIDENCIA, TIPOS_INCIDENCIA } from "@tukit/contrato";
import { avanzarPedido, FalloApi } from "@/lib/api-navegador";
import { accionesDisponibles, fechaEstimadaIso, type AccionLogistica } from "@/lib/logistica";
import styles from "./AccionesPedido.module.css";

interface Props {
  pedidoId: string;
  estado: EstadoPedido;
}

interface Fallo {
  mensaje: string;
  campo: string | null;
}

export default function AccionesPedido({ pedidoId, estado }: Props) {
  const router = useRouter();
  const [abierta, setAbierta] = useState<AccionLogistica | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<Fallo | null>(null);

  const acciones = accionesDisponibles(estado);

  async function avanzar(cuerpo: SolicitudAvancePedido): Promise<void> {
    setFallo(null);
    setEnviando(true);
    try {
      await avanzarPedido(pedidoId, cuerpo);
      setAbierta(null);
      router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        const campo = typeof causa.detalle.campo === "string" ? causa.detalle.campo : null;
        setFallo({ mensaje: causa.message, campo });
        // 409: otro operador lo movio (o la matriz cambio). El refresco trae
        // el estado real y con el los botones que si aplican.
        if (causa.estado === 409) router.refresh();
      } else {
        setFallo({ mensaje: "No pudimos mover el pedido. Intenta de nuevo.", campo: null });
      }
    } finally {
      setEnviando(false);
    }
  }

  function abrir(accion: AccionLogistica): void {
    setFallo(null);
    if (accion.forma === "simple") {
      void avanzar({ destino: accion.destino });
    } else {
      setAbierta(accion);
    }
  }

  if (acciones.length === 0) {
    return (
      <p className={styles.cerrado}>
        Este pedido ya no tiene pasos de logística ({estado === "pendiente_pago" ? "espera el pago" : "está cerrado"}).
      </p>
    );
  }

  const invalido = (campo: string) => (fallo?.campo === campo ? true : undefined);

  return (
    <section className={styles.acciones} aria-labelledby="acciones-titulo">
      <h2 id="acciones-titulo">Siguiente paso</h2>

      {abierta === null ? (
        <div className={styles.botonera}>
          {acciones.map((accion, i) => (
            <button
              key={accion.destino}
              type="button"
              className={
                accion.forma === "cancelar" ? styles.peligro : i === 0 ? styles.principal : styles.secundario
              }
              disabled={enviando}
              onClick={() => abrir(accion)}
            >
              {accion.etiqueta}
            </button>
          ))}
        </div>
      ) : abierta.forma === "despachar" ? (
        <FormDespacho
          enviando={enviando}
          invalido={invalido}
          onCancelar={() => setAbierta(null)}
          onEnviar={avanzar}
        />
      ) : abierta.forma === "incidencia" ? (
        <FormIncidencia
          enviando={enviando}
          invalido={invalido}
          onCancelar={() => setAbierta(null)}
          onEnviar={avanzar}
        />
      ) : (
        <ConfirmarCancelacion
          enviando={enviando}
          onCancelar={() => setAbierta(null)}
          onEnviar={avanzar}
        />
      )}

      {fallo ? (
        <p className={styles.error} role="alert">
          {fallo.mensaje}
        </p>
      ) : null}
    </section>
  );
}

interface PropsFormulario {
  enviando: boolean;
  onCancelar: () => void;
  onEnviar: (cuerpo: SolicitudAvancePedido) => Promise<void>;
}

interface PropsConCampos extends PropsFormulario {
  invalido: (campo: string) => true | undefined;
}

function FormDespacho({ enviando, invalido, onCancelar, onEnviar }: PropsConCampos) {
  const [nombre, setNombre] = useState("");
  const [celular, setCelular] = useState("");
  const [dia, setDia] = useState("");

  function enviar(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    const entrega = fechaEstimadaIso(dia);
    void onEnviar({
      destino: "despachado",
      repartidor_nombre: nombre,
      repartidor_celular: celular,
      ...(entrega ? { entrega_estimada: entrega } : {}),
    });
  }

  return (
    <form className={styles.formulario} onSubmit={enviar}>
      <h3>Despachar con reparto propio</h3>
      <div className={styles.campo}>
        <label htmlFor="repartidor-nombre">Nombre del repartidor</label>
        <input
          id="repartidor-nombre"
          required
          maxLength={128}
          autoComplete="off"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          aria-invalid={invalido("repartidor_nombre")}
        />
      </div>
      <div className={styles.campo}>
        <label htmlFor="repartidor-celular">Celular del repartidor</label>
        <input
          id="repartidor-celular"
          type="tel"
          required
          maxLength={32}
          autoComplete="off"
          value={celular}
          onChange={(e) => setCelular(e.target.value)}
          aria-invalid={invalido("repartidor_celular")}
          aria-describedby="repartidor-celular-ayuda"
        />
        <span id="repartidor-celular-ayuda" className={styles.ayuda}>
          Solo lo ve el equipo interno; al acudiente le llega el nombre.
        </span>
      </div>
      <div className={styles.campo}>
        <label htmlFor="entrega-estimada">Entrega estimada (opcional)</label>
        <input
          id="entrega-estimada"
          type="date"
          value={dia}
          onChange={(e) => setDia(e.target.value)}
          aria-invalid={invalido("entrega_estimada")}
        />
      </div>
      <div className={styles.botonera}>
        <button type="submit" className={styles.principal} disabled={enviando}>
          Despachar y avisar
        </button>
        <button type="button" className={styles.plano} disabled={enviando} onClick={onCancelar}>
          Volver
        </button>
      </div>
    </form>
  );
}

function FormIncidencia({ enviando, invalido, onCancelar, onEnviar }: PropsConCampos) {
  const [tipo, setTipo] = useState<TipoIncidencia | "">("");
  const [nota, setNota] = useState("");

  function enviar(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    void onEnviar({
      destino: "incidencia",
      ...(tipo ? { tipo_incidencia: tipo } : {}),
      ...(nota.trim() ? { nota: nota.trim() } : {}),
    });
  }

  return (
    <form className={styles.formulario} onSubmit={enviar}>
      <h3>Reportar incidencia</h3>
      <div className={styles.campo}>
        <label htmlFor="incidencia-tipo">Qué pasó</label>
        <select
          id="incidencia-tipo"
          required
          value={tipo}
          onChange={(e) => setTipo(e.target.value as TipoIncidencia | "")}
          aria-invalid={invalido("tipo_incidencia")}
        >
          <option value="" disabled>
            Elige una opción
          </option>
          {TIPOS_INCIDENCIA.map((t) => (
            <option key={t} value={t}>
              {ETIQUETA_TIPO_INCIDENCIA[t]}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.campo}>
        <label htmlFor="incidencia-nota">
          Nota interna {tipo === "otro" ? "(obligatoria)" : "(opcional)"}
        </label>
        <textarea
          id="incidencia-nota"
          rows={2}
          maxLength={512}
          required={tipo === "otro"}
          value={nota}
          onChange={(e) => setNota(e.target.value)}
          aria-invalid={invalido("nota")}
        />
      </div>
      <p className={styles.ayuda}>Al acudiente le llega un aviso genérico; el tipo y la nota no salen de aquí.</p>
      <div className={styles.botonera}>
        <button type="submit" className={styles.principal} disabled={enviando}>
          Reportar
        </button>
        <button type="button" className={styles.plano} disabled={enviando} onClick={onCancelar}>
          Volver
        </button>
      </div>
    </form>
  );
}

function ConfirmarCancelacion({ enviando, onCancelar, onEnviar }: PropsFormulario) {
  const [nota, setNota] = useState("");

  return (
    <div className={styles.formulario}>
      <h3>¿Cancelar el pedido?</h3>
      <p>
        Es definitivo: el pedido queda cancelado y su pago marcado para reembolso (el reembolso en
        Wompi se hace aparte). Al acudiente no le llega aviso; contáctalo tú.
      </p>
      <div className={styles.campo}>
        <label htmlFor="cancelar-nota">Motivo (opcional, queda en el historial)</label>
        <textarea
          id="cancelar-nota"
          rows={2}
          maxLength={512}
          value={nota}
          onChange={(e) => setNota(e.target.value)}
        />
      </div>
      <div className={styles.botonera}>
        <button
          type="button"
          className={styles.peligro}
          disabled={enviando}
          onClick={() =>
            void onEnviar({ destino: "cancelado", ...(nota.trim() ? { nota: nota.trim() } : {}) })
          }
        >
          Sí, cancelar
        </button>
        <button type="button" className={styles.plano} disabled={enviando} onClick={onCancelar}>
          No, volver
        </button>
      </div>
    </div>
  );
}
