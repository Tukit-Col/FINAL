// La vista kanban de `/logistica`: una columna por etapa del flujo y un carril
// aparte para incidencia y cancelado. Server Component: recibe los pedidos ya
// filtrados por la pagina; la agrupacion, el orden, el recorte de lo cerrado y
// la accion de cada tarjeta salen de `lib/logistica.ts` (probados con
// `node --test`). Solo el boton de avance es de cliente.
//
// Ley 1581: la tarjeta muestra codigo, colegio, articulos y total. Nunca el
// apodo ni el nombre de un menor (el tablero de comercio tampoco los trae).

import Link from "next/link";
import type { Pedido } from "@tukit/contrato";
import { ETIQUETA_ALERTA_PEDIDO, ETIQUETA_ESTADO_PEDIDO, formatearPesos } from "@tukit/contrato";
import { haceCuanto } from "@/lib/formato";
import {
  agruparPorEtapa,
  articulosDePedido,
  CARRIL_APARTE,
  codigoCorto,
  COLUMNAS_FLUJO,
  fechaDeEtapa,
  hrefEtapaEnTabla,
  type ColumnaTablero,
  type FiltrosLogistica,
} from "@/lib/logistica";
import { nombresDeColegios } from "@/lib/logistica-servidor";
import AvanzarTarjeta from "./AvanzarTarjeta";
import styles from "./TableroPedidos.module.css";

interface Props {
  pedidos: readonly Pedido[];
  filtros: FiltrosLogistica;
  nombresColegio: ReadonlyMap<string, string>;
  urlIngresar: string;
  /** Un solo reloj para todo el tablero, leido por la pagina (como la Cola). */
  ahora: number;
}

export default function TableroPedidos({ pedidos, filtros, nombresColegio, urlIngresar, ahora }: Props) {
  const flujo = agruparPorEtapa(pedidos, COLUMNAS_FLUJO);
  const aparte = agruparPorEtapa(pedidos, CARRIL_APARTE);
  const comun = { filtros, nombresColegio, urlIngresar, ahora };

  return (
    <div className={styles.tablero}>
      <section aria-labelledby="carril-flujo" className={styles.carril}>
        <h2 id="carril-flujo" className={styles.tituloCarril}>
          Flujo del pedido
        </h2>
        {/* Region con foco: en movil se desplaza con el teclado (flechas). */}
        <div className={styles.columnas} role="region" aria-label="Etapas del pedido" tabIndex={0}>
          {flujo.map((columna) => (
            <Columna key={columna.estado} columna={columna} {...comun} />
          ))}
        </div>
      </section>

      <section aria-labelledby="carril-aparte" className={styles.carril}>
        <h2 id="carril-aparte" className={styles.tituloCarril}>
          Fuera del flujo
        </h2>
        <div className={`${styles.columnas} ${styles.columnasAparte}`}>
          {aparte.map((columna) => (
            <Columna key={columna.estado} columna={columna} {...comun} />
          ))}
        </div>
      </section>
    </div>
  );
}

interface PropsColumna {
  columna: ColumnaTablero;
  filtros: FiltrosLogistica;
  nombresColegio: ReadonlyMap<string, string>;
  urlIngresar: string;
  ahora: number;
}

function Columna({ columna, filtros, nombresColegio, urlIngresar, ahora }: PropsColumna) {
  const { estado, total, pedidos, ocultos } = columna;
  const idTitulo = `columna-${estado}`;
  return (
    <section className={`${styles.columna} ${styles[`columna_${estado}`] ?? ""}`} aria-labelledby={idTitulo}>
      <header className={styles.cabeza}>
        <h3 id={idTitulo}>{ETIQUETA_ESTADO_PEDIDO[estado]}</h3>
        <span className={`${styles.cuenta} cifra`} aria-label={`${total} ${total === 1 ? "pedido" : "pedidos"}`}>
          {total}
        </span>
      </header>

      {pedidos.length === 0 ? (
        <p className={styles.vacia}>Sin pedidos</p>
      ) : (
        <ul className={styles.lista} tabIndex={0} aria-label={`Pedidos en ${ETIQUETA_ESTADO_PEDIDO[estado]}`}>
          {pedidos.map((pedido) => (
            <li key={pedido.pedido_id}>
              <Tarjeta pedido={pedido} nombresColegio={nombresColegio} urlIngresar={urlIngresar} ahora={ahora} />
            </li>
          ))}
        </ul>
      )}

      {ocultos > 0 ? (
        <Link href={hrefEtapaEnTabla(filtros, estado)} className={styles.verMas}>
          Ver los {ocultos} restantes en la tabla
        </Link>
      ) : null}
    </section>
  );
}

interface PropsTarjeta {
  pedido: Pedido;
  nombresColegio: ReadonlyMap<string, string>;
  urlIngresar: string;
  ahora: number;
}

function Tarjeta({ pedido, nombresColegio, urlIngresar, ahora }: PropsTarjeta) {
  const codigo = codigoCorto(pedido.pedido_id);
  const alertas = pedido.alertas ?? [];
  const articulos = articulosDePedido(pedido);
  const colegios = nombresDeColegios(pedido.colegios, nombresColegio) || "Sin colegio";
  const entregado = pedido.estado === "entregado" && pedido.envio?.entregado_en;
  return (
    <article className={`${styles.tarjeta} ${alertas.length > 0 ? styles.tarjetaAlerta : ""}`}>
      <div className={styles.fila}>
        <Link href={`/logistica/${pedido.pedido_id}`} className={styles.codigo}>
          <code>{codigo}</code>
          <span className={styles.oculto}> (ver detalle)</span>
        </Link>
        <span className={`${styles.total} cifra`}>{formatearPesos(pedido.total)}</span>
      </div>
      <p className={styles.colegio}>{colegios}</p>
      <p className={styles.meta}>
        <span className="cifra">
          {articulos} {articulos === 1 ? "artículo" : "artículos"}
        </span>
        <span aria-hidden="true"> · </span>
        {/* El tablero no trae la llegada a cada etapa: la antiguedad se cuenta
            desde la entrega (si llego) o desde la creacion del pedido. */}
        <span title={entregado ? "Desde la entrega" : "Desde que se creó el pedido"}>
          {entregado ? "entregado " : "creado "}
          {haceCuanto(fechaDeEtapa(pedido), ahora)}
        </span>
      </p>
      {alertas.length > 0 ? (
        <ul className={styles.alertas} aria-label="Alertas">
          {alertas.map((alerta) => (
            <li key={alerta} className={styles.alerta}>
              {ETIQUETA_ALERTA_PEDIDO[alerta]}
            </li>
          ))}
        </ul>
      ) : null}
      <AvanzarTarjeta pedidoId={pedido.pedido_id} estado={pedido.estado} codigo={codigo} urlIngresar={urlIngresar} />
    </article>
  );
}
