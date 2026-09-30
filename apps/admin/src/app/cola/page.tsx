// `/cola` — la cola de revision unificada (AD-01, AD-03).
//
// El item de la cola es una VERSION DE LISTA pendiente (`revisada=false`): el
// mismo acto —revisar "la lista del colegio X, grado Y"— sin importar si la
// envio el colegio (onboarding) o la subio un acudiente (sugerencia_padre).
// Revisar una version abre el revisor de cuatro paneles; aprobarla la vuelve
// lista oficial verificada y la reusa el pipeline para todos los acudientes de
// ese (colegio, grado).
//
// Debajo, mientras el ingreso de acudiente todavia crea trabajos desechables,
// se listan los que esperan revision para que no desaparezcan. Cuando el
// ingreso de acudiente pase a crear versiones (Slice C), esta seccion se vacia
// sola.
//
// Server Component: lee el origen directamente. No hay `fetch` de por medio
// porque la lectura no pasa por el navegador.

import Link from "next/link";
import type { EntradaCola, VersionListaAdmin } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import BorrarTrabajo from "@/components/BorrarTrabajo";
import BorrarVersion from "@/components/BorrarVersion";
import { formatearFecha, haceCuanto, TITULO_ESTADO_TRABAJO } from "@/lib/formato";
import SubirLista from "./SubirLista";
import styles from "./Cola.module.css";

export const dynamic = "force-dynamic";

// Como se nombra cada ingreso en la insignia. `null` es una version sin
// procedencia conocida (sembrada del corpus): se revisa igual, pero no se
// atribuye a un colegio ni a un padre.
const ETIQUETA_INGRESO: Record<NonNullable<VersionListaAdmin["procedencia"]>, string> = {
  onboarding: "El colegio la envió",
  sugerencia_padre: "Un acudiente la subió",
};

function ColaVacia() {
  return (
    <div className={styles.vacia}>
      <h2>No hay nada que verificar.</h2>
      <p>
        La cola se llena sola: cada lista que un colegio envía o que un acudiente sube entra
        aquí como una versión pendiente y espera a que alguien la revise. Aprobarla la deja
        como lista oficial verificada y el pipeline la reutiliza para todos los acudientes de
        ese colegio y grado.
      </p>
      <p className={styles.pistaVacia}>
        Para crear una, abre la app del acudiente en{" "}
        <a href="http://localhost:3000/empezar" className={styles.enlaceExterno}>
          http://localhost:3000/empezar
        </a>{" "}
        y sube la lista de un grado sin verificar.
      </p>
    </div>
  );
}

