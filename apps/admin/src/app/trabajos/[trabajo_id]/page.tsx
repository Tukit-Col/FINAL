// `/trabajos/{id}` — el detalle y la revision (AD-03 a AD-07).
//
// Server Component para leer: `trabajoAdmin()` sale del origen directamente,
// sin pasar por el navegador. Las escrituras si van por Route Handlers, que
// es donde la bandera y la URL del backend se quedan del lado del servidor.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { TrabajoAdmin } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import ConsolaRevision from "@/components/ConsolaRevision";
import DecisionTrabajo from "@/components/DecisionTrabajo";
import {
  formatearFecha,
  haceCuanto,
  TITULO_ESTADO_ETAPA,
  TITULO_ESTADO_TRABAJO,
} from "@/lib/formato";
import styles from "./Detalle.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ trabajo_id: string }>;
}

export default async function PaginaTrabajo({ params }: Props) {
  const { trabajo_id } = await params;

  let trabajo: TrabajoAdmin;
  try {
    trabajo = await origenDeDatos().trabajoAdmin(trabajo_id);
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) notFound();
    throw causa;
  }

  // El reloj de la peticion. `react-hooks/purity` lo marca porque en un
  // componente de cliente daria un render inestable; este es un Server
  // Component con `force-dynamic`, se renderiza una vez por peticion y no se
  // hidrata, asi que el valor no puede cambiar bajo los pies de nadie.
  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  // Los hijos no vienen sueltos en `TrabajoAdmin`: se derivan de las lineas,
  // que es donde el contrato pone la referencia de cada hijo.
  const hijos = [
    ...new Set(
      (trabajo.kits[0]?.lineas ?? []).flatMap((linea) => (linea.hijo ? [linea.hijo] : [])),
    ),
  ];

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href="/">← Cola de revisión</Link>
      </nav>

      <header className={styles.encabezado}>
        <div className={styles.identidad}>
          <h1>
            Trabajo <code>{trabajo.trabajo_id}</code>
          </h1>
          <div className={styles.hechos}>
            <span className={`${styles.estado} ${styles[`estado_${trabajo.estado}`]}`}>
              {TITULO_ESTADO_TRABAJO[trabajo.estado]}
            </span>
            <span>
              Recibido {haceCuanto(trabajo.recibido_en, ahora)} ·{" "}
              <span className="cifra">{formatearFecha(trabajo.recibido_en)}</span>
            </span>
            <span>
              {hijos.length} {hijos.length === 1 ? "hijo" : "hijos"}
              {hijos.length > 0 ? `: ${hijos.join(", ")}` : ""}
            </span>
            <span
              className={
                trabajo.lineas_pendientes.length > 0 ? styles.pendientes : styles.sinPendientes
              }
            >
              {trabajo.lineas_pendientes.length} líneas pendientes
            </span>
          </div>

          {/* Nunca el correo ni el celular: la notificacion referencia al
              acudiente por identificador, y por eso el tipo trae `contacto_id`
              y no el correo. Mostrarlo aqui seria reintroducir a mano la
              deuda que el manifiesto documenta en `operacion.notificacion`. */}
          <p className={styles.contacto}>
            Acudiente <code>{trabajo.contacto_id}</code>
            <span className={styles.contactoNota}>
              La consola no muestra el correo ni el celular: la notificación los referencia por
              identificador.
            </span>
          </p>
        </div>

        <ol className={styles.etapas}>
          {trabajo.etapas.map((etapa) => (
            <li key={etapa.nombre} className={styles[`etapa_${etapa.estado}`]}>
              <span className={styles.etapaNombre}>{etapa.nombre}</span>
              <span className={styles.etapaEstado}>{TITULO_ESTADO_ETAPA[etapa.estado]}</span>
              <span className={`${styles.etapaMs} cifra`}>{etapa.ms} ms</span>
            </li>
          ))}
        </ol>
      </header>

      {trabajo.degradaciones.length > 0 ? (
        <section className={styles.degradaciones} aria-labelledby="degradaciones-titulo">
          <h2 id="degradaciones-titulo">Degradaciones (§8)</h2>
          <p className={styles.degradacionesBajada}>
            Se reportan, no se esconden: el trabajo salió adelante con una respuesta parcial
            honesta en vez de caerse.
          </p>
          <ul>
            {trabajo.degradaciones.map((degradacion) => (
              <li key={degradacion.dependencia}>
                <code>{degradacion.dependencia}</code> {degradacion.efecto}
                <span className={styles.afectadas}>
                  {degradacion.lineas_afectadas} líneas afectadas
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <DecisionTrabajo
        trabajoId={trabajo.trabajo_id}
        estado={trabajo.estado}
        lineasPendientes={trabajo.lineas_pendientes.length}
        notaRevision={trabajo.nota_revision}
      />

      <ConsolaRevision trabajo={trabajo} />
    </div>
  );
}
