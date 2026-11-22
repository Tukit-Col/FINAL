"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import type {
  DestinoDeLote,
  EstadoPedido,
  RespuestaLote,
} from "@tukit/contrato";
import { avanzarEnLote, FalloApi } from "@/lib/api-navegador";
import {
  codigoCorto,
  destinoComunDeLote,
  rutaSinActivar,
  resumenDeLote,
} from "@/lib/logistica";
import BannerAcceso, { type FalloVisible } from "./BannerAcceso";
import styles from "./AvanceEnLote.module.css";

const MAX_LOTE = 50;

const ETIQUETA_DESTINO: Record<DestinoDeLote, string> = {
  en_preparacion: "preparación",
  en_reparto: "reparto",
  entregado: "entregado",
};

interface Visible {
  pedido_id: string;
  estado: EstadoPedido;
}

interface Contexto {
  visibles: readonly Visible[];
  elegidos: ReadonlySet<string>;
  alternar: (id: string) => void;
  alternarTodos: () => void;
  limpiar: (ids?: readonly string[]) => void;
}

const Seleccion = createContext<Contexto | null>(null);

function useSeleccion(): Contexto {
  const c = useContext(Seleccion);
  if (!c)
    throw new Error("Las casillas de lote van dentro de <ProveedorLote>.");
  return c;
}

export function ProveedorLote({
  visibles,
  children,
}: {
  visibles: readonly Visible[];
  children: ReactNode;
}) {
  const [elegidos, setElegidos] = useState<ReadonlySet<string>>(new Set());
  const valor = useMemo<Contexto>(
    () => ({
      visibles,
      elegidos,
      alternar: (id) =>
        setElegidos((previo) => {
          const sig = new Set(previo);
          if (!sig.delete(id)) sig.add(id);
          return sig;
        }),
      alternarTodos: () =>
        setElegidos((previo) => {
          const todos =
            visibles.length > 0 &&
            visibles.every((v) => previo.has(v.pedido_id));
          return todos ? new Set() : new Set(visibles.map((v) => v.pedido_id));
        }),
      limpiar: (ids) =>
        setElegidos((previo) => {
          if (!ids) return new Set();
          const sig = new Set(previo);
          for (const id of ids) sig.delete(id);
          return sig;
        }),
    }),
    [visibles, elegidos],
  );
  return <Seleccion.Provider value={valor}>{children}</Seleccion.Provider>;
}

export function CasillaPedido({ pedidoId }: { pedidoId: string }) {
  const { elegidos, alternar } = useSeleccion();
  return (
    <input
      type="checkbox"
      className={styles.casilla}
      checked={elegidos.has(pedidoId)}
      onChange={() => alternar(pedidoId)}
      aria-label={`Seleccionar el pedido ${codigoCorto(pedidoId)}`}
    />
  );
}

export function CasillaTodos() {
  const { visibles, elegidos, alternarTodos } = useSeleccion();
  const todos =
    visibles.length > 0 && visibles.every((v) => elegidos.has(v.pedido_id));
  return (
    <input
      type="checkbox"
      className={styles.casilla}
      checked={todos}
      onChange={alternarTodos}
      aria-label="Seleccionar los pedidos visibles"
    />
  );
}

export function BarraLote({ urlIngresar }: { urlIngresar?: string }) {
  const router = useRouter();
  const { visibles, elegidos, limpiar } = useSeleccion();
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState<FalloVisible | null>(null);
  const [resultado, setResultado] = useState<RespuestaLote | null>(null);

  const seleccion = visibles.filter((v) => elegidos.has(v.pedido_id));
  const destino = destinoComunDeLote(seleccion) as DestinoDeLote | null;
  const motivo =
    seleccion.length > MAX_LOTE
      ? `Máximo ${MAX_LOTE} pedidos por lote.`
      : destino === null
        ? "Elige pedidos en el mismo estado, y en uno que se mueva sin datos (los de despacho, incidencia o cancelación van de a uno)."
        : null;

  async function ejecutar(): Promise<void> {
    if (!destino) return;
    setEnviando(true);
    setFallo(null);
    try {
      const r = await avanzarEnLote({
        pedido_ids: seleccion.map((s) => s.pedido_id),
        destino,
      });
      setResultado(r);
      setConfirmando(false);
      limpiar(r.avanzados);
      router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        setFallo({
          estado: rutaSinActivar(causa.estado) ? 0 : causa.estado,
          mensaje: rutaSinActivar(causa.estado)
            ? "El avance en lote se activa al reiniciar el servicio de comercio."
            : causa.message,
        });
      } else {
        setFallo({
          estado: 0,
          mensaje: "No pudimos mover el lote. Intenta de nuevo.",
        });
      }
    } finally {
      setEnviando(false);
    }
  }

  if (seleccion.length === 0 && !resultado && !fallo) return null;

  return (
    <div className={styles.barra} role="region" aria-label="Avance en lote">
      <BannerAcceso
        fallo={fallo}
        urlIngresar={urlIngresar}
        onCerrar={() => setFallo(null)}
      />

      {resultado ? (
        <div className={styles.resultado} role="status">
          <strong>{resumenDeLote(resultado)}</strong>
          {resultado.fallidos.length > 0 ? (
            <ul>
              {resultado.fallidos.map((f) => (
                <li key={f.pedido_id}>
                  <code>{codigoCorto(f.pedido_id)}</code> {f.mensaje}
                </li>
              ))}
            </ul>
          ) : null}
          <button
            type="button"
            className={styles.plano}
            onClick={() => setResultado(null)}
          >
            Cerrar
          </button>
        </div>
      ) : null}

      {seleccion.length > 0 ? (
        <div className={styles.fila}>
          <span className={styles.conteo}>
            {seleccion.length}{" "}
            {seleccion.length === 1 ? "seleccionado" : "seleccionados"}
          </span>
          {confirmando && destino ? (
            <>
              <span>
                ¿Pasar {seleccion.length} a {ETIQUETA_DESTINO[destino]}? Cada
                uno queda en su historial y avisa al acudiente.
              </span>
              <button
                type="button"
                className={styles.principal}
                disabled={enviando}
                onClick={() => void ejecutar()}
              >
                {enviando ? "Moviendo…" : "Sí, pasar"}
              </button>
              <button
                type="button"
                className={styles.plano}
                disabled={enviando}
                onClick={() => setConfirmando(false)}
              >
                Volver
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className={styles.principal}
                disabled={motivo !== null}
                onClick={() => setConfirmando(true)}
              >
                {destino
                  ? `Pasar ${seleccion.length} a ${ETIQUETA_DESTINO[destino]}`
                  : "Pasar en lote"}
              </button>
              <button
                type="button"
                className={styles.plano}
                onClick={() => limpiar()}
              >
                Quitar selección
              </button>
              {motivo ? <span className={styles.motivo}>{motivo}</span> : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
