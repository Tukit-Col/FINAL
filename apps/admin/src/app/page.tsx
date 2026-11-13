// `/` — lo que hay que atender hoy. Es la casa del operador: solo muestra lo que
// pide una acción, cada widget con el enlace directo a esa acción. Los totales y
// las tendencias viven en sus pantallas (`/logistica`, `/tickets`, `/cola`,
// `/catalogo`, `/colegios`).
//
// Tres lecturas independientes (pedidos, casos, cola) con `allSettled`: si un
// servicio cae, se avisa de ESE y los demás widgets se pintan. Con todo en cero
// se dice una sola vez "Todo al día".

import Link from "next/link";
import { ArrowRight, CircleCheck, TriangleAlert } from "lucide-react";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import Revelar from "@/components/Revelar";
import { construirWidgets, type FuentePanel } from "@/lib/panel-accionable";
import { tokenDeSesion } from "@/lib/sesion";
import styles from "./Panel.module.css";

export const dynamic = "force-dynamic";

const NOMBRE_FUENTE: Record<FuentePanel, string> = {
  pedidos: "los pedidos (comercio)",
  casos: "los tickets (operación)",
  cola: "la cola de revisión",
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
  // Pedidos y casos son solo de operador/admin: sin cookie ni se pregunta.
  const token = await tokenDeSesion();
  const sinSesion = () =>
    Promise.reject(new ErrorTukit(401, "sesion_invalida", "Sin sesion."));

  const [pedidosR, casosR, colaR] = await Promise.allSettled([
    token ? api.pedidos(token) : sinSesion(),
    token ? api.casos(token) : sinSesion(),
    api.cola(),
  ]);

  const { widgets, caidos, sinActivar } = construirWidgets({
    pedidos: pedidosR.status === "fulfilled" ? pedidosR.value.resumen : null,
    casos: casosR.status === "fulfilled" ? casosR.value.resumen : null,
    cola: colaR.status === "fulfilled" ? colaR.value : null,
  });
  const sinPermisoDe: Record<FuentePanel, boolean> = {
    pedidos: sinPermiso(pedidosR),
    casos: sinPermiso(casosR),
    cola: sinPermiso(colaR),
  };

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <h1>Hoy hay que atender</h1>
      </header>

      {caidos.map((fuente) => (
        <p key={fuente} className={styles.caida} role="status">
          <TriangleAlert size={15} strokeWidth={2.2} aria-hidden="true" />
          {sinPermisoDe[fuente]
            ? `Tu sesión no puede ver ${NOMBRE_FUENTE[fuente]}: ingresa con una cuenta de operador o admin.`
            : `No pudimos leer ${NOMBRE_FUENTE[fuente]}. Revisa que el servicio esté arriba (make estado).`}
        </p>
      ))}

      {widgets.length > 0 ? (
        <Revelar>
          <ul className={styles.rejilla} aria-label="Pendientes">
            {widgets.map((w) => (
              <li
                key={w.id}
                className={`${styles.widget} ${w.urgencia === "alta" ? styles.alta : styles.media}`}
              >
                <span className={`${styles.cantidad} cifra`}>{w.cantidad}</span>
                <h2>{w.titulo}</h2>
                <p>{w.ayuda}</p>
                <Link href={w.enlace} className={styles.accion}>
                  {w.textoEnlace}
                  <ArrowRight size={15} strokeWidth={2.4} aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        </Revelar>
      ) : caidos.length < 3 ? (
        <p className={styles.alDia} role="status">
          <CircleCheck size={20} strokeWidth={2.2} aria-hidden="true" />
          Todo al día. No hay nada que requiera una acción ahora.
        </p>
      ) : null}

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
