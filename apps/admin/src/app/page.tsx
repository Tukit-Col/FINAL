import Link from "next/link";
import { ArrowRight, CircleCheck, TriangleAlert } from "lucide-react";
import {
  ETIQUETA_CATEGORIA_CASO,
  ETIQUETA_ESTADO_CASO,
  ETIQUETA_ESTADO_PEDIDO,
  ETIQUETA_PRIORIDAD,
  formatearPesos,
  GRADOS_CANONICOS,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { PulsoActividad, PulsoListas } from "@/components/PanelPulso";
import Revelar from "@/components/Revelar";
import Barras from "@/components/ui/Barras";
import BotonMagnetico from "@/components/ui/BotonMagnetico";
import Destacada from "@/components/ui/Destacada";
import Dona, { type SegmentoDona } from "@/components/ui/Dona";
import { construirPanel, type FuentePanel } from "@/lib/panel-accionable";
import {
  actividadReciente,
  flujoDePedidos,
  listasPorColegio,
  ticketsPorEstado,
} from "@/lib/panel-vivo";
import { tokenDeSesion } from "@/lib/sesion";
import styles from "./Panel.module.css";

export const dynamic = "force-dynamic";

const NOMBRE_FUENTE: Record<FuentePanel, string> = {
  pedidos: "los pedidos (comercio)",
  casos: "los tickets (operación)",
  cola: "la cola de revisión",
};

const COLOR_ETAPA: Record<string, string> = {
  pendiente_pago: "var(--clay-estrella-oscuro)",
  pagado: "var(--clay-cielo-claro)",
  en_preparacion: "var(--clay-cielo)",
  despachado: "#2b6cc4",
  en_reparto: "var(--color-primary)",
  entregado: "var(--color-success)",
};

const ETIQUETA_SLA: Record<string, string> = {
  vencidos: "Plazo vencido",
  vencen_hoy: "Vencen hoy",
  urgentes: "Urgentes",
};

function sinPermiso(r: PromiseSettledResult<unknown>): boolean {
  return (
    r.status === "rejected" &&
    r.reason instanceof ErrorTukit &&
    (r.reason.estado === 401 || r.reason.estado === 403)
  );
}

export default async function PaginaPanel() {
  const api = origenDeDatos();
  const token = await tokenDeSesion();
  const sinSesion = () =>
    Promise.reject(new ErrorTukit(401, "sesion_invalida", "Sin sesion."));

  const [pedidosR, casosR, colaR, listasR, colegiosR] = await Promise.allSettled([
    token ? api.pedidos(token) : sinSesion(),
    token ? api.casos(token) : sinSesion(),
    api.cola(),
    api.listasAdmin({ revisada: false }),
    api.colegios(),
  ]);

  const pedidos = pedidosR.status === "fulfilled" ? pedidosR.value : null;
  const casos = casosR.status === "fulfilled" ? casosR.value : null;
  const cola = colaR.status === "fulfilled" ? colaR.value : null;

  const { widgets, enCero, caidos, sinActivar } = construirPanel({
    pedidos: pedidos?.resumen ?? null,
    casos: casos?.resumen ?? null,
    cola,
  });
  const sinPermisoDe: Record<FuentePanel, boolean> = {
    pedidos: sinPermiso(pedidosR),
    casos: sinPermiso(casosR),
    cola: sinPermiso(colaR),
  };

  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();
  const nombres = new Map(
    colegiosR.status === "fulfilled"
      ? colegiosR.value.map((c) => [c.colegio_id, c.nombre] as const)
      : [],
  );
  const flujo = pedidos ? flujoDePedidos(pedidos.resumen) : null;
  const tk = casos ? ticketsPorEstado(casos.casos, casos.resumen) : null;
  const listas =
    listasR.status === "fulfilled"
      ? listasPorColegio(listasR.value, nombres, 5, GRADOS_CANONICOS)
      : null;
  const actividad = actividadReciente({
    pedidos: pedidos?.pedidos ?? [],
    casos: casos?.casos ?? [],
    cola,
    etiquetaPedido: (e) => ETIQUETA_ESTADO_PEDIDO[e],
    etiquetaCategoria: (c) => ETIQUETA_CATEGORIA_CASO[c],
    etiquetaPrioridad: (p) => ETIQUETA_PRIORIDAD[p],
    dinero: formatearPesos,
    nombreColegio: (ids) => ids.map((id) => nombres.get(id) ?? id).join(", "),
  });

  const hayPendientes = widgets.length > 0;
  const urgente = [...widgets].sort(
    (x, y) => Number(y.urgencia === "alta") - Number(x.urgencia === "alta") || y.cantidad - x.cantidad,
  )[0];

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <h1>Panel</h1>
        <p>Lo que pide acción y cómo va la operación.</p>
      </header>

      {caidos.map((fuente) => (
        <p key={fuente} className={styles.caida} role="status">
          <TriangleAlert size={15} strokeWidth={2.2} aria-hidden="true" />
          {sinPermisoDe[fuente]
            ? `Tu sesión no puede ver ${NOMBRE_FUENTE[fuente]}: ingresa con una cuenta de operador o admin.`
            : `No pudimos leer ${NOMBRE_FUENTE[fuente]}. Revisa que el servicio esté arriba (make estado).`}
        </p>
      ))}

      {hayPendientes ? (
        <Revelar>
          <ul className={styles.rejilla} aria-label="Pendientes">
            {widgets.map((w) => {
              const esUrgente = w.id === urgente?.id;
              const cuerpo = (
                <>
                  <span className={`${styles.cantidad} cifra`}>{w.cantidad}</span>
                  <h2>{w.titulo}</h2>
                  <p>{w.ayuda}</p>
                  {esUrgente ? (
                    <BotonMagnetico href={w.enlace}>
                      {w.textoEnlace}
                      <ArrowRight size={15} strokeWidth={2.4} aria-hidden="true" />
                    </BotonMagnetico>
                  ) : (
                    <Link href={w.enlace} className={styles.accion}>
                      {w.textoEnlace}
                      <ArrowRight size={15} strokeWidth={2.4} aria-hidden="true" />
                    </Link>
                  )}
                </>
              );
              return esUrgente ? (
                <li key={w.id} className={`${styles.grande} ${widgets.length === 1 ? styles.sola : ""}`}>
                  <Destacada className={`${styles.widget} ${styles.alta} ${styles.urgente}`}>{cuerpo}</Destacada>
                </li>
              ) : (
                <li
                  key={w.id}
                  className={`${styles.widget} ${w.urgencia === "alta" ? styles.alta : styles.media}`}
                >
                  {cuerpo}
                </li>
              );
            })}
          </ul>
        </Revelar>
      ) : caidos.length < 3 ? (
        <p className={styles.alDia} role="status">
          <CircleCheck size={20} strokeWidth={2.2} aria-hidden="true" />
          Todo al día. No hay nada que requiera una acción ahora.
        </p>
      ) : null}

      {enCero.length > 0 ? (
        <ul className={styles.ceros} aria-label="Pendientes en cero">
          {enCero.map((w) => (
            <li key={w.id}>
              <Link href={w.enlace} className={styles.cero}>
                <span className="cifra">0</span> {w.titulo}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      <div className={styles.paneles}>
        {flujo ? (
          <section className={`${styles.bloque} ${styles.ancho}`} aria-labelledby="t-flujo">
            <h2 id="t-flujo">Flujo de pedidos</h2>
            <Dona
              centro="en el flujo"
              segmentos={flujo.etapas.map(
                (e): SegmentoDona => ({
                  clave: e.estado,
                  etiqueta: ETIQUETA_ESTADO_PEDIDO[e.estado],
                  valor: e.cantidad,
                  href: e.enlace,
                  color: COLOR_ETAPA[e.estado] ?? "var(--clay-cielo)",
                }),
              )}
            />
            <p className={styles.lateral}>
              <Link
                href={flujo.incidencia.enlace}
                className={flujo.incidencia.cantidad > 0 ? styles.rojo : undefined}
              >
                <span className="cifra">{flujo.incidencia.cantidad}</span>{" "}
                {ETIQUETA_ESTADO_PEDIDO.incidencia.toLowerCase()}
              </Link>
              <Link href={flujo.cancelado.enlace}>
                <span className="cifra">{flujo.cancelado.cantidad}</span>{" "}
                {ETIQUETA_ESTADO_PEDIDO.cancelado.toLowerCase()}
              </Link>
            </p>
          </section>
        ) : null}

        {tk ? (
          <section className={`${styles.bloque} ${styles.ancho}`} aria-labelledby="t-tickets">
            <h2 id="t-tickets">Tickets</h2>
            <Barras
              filas={tk.sla.map((f) => ({
                clave: f.clave,
                etiqueta: ETIQUETA_SLA[f.clave],
                valor: f.cantidad,
                href: f.enlace,
                tono: f.critico ? "critico" : "aviso",
              }))}
            />
            <h3>Activos por estado</h3>
            <Barras
              filas={tk.estados.map((f) => ({
                clave: f.clave,
                etiqueta: ETIQUETA_ESTADO_CASO[f.clave as keyof typeof ETIQUETA_ESTADO_CASO],
                valor: f.cantidad,
                href: f.enlace,
              }))}
            />
          </section>
        ) : null}

        <section className={`${styles.bloque} ${styles.ancho}`} aria-labelledby="t-listas">
          <h2 id="t-listas">Listas por verificar</h2>
          <PulsoListas listas={listas} />
        </section>

        <section className={`${styles.bloque} ${styles.ancho}`} aria-labelledby="t-act">
          <h2 id="t-act">Actividad reciente</h2>
          <PulsoActividad actividad={actividad} pedidos={pedidos?.pedidos ?? null} ahora={ahora} />
        </section>
      </div>

      {sinActivar.length > 0 ? (
        <p className={styles.nota}>
          Algunos conteos de{" "}
          {sinActivar.map((f) => NOMBRE_FUENTE[f]).join(" y ")} se activan al
          reiniciar el servicio; hasta entonces cuentan como cero.
        </p>
      ) : null}
    </div>
  );
}
