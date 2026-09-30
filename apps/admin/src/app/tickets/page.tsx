// `/tickets` — la bandeja de casos y PQRS (CABLEADO vía contrato extendido).
//
// Consume `origenDeDatos().casos()`, la superficie de lectura de `operacion`.
// Cuando `operacion` aún no publica casos, la lectura vuelve vacía y la pantalla
// muestra su estado vacío. `cliente-http.ts` ya pega contra `/v1/operacion/*`.
//
// Server Component, mismo patrón que la Cola.

import Link from "next/link";
import { LifeBuoy, AlarmClock, CheckCircle2 } from "lucide-react";
import type { Caso, Prioridad } from "@tukit/contrato";
import {
  casoActivo,
  ETIQUETA_CATEGORIA_CASO,
  ETIQUETA_ESTADO_CASO,
  ETIQUETA_PRIORIDAD,
  ORDEN_PRIORIDAD,
} from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { formatearFecha } from "@/lib/formato";
import Revelar from "@/components/Revelar";
import styles from "./Tickets.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaTickets() {
  const { resumen, casos } = await origenDeDatos().casos();

  // Lo activo primero; dentro de lo activo, lo más urgente arriba. Lo resuelto
  // y cerrado baja al final como historial.
  const ordenados = [...casos].sort((a, b) => {
    const activoA = casoActivo(a) ? 0 : 1;
    const activoB = casoActivo(b) ? 0 : 1;
    return (
      activoA - activoB ||
      ORDEN_PRIORIDAD[a.prioridad] - ORDEN_PRIORIDAD[b.prioridad] ||
      (a.abierto_en < b.abierto_en ? 1 : -1)
    );
  });

  const tarjetas = [
    {
      etiqueta: "Abiertos",
      valor: resumen.abiertos,
      pista: "Casos sin resolver",
      Icono: LifeBuoy,
      tono: resumen.abiertos > 0 ? "info" : "ok",
    },
    {
      etiqueta: "Urgentes",
      valor: resumen.urgentes,
      pista: "Con reloj legal o dinero bloqueado",
      Icono: AlarmClock,
      tono: resumen.urgentes > 0 ? "aviso" : "ok",
    },
    {
      etiqueta: "Resueltos",
      valor: resumen.resueltos_semana,
      pista: "Cerrados favorablemente",
      Icono: CheckCircle2,
      tono: "ok",
    },
  ] as const;

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Tickets</h1>
          <p className={styles.bajada}>
            PQRS y casos de <code>operacion</code>. Cada falla del flujo abre un caso; las
            peticiones de los acudientes entran por aquí. Lo urgente tiene un reloj legal (Ley
            1755), así que se entra por lo de arriba.
          </p>
        </div>
      </header>

      <Revelar>
        <section className={styles.tarjetas} aria-label="Resumen de casos">
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
            No hay casos abiertos. Un caso aparece cuando el flujo falla (pago, stock, lectura de
            lista) o cuando un acudiente abre una PQRS.
          </p>
        </div>
      ) : (
        <div className={styles.marco}>
          <table className={styles.tabla}>
            <thead>
              <tr>
                <th scope="col">Caso</th>
                <th scope="col">Prioridad</th>
                <th scope="col">Categoría</th>
                <th scope="col">Asunto</th>
                <th scope="col">Estado</th>
                <th scope="col">Abierto</th>
                <th scope="col">Vínculo</th>
              </tr>
            </thead>
            <tbody>
              {ordenados.map((caso) => (
                <FilaCaso key={caso.caso_id} caso={caso} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FilaCaso({ caso }: { caso: Caso }) {
  const activo = casoActivo(caso);
  const urgente: Prioridad = "urgente";
  return (
    <tr className={!activo ? styles.filaCerrada : caso.prioridad === urgente ? styles.filaUrgente : ""}>
      <th scope="row" className={styles.identificador}>
        <code>{caso.caso_id}</code>
      </th>
      <td>
        <span className={`${styles.prioridad} ${styles[`prioridad_${caso.prioridad}`]}`}>
          {ETIQUETA_PRIORIDAD[caso.prioridad]}
        </span>
      </td>
      <td>
        <span className={styles.categoria}>{ETIQUETA_CATEGORIA_CASO[caso.categoria]}</span>
      </td>
      <td className={styles.asunto}>{caso.asunto}</td>
      <td>
        <span className={`${styles.estado} ${styles[`estado_${caso.estado}`]}`}>
          {ETIQUETA_ESTADO_CASO[caso.estado]}
        </span>
      </td>
      <td className={styles.fechaExacta}>{formatearFecha(caso.abierto_en)}</td>
      <td className={styles.vinculo}>
        {caso.trabajo_id ? (
          <Link href={`/trabajos/${caso.trabajo_id}`} className={styles.enlace}>
            <code>{caso.trabajo_id.slice(0, 8)}</code>
          </Link>
        ) : (
          <span className={styles.tenue}>—</span>
        )}
      </td>
    </tr>
  );
}
