// `/trabajos/{id}` — el detalle y la revision (AD-02 a AD-07).
//
// Server Component para leer: `trabajoAdmin()` sale del origen directamente,
// sin pasar por el navegador. Las escrituras si van por Route Handlers, que
// es donde la bandera y la URL del backend se quedan del lado del servidor.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { TrabajoAdmin } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import BorrarTrabajo from "@/components/BorrarTrabajo";
import ConsolaRevision from "@/components/ConsolaRevision";
import DecisionTrabajo from "@/components/DecisionTrabajo";
import { resumenPendientes } from "@/lib/consola";
import {
  formatearFecha,
  haceCuanto,
  TITULO_ESTADO_ETAPA,
  TITULO_ESTADO_TRABAJO,
} from "@/lib/formato";
import styles from "./Detalle.module.css";

export const dynamic = "force-dynamic";

// Los 4 conceptos ancla del kit Fan (cuaderno/cartuchera/carpeta/maleta),
// espejo de CONCEPTOS_ANCLA en optimizador.py:91 y PersonajeFan.tsx:26. Una
// franquicia solo es "validada" si tiene producto para las cuatro.
const ANCLAS_FAN = ["C001", "C009", "C011", "C086"] as const;

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

  // Las franquicias del catálogo para el interruptor de personaje del kit Fan
  // (§7, 2d). Se lee aquí —Server Component— y se pasa como nombres; si el
  // catálogo está caído, se degrada a lista vacía (el interruptor no aparece).
  //
  // Solo las franquicias VALIDADAS: las que tienen producto para las 4 anclas.
  // El endpoint devuelve `conceptos` justo para que la UI calcule este gate (el
  // catálogo no lo calcula). Sin las 4, el switch dejaría anclas sin cambiar.
  const personajes = await origenDeDatos()
    .personajes()
    .then((lista) =>
      lista.filter((p) => ANCLAS_FAN.every((c) => p.conceptos?.includes(c))).map((p) => p.nombre),
    )
    .catch(() => [] as string[]);

  // El reloj de la peticion. `react-hooks/purity` lo marca porque en un
  // componente de cliente daria un render inestable; este es un Server
  // Component con `force-dynamic`, se renderiza una vez por peticion y no se
  // hidrata, asi que el valor no puede cambiar bajo los pies de nadie.
  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  // Un preview de onboarding no se publica desde aquí: se ajusta, y al aprobar
  // su lista esos ajustes pasan a ser el kit del colegio y grado. La consola lo
  // trata distinto: enlaza al revisor de su lista (el `version_id` que el
  // preview guarda en su único hijo) en vez de ofrecer "Publicar".
  const esPreview = trabajo.origen === "preview_onboarding";
  const versionPreview = trabajo.hijos[0]?.version_id;

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
        <Link href="/cola">← Cola de revisión</Link>
        <BorrarTrabajo trabajoId={trabajo.trabajo_id} estado={trabajo.estado} volverA="/cola" />
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
                trabajo.lineas_sin_decidir + trabajo.huecos > 0
                  ? styles.pendientes
                  : styles.sinPendientes
              }
            >
              {resumenPendientes(trabajo.lineas_sin_decidir, trabajo.huecos)}
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

      {esPreview ? (
        // Un preview de onboarding no se publica desde aquí: no tiene acudiente a
        // quien avisar (el backend lo rechaza con 409). Se publica al APROBAR su
        // lista en el revisor, que lo promueve —con estos ajustes— a kit del
        // colegio y grado. Se enlaza de vuelta en vez de ofrecer un "Publicar"
        // que no funciona.
        <section className={styles.avisoPreview}>
          <h2>Este es un preview de la lista</h2>
          <p>
            Ajusta aquí los tres kits: valida líneas, cambia productos o personaje. Cuando
            apruebes la lista en su revisión, esta vista previa —con tus ajustes— pasa a ser el kit
            de ese colegio y grado. Si al aprobar quedan líneas dudosas sin decidir, el kit queda en
            la cola para terminarlo; si la lista cambió después de previsualizar, se arma de nuevo.
          </p>
          {versionPreview ? (
            <Link href={`/onboarding/${encodeURIComponent(versionPreview)}`} className={styles.enlaceRevisor}>
              Ir a la revisión de la lista →
            </Link>
          ) : (
            <Link href="/cola" className={styles.enlaceRevisor}>
              Volver a la cola de verificación →
            </Link>
          )}
        </section>
      ) : (
        <DecisionTrabajo
          trabajoId={trabajo.trabajo_id}
          estado={trabajo.estado}
          lineasPendientes={trabajo.lineas_pendientes.length}
          notaRevision={trabajo.nota_revision}
        />
      )}

      <ConsolaRevision trabajo={trabajo} personajes={personajes} />
    </div>
  );
}
