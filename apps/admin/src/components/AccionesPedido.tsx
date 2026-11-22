// Los botones del detalle de un pedido: uno por transición que el back-office puede hacer.
//
// Decisiones:
// - La matriz de transiciones vive en `lib/logistica.ts`, espejo de la de Comercio.
// - Los pasos simples van directo porque se deshacen con el siguiente; despachar e incidencia abren un
//   formulario porque Comercio exige datos; cancelar pide confirmación en dos pasos porque es terminal y
//   marca el pago para reembolso.
// - La validación la hace Comercio: aquí solo se pinta su mensaje y se marca el `campo` culpable, para
//   no tener dos reglas que se desalineen.

"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type {
  EstadoPedido,
  SolicitudAvanceAdmin,
  TipoIncidencia,
} from "@tukit/contrato";
import { ETIQUETA_TIPO_INCIDENCIA, TIPOS_INCIDENCIA } from "@tukit/contrato";
import { avanzarPedido, FalloApi, reconciliarPago } from "@/lib/api-navegador";
import {
  accionesDisponibles,
  etiquetaResultadoReconciliacion,
  fechaEstimadaIso,
  motivoSinAcciones,
  type AccionLogistica,
} from "@/lib/logistica";
import BannerAcceso, { type NotaVisible } from "./BannerAcceso";
import SelectorFase from "./SelectorFase";
import styles from "./AccionesPedido.module.css";

interface Props {
  pedidoId: string;
  estado: EstadoPedido;
  urlIngresar?: string;
}

interface Fallo {
  mensaje: string;
  campo: string | null;
  estado: number;
}

