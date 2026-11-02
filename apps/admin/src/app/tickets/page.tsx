// `/tickets` — la bandeja de casos y PQRS (CABLEADO vía contrato extendido).
//
// Consume `origenDeDatos().casos()`, la superficie de lectura de `operacion`.
// Cuando `operacion` aún no publica casos, la lectura vuelve vacía y la pantalla
// muestra su estado vacío. `cliente-http.ts` ya pega contra `/v1/operacion/*`.
//
// Server Component, mismo patrón que la Cola. Operacion solo se la da a
// operador y admin: sin sesion o sin rol se muestra el aviso que corresponde.
// Los filtros viven en la URL y filtran aqui, en el servidor; las tarjetas de
// arriba son siempre las globales.

import Form from "next/form";
import Link from "next/link";
import { LifeBuoy, AlarmClock, CheckCircle2 } from "lucide-react";
import type { BandejaOperacion, Caso, Prioridad } from "@tukit/contrato";
import {
  casoActivo,
  ETIQUETA_CATEGORIA_CASO,
  ETIQUETA_PRIORIDAD,
  ORDEN_PRIORIDAD,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import AvisoAcceso from "@/components/AvisoAcceso";
import { formatearFecha } from "@/lib/formato";
import { motivoDeFallo } from "@/lib/logistica";
import { tokenDeSesion } from "@/lib/sesion";
import {
  ESTADOS_TICKET,
  ETIQUETA_ESTADO_TICKET,
  estaVencido,
  filtrarCasos,
  hayFiltrosTickets,
  instanteActual,
  leerFiltrosTickets,
  textoVencimiento,
} from "@/lib/tickets";
import Revelar from "@/components/Revelar";
import styles from "./Tickets.module.css";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const CATEGORIAS = Object.keys(ETIQUETA_CATEGORIA_CASO) as (keyof typeof ETIQUETA_CATEGORIA_CASO)[];

function Encabezado() {
  return (
    <header className={styles.encabezado}>
      <div>
        <h1>Tickets</h1>
        <p className={styles.bajada}>
          PQRS y casos de <code>operacion</code>. Cada falla del flujo abre un caso; las
          peticiones de los acudientes entran por aquí. Lo urgente tiene un reloj legal (Ley
          1755), así que se entra por lo de arriba. Abre un ticket para responder.
        </p>
      </div>
    </header>
  );
}

export default async function PaginaTickets({ searchParams }: Props) {
  const token = await tokenDeSesion();
  if (!token) {
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo="sin_sesion" />
      </div>
    );
  }

  let bandeja: BandejaOperacion;
  try {
    bandeja = await origenDeDatos().casos(token);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit)) throw causa;
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo={motivoDeFallo(causa.estado)} />
      </div>
    );
  }
  const { resumen } = bandeja;
  const filtros = leerFiltrosTickets(await searchParams);
  const casos = filtrarCasos(bandeja.casos, filtros);
  const ahora = instanteActual();

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
      <Encabezado />

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

      {bandeja.casos.length > 0 ? (
        // El `key` remonta el formulario al cambiar los filtros (atras/adelante,
        // "Limpiar"), para que sus `defaultValue` no queden viejos.
        <Form action="/tickets" className={styles.filtros} aria-label="Filtrar tickets" key={JSON.stringify(filtros)}>
          <div className={styles.campoFiltro}>
            <label htmlFor="t-q">Código o asunto</label>
            <input id="t-q" name="q" type="search" defaultValue={filtros.q} autoComplete="off" />
          </div>
          <div className={styles.campoFiltro}>
            <label htmlFor="t-estado">Estado</label>
            <select id="t-estado" name="estado" defaultValue={filtros.estado}>
              <option value="">Todos</option>
              {ESTADOS_TICKET.map((e) => (
                <option key={e} value={e}>
                  {ETIQUETA_ESTADO_TICKET[e]}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.campoFiltro}>
            <label htmlFor="t-categoria">Categoría</label>
            <select id="t-categoria" name="categoria" defaultValue={filtros.categoria}>
              <option value="">Todas</option>
              {CATEGORIAS.map((c) => (
                <option key={c} value={c}>
                  {ETIQUETA_CATEGORIA_CASO[c]}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className={styles.filtrar}>
            Filtrar
          </button>
          <Link href="/tickets" className={styles.limpiar}>
            Limpiar
          </Link>
        </Form>
      ) : null}

      {bandeja.casos.length > 0 && hayFiltrosTickets(filtros) ? (
        <p className={styles.tenue} aria-live="polite">
          Mostrando {casos.length} de {bandeja.casos.length} tickets.
        </p>
      ) : null}

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
                <th scope="col">Plazo</th>
                <th scope="col">Vínculo</th>
              </tr>
            </thead>
            <tbody>
              {ordenados.map((caso) => (
                <FilaCaso key={caso.caso_id} caso={caso} ahora={ahora} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FilaCaso({ caso, ahora }: { caso: Caso; ahora: number }) {
  const activo = casoActivo(caso);
  const urgente: Prioridad = "urgente";
  return (
    <tr className={!activo ? styles.filaCerrada : caso.prioridad === urgente ? styles.filaUrgente : ""}>
      <th scope="row" className={styles.identificador}>
        <Link href={`/tickets/${caso.caso_id}`} className={styles.enlace}>
          <code>{caso.caso_id.slice(0, 8).toUpperCase()}</code>
        </Link>
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
          {ETIQUETA_ESTADO_TICKET[caso.estado]}
        </span>
      </td>
      <td className={styles.fechaExacta}>{formatearFecha(caso.abierto_en)}</td>
      <td className={estaVencido(caso, ahora) ? styles.vencido : styles.tenue}>
        {textoVencimiento(caso, ahora) ?? "—"}
      </td>
      <td className={styles.vinculo}>
        {caso.pedido_id ? (
          <Link href={`/logistica/${caso.pedido_id}`} className={styles.enlace}>
            pedido <code>{caso.pedido_id.slice(0, 8).toUpperCase()}</code>
          </Link>
        ) : caso.trabajo_id ? (
          <Link href={`/trabajos/${caso.trabajo_id}`} className={styles.enlace}>
            trabajo <code>{caso.trabajo_id.slice(0, 8)}</code>
          </Link>
        ) : (
          <span className={styles.tenue}>—</span>
        )}
      </td>
    </tr>
  );
}
