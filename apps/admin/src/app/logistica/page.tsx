// `/logistica` — el tablero de pedidos y entregas (CABLEADO vía contrato extendido).
//
// Consume `origenDeDatos().pedidos()`, la superficie de lectura de `comercio`
// (`cliente-http.ts` pega contra `/v1/comercio/*`). Cuando `comercio` aún no
// publica pedidos, la lectura vuelve vacía y la pantalla muestra su estado vacío.
//
// Server Component, mismo patrón que la Cola.

import Link from "next/link";
import { Truck, PackageCheck, CircleDollarSign, TriangleAlert } from "lucide-react";
import type { EstadoPedido, Pedido } from "@tukit/contrato";
import { ETIQUETA_ESTADO_PEDIDO, formatearPesos, pedidoEnCurso } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { formatearFecha } from "@/lib/formato";
import Revelar from "@/components/Revelar";
import styles from "./Logistica.module.css";

export const dynamic = "force-dynamic";

// Orden operativo: primero lo que hay que mover (en curso), después incidencias,
// y al final lo cerrado (entregado/cancelado) como historial.
const PRIORIDAD_ESTADO: Record<EstadoPedido, number> = {
  incidencia: 0,
  pagado: 1,
  en_preparacion: 2,
  despachado: 3,
  en_reparto: 4,
  pendiente_pago: 5,
  entregado: 6,
  cancelado: 7,
};

export default async function PaginaLogistica() {
  const { resumen, pedidos } = await origenDeDatos().pedidos();
  const ordenados = [...pedidos].sort(
    (a, b) => PRIORIDAD_ESTADO[a.estado] - PRIORIDAD_ESTADO[b.estado],
  );

  const tarjetas = [
    {
      etiqueta: "En curso",
      valor: resumen.entregas_pendientes,
      pista: "Pagados y todavía sin entregar",
      Icono: Truck,
      tono: "info",
    },
    {
      etiqueta: "Con incidencia",
      valor: resumen.por_estado.incidencia,
      pista: "Necesitan intervención",
      Icono: TriangleAlert,
      tono: resumen.por_estado.incidencia > 0 ? "aviso" : "ok",
    },
    {
      etiqueta: "Entregados",
      valor: resumen.por_estado.entregado,
      pista: "Ya en el hogar",
      Icono: PackageCheck,
      tono: "ok",
    },
    {
      etiqueta: "Ingresos confirmados",
      valor: formatearPesos(resumen.ingresos_confirmados),
      pista: "Pagos aprobados",
      Icono: CircleDollarSign,
      tono: "ok",
    },
  ] as const;

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Logística</h1>
          <p className={styles.bajada}>
            Pedidos, pagos y entregas. Cada pedido nace de un trabajo publicado; el estado, la
            transportadora y la guía se leen de <code>comercio</code>.
          </p>
        </div>
      </header>

      <Revelar>
        <section className={styles.tarjetas} aria-label="Resumen de logística">
          {tarjetas.map(({ etiqueta, valor, pista, Icono, tono }) => (
            <div
              key={etiqueta}
              className={`${styles.tarjeta} ${tono === "aviso" ? styles.tarjetaAviso : ""}`}
            >
              <span className={styles.tarjetaIcono} aria-hidden="true">
                <Icono size={20} strokeWidth={2.2} />
              </span>
              <span className={`${styles.tarjetaValor} cifra`}>{valor}</span>
              <span className={styles.tarjetaEtiqueta}>{etiqueta}</span>
              <span className={styles.tarjetaPista}>{pista}</span>
            </div>
          ))}
        </section>
      </Revelar>

      {ordenados.length === 0 ? (
        <div className={styles.vacio}>
          <p>
            No hay pedidos todavía. Un pedido aparece cuando un trabajo se aprueba en la cola de
            revisión y arranca la saga de pago.
          </p>
        </div>
      ) : (
        <div className={styles.marco}>
          <table className={styles.tabla}>
            <thead>
              <tr>
                <th scope="col">Pedido</th>
                <th scope="col">Estado</th>
                <th scope="col">Creado</th>
                <th scope="col" className={styles.num}>
                  Hijos
                </th>
                <th scope="col">Colegios</th>
                <th scope="col">Envío</th>
                <th scope="col" className={styles.num}>
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {ordenados.map((pedido) => (
                <FilaPedido key={pedido.pedido_id} pedido={pedido} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FilaPedido({ pedido }: { pedido: Pedido }) {
  const enCurso = pedidoEnCurso(pedido);
  return (
    <tr className={enCurso ? styles.filaCurso : pedido.estado === "incidencia" ? styles.filaIncidencia : ""}>
      <th scope="row" className={styles.identificador}>
        <code>{pedido.pedido_id}</code>
        {pedido.trabajo_id ? (
          <Link href={`/trabajos/${pedido.trabajo_id}`} className={styles.enlaceTrabajo}>
            ver trabajo
          </Link>
        ) : null}
      </th>
      <td>
        <span className={`${styles.estado} ${styles[`estado_${pedido.estado}`]}`}>
          {ETIQUETA_ESTADO_PEDIDO[pedido.estado]}
        </span>
      </td>
      <td className={styles.fechaExacta}>{formatearFecha(pedido.creado_en)}</td>
      <td className={`${styles.num} cifra`}>{pedido.hijos}</td>
      <td className={styles.lista}>{pedido.colegios.join(", ") || "—"}</td>
      <td className={styles.envio}>
        {pedido.envio?.transportadora ? (
          <>
            <span>{pedido.envio.transportadora}</span>
            {pedido.envio.guia ? (
              <code className={styles.guia}>{pedido.envio.guia}</code>
            ) : null}
          </>
        ) : (
          <span className={styles.tenue}>—</span>
        )}
      </td>
      <td className={`${styles.num} cifra ${styles.total}`}>{formatearPesos(pedido.total)}</td>
    </tr>
  );
}