export default function AccionesPedido({
  pedidoId,
  estado,
  urlIngresar,
}: Props) {
  const router = useRouter();
  const [abierta, setAbierta] = useState<AccionLogistica | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const [nota, setNota] = useState<NotaVisible | null>(null);

  const acciones = accionesDisponibles(estado);

  async function avanzar(cuerpo: SolicitudAvanceAdmin): Promise<void> {
    setFallo(null);
    setEnviando(true);
    try {
      await avanzarPedido(pedidoId, cuerpo);
      setAbierta(null);
      router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        const campo =
          typeof causa.detalle.campo === "string" ? causa.detalle.campo : null;
        setFallo({ mensaje: causa.message, campo, estado: causa.estado });
        if (causa.estado === 409) router.refresh();
      } else {
        setFallo({
          mensaje: "No pudimos mover el pedido. Intenta de nuevo.",
          campo: null,
          estado: 0,
        });
      }
    } finally {
      setEnviando(false);
    }
  }

  async function reconciliar(): Promise<void> {
    setFallo(null);
    setNota(null);
    setEnviando(true);
    try {
      const r = await reconciliarPago(pedidoId);
      setNota({
        tono: r.resultado === "pagado" ? "ok" : "aviso",
        mensaje: etiquetaResultadoReconciliacion(r.resultado),
      });
      if (r.resultado === "pagado") router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        const sinActivar = causa.estado === 404 || causa.estado === 405;
        setFallo({
          mensaje: sinActivar
            ? "Esta acción se activa al reiniciar el servicio de comercio."
            : causa.message,
          campo: null,
          estado: sinActivar ? 0 : causa.estado,
        });
      } else {
        setFallo({
          mensaje: "No pudimos consultar el pago. Intenta de nuevo.",
          campo: null,
          estado: 0,
        });
      }
    } finally {
      setEnviando(false);
    }
  }

  function abrir(accion: AccionLogistica): void {
    setFallo(null);
    setNota(null);
    if (accion.forma === "simple") {
      void avanzar({ destino: accion.destino });
    } else {
      setAbierta(accion);
    }
  }

  const motivo = motivoSinAcciones(estado);
  const banner = (
    <BannerAcceso
      fallo={fallo}
      nota={nota}
      urlIngresar={urlIngresar}
      onCerrar={() => {
        setFallo(null);
        setNota(null);
      }}
    />
  );

  if (motivo) {
    return (
      <section className={styles.acciones} aria-labelledby="acciones-titulo">
        {banner}
        <h2 id="acciones-titulo">{motivo.titulo}</h2>
        <p className={styles.motivo}>{motivo.detalle}</p>
        {motivo.accion === "reconciliar" ? (
          <div className={styles.botonera}>
            <button
              type="button"
              className={styles.principal}
              disabled={enviando}
              onClick={() => void reconciliar()}
            >
              {enviando ? "Consultando a Wompi…" : "Reconciliar con Wompi"}
            </button>
          </div>
        ) : null}
      </section>
    );
  }

  const invalido = (campo: string) =>
    fallo?.campo === campo ? true : undefined;

  return (
    <section className={styles.acciones} aria-labelledby="acciones-titulo">
      {banner}
      <h2 id="acciones-titulo">Siguiente paso</h2>

      {abierta === null ? (
        <>
          <div className={styles.botonera}>
            {acciones.map((accion, i) => (
              <button
                key={accion.destino}
                type="button"
                className={
                  accion.forma === "cancelar"
                    ? styles.peligro
                    : i === 0
                      ? styles.principal
                      : styles.secundario
                }
                disabled={enviando}
                onClick={() => abrir(accion)}
              >
                {accion.etiqueta}
              </button>
            ))}
          </div>
          <SelectorFase
            key={estado}
            pedidoId={pedidoId}
            estado={estado}
            deshabilitado={enviando}
            onAvanzar={abrir}
          />
        </>
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
    </section>
  );
}

interface PropsFormulario {
  enviando: boolean;
  onCancelar: () => void;
  onEnviar: (cuerpo: SolicitudAvanceAdmin) => Promise<void>;
}

interface PropsConCampos extends PropsFormulario {
  invalido: (campo: string) => true | undefined;
}

function FormDespacho({
  enviando,
  invalido,
  onCancelar,
  onEnviar,
}: PropsConCampos) {
  const [modo, setModo] = useState<"propio" | "transportadora">("propio");
  const [nombre, setNombre] = useState("");
  const [celular, setCelular] = useState("");
  const [transportadora, setTransportadora] = useState("");
  const [guia, setGuia] = useState("");
  const [dia, setDia] = useState("");

  function enviar(evento: FormEvent<HTMLFormElement>): void {
    evento.preventDefault();
    const entrega = fechaEstimadaIso(dia);
    void onEnviar({
      destino: "despachado",
      ...(modo === "propio"
        ? { repartidor_nombre: nombre, repartidor_celular: celular }
        : { transportadora, guia }),
      ...(entrega ? { entrega_estimada: entrega } : {}),
    });
  }

  return (
    <form className={styles.formulario} onSubmit={enviar}>
      <h3>Despachar</h3>
      <fieldset className={styles.modos}>
        <legend>Cómo sale</legend>
        <label>
          <input
            type="radio"
            name="modo-despacho"
            checked={modo === "propio"}
            onChange={() => setModo("propio")}
          />
          Reparto propio
        </label>
        <label>
          <input
            type="radio"
            name="modo-despacho"
            checked={modo === "transportadora"}
            onChange={() => setModo("transportadora")}
          />
          Transportadora
        </label>
      </fieldset>

      {modo === "propio" ? (
        <>
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
        </>
      ) : (
        <>
          <div className={styles.campo}>
            <label htmlFor="transportadora">Transportadora</label>
            <input
              id="transportadora"
              required
              maxLength={128}
              autoComplete="off"
              placeholder="Servientrega, Coordinadora…"
              value={transportadora}
              onChange={(e) => setTransportadora(e.target.value)}
              aria-invalid={invalido("transportadora")}
            />
          </div>
          <div className={styles.campo}>
            <label htmlFor="guia">Número de guía</label>
            <input
              id="guia"
              required
              maxLength={128}
              autoComplete="off"
              value={guia}
              onChange={(e) => setGuia(e.target.value)}
              aria-invalid={invalido("guia")}
            />
          </div>
        </>
      )}

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
        <button
          type="button"
          className={styles.plano}
          disabled={enviando}
          onClick={onCancelar}
        >
          Volver
        </button>
      </div>
    </form>
  );
}

function FormIncidencia({
  enviando,
  invalido,
  onCancelar,
  onEnviar,
}: PropsConCampos) {
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
      <p className={styles.ayuda}>
        Al acudiente le llega un aviso genérico; el tipo y la nota no salen de
        aquí.
      </p>
      <div className={styles.botonera}>
        <button type="submit" className={styles.principal} disabled={enviando}>
          Reportar
        </button>
        <button
          type="button"
          className={styles.plano}
          disabled={enviando}
          onClick={onCancelar}
        >
          Volver
        </button>
      </div>
    </form>
  );
}

function ConfirmarCancelacion({
  enviando,
  onCancelar,
  onEnviar,
}: PropsFormulario) {
  const [nota, setNota] = useState("");

  return (
    <div className={styles.formulario}>
      <h3>¿Cancelar el pedido?</h3>
      <p>
        Es definitivo: el pedido queda cancelado y su pago marcado para
        reembolso (el reembolso en Wompi se hace aparte). Al acudiente no le
        llega aviso; contáctalo tú.
      </p>
      <div className={styles.campo}>
        <label htmlFor="cancelar-nota">
          Motivo (opcional, queda en el historial)
        </label>
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
            void onEnviar({
              destino: "cancelado",
              ...(nota.trim() ? { nota: nota.trim() } : {}),
            })
          }
        >
          Sí, cancelar
        </button>
        <button
          type="button"
          className={styles.plano}
          disabled={enviando}
          onClick={onCancelar}
        >
          No, volver
        </button>
      </div>
    </div>
  );
}