export default async function PaginaCola() {
  // Dos lecturas del mismo origen: las versiones PENDIENTES (el item real de la
  // cola) y los trabajos en vuelo (el ingreso de acudiente que aún no se ha
  // migrado a versión). Los colegios dan el nombre legible de cada `colegio_id`.
  const [pendientes, { entradas }, colegios] = await Promise.all([
    origenDeDatos().listasAdmin({ revisada: false }),
    origenDeDatos().cola(),
    origenDeDatos().colegios(),
  ]);

  const nombreColegio = new Map(colegios.map((c) => [c.colegio_id, c.nombre]));

  // Un solo reloj para toda la página: si cada fila llamara a `Date.now()`, dos
  // filas del mismo instante podrían mostrar minutos distintos.
  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  // Las versiones se ordenan por lo que más trabajo pide: primero las que
  // tienen un acudiente esperando (aprobar dispara su kit), después por
  // renglones por resolver, y a igualdad por más renglones primero.
  const versiones = [...pendientes].sort(
    (a, b) =>
      Number(b.tiene_contacto) - Number(a.tiene_contacto) || b.items - a.items,
  );

  // Solo los trabajos que esperan una persona: lo publicado es historial y lo
  // que aún procesa no necesita acción. Un trabajo es el ingreso de acudiente
  // sin migrar; se muestra aparte, no mezclado con las versiones.
  const trabajosEnEspera = entradas.filter((e) => e.estado === "espera_revision");

  const conContacto = versiones.filter((v) => v.tiene_contacto).length;

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Cola de verificación</h1>
          <p className={styles.bajada}>
            Ninguna lista llega al acudiente sin pasar por aquí. Cada versión pendiente —la
            envíe el colegio o la suba un acudiente— se revisa una vez; al aprobarla queda
            verificada y el pipeline la reutiliza para todos.
          </p>
        </div>
        <div className={styles.acciones}>
          <SubirLista colegios={colegios} />
          <dl className={styles.resumen}>
            <div>
              <dt>Listas por verificar</dt>
              <dd className="cifra">{versiones.length}</dd>
            </div>
            <div>
              <dt>Con acudiente esperando</dt>
              <dd className="cifra">{conContacto}</dd>
            </div>
            <div>
              <dt>Trabajos en espera</dt>
              <dd className="cifra">{trabajosEnEspera.length}</dd>
            </div>
          </dl>
        </div>
      </header>

      {versiones.length === 0 && trabajosEnEspera.length === 0 ? (
        <ColaVacia />
      ) : (
        <>
          {versiones.length > 0 ? (
            <div className={styles.marco}>
              <table className={styles.tabla}>
                <caption className={styles.leyenda}>
                  Versiones pendientes de verificación. Primero las que tienen un acudiente
                  esperando —aprobarlas dispara su kit—, después por renglones por resolver.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Colegio</th>
                    <th scope="col">Grado</th>
                    <th scope="col">Ingreso</th>
                    <th scope="col" className={styles.num}>
                      Año
                    </th>
                    <th scope="col" className={styles.num}>
                      Renglones
                    </th>
                    <th scope="col">
                      <span className={styles.oculto}>Acción</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {versiones.map((v) => (
                    <tr key={v.version_id} className={v.tiene_contacto ? styles.filaEspera : ""}>
                      <th scope="row" className={styles.identificador}>
                        <Link href={`/onboarding/${encodeURIComponent(v.version_id)}`}>
                          {nombreColegio.get(v.colegio_id) ??
                            v.colegio_nombre ?? <code>{v.colegio_id}</code>}
                        </Link>
                      </th>
                      <td>{v.grado}</td>
                      <td>
                        <span className={styles.estado}>
                          {v.procedencia ? ETIQUETA_INGRESO[v.procedencia] : "Sin procedencia"}
                        </span>
                        {v.tiene_contacto ? (
                          <span className={styles.pistaContacto}> · acudiente esperando</span>
                        ) : null}
                      </td>
                      <td className={`${styles.num} cifra ${styles.tenue}`}>{v.anio_lectivo}</td>
                      <td className={`${styles.num} cifra`}>{v.items}</td>
                      <td className={styles.accionCelda}>
                        <Link
                          href={`/onboarding/${encodeURIComponent(v.version_id)}`}
                          className={styles.accion}
                        >
                          Revisar
                        </Link>
                        <BorrarVersion versionId={v.version_id} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {trabajosEnEspera.length > 0 ? (
            <section className={styles.bloqueTrabajos}>
              <h2 className={styles.subtitulo}>Trabajos de acudiente en espera</h2>
              <p className={styles.bajada}>
                Ingresos de acudiente que aún esperan revisión como trabajo. Cada uno se
                revisará contra la versión de su colegio y grado.
              </p>
              <div className={styles.marco}>
                <table className={styles.tabla}>
                  <thead>
                    <tr>
                      <th scope="col">Trabajo</th>
                      <th scope="col">Recibido</th>
                      <th scope="col" className={styles.num}>
                        Pendientes
                      </th>
                      <th scope="col">Colegios</th>
                      <th scope="col">Grados</th>
                      <th scope="col">
                        <span className={styles.oculto}>Acción</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {trabajosEnEspera.map((entrada: EntradaCola) => (
                      <tr key={entrada.trabajo_id} className={styles.filaEspera}>
                        <th scope="row" className={styles.identificador}>
                          <Link href={`/trabajos/${entrada.trabajo_id}`}>
                            <code>{entrada.trabajo_id.slice(0, 8).toUpperCase()}</code>
                          </Link>
                        </th>
                        <td className={styles.fecha}>
                          <span>{haceCuanto(entrada.recibido_en, ahora)}</span>
                          <span className={styles.fechaExacta}>
                            {formatearFecha(entrada.recibido_en)}
                          </span>
                        </td>
                        <td className={`${styles.num} cifra`}>
                          {entrada.lineas_pendientes > 0 ? (
                            <span className={styles.pendientes}>{entrada.lineas_pendientes}</span>
                          ) : (
                            <span className={styles.cero}>0</span>
                          )}
                        </td>
                        <td className={styles.lista}>{entrada.colegios.join(", ") || "—"}</td>
                        <td className={styles.lista}>{entrada.grados.join(", ") || "—"}</td>
                        <td className={styles.accionCelda}>
                          <Link href={`/trabajos/${entrada.trabajo_id}`} className={styles.accion}>
                            {TITULO_ESTADO_TRABAJO[entrada.estado] ? "Revisar" : "Ver"}
                          </Link>
                          <BorrarTrabajo trabajoId={entrada.trabajo_id} estado={entrada.estado} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
