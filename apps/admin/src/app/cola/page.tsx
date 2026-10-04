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
import BorrarVersionLista from "@/components/BorrarVersionLista";
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

interface PropsTabla {
  titulo: string;
  bajada: string;
  entradas: EntradaCola[];
  nombreColegio: Map<string, string>;
  ahora: number;
  /** Sin la barra de "espera a una persona": nadie la espera. */
  tenue?: boolean;
}

function TablaTrabajos({ titulo, bajada, entradas, nombreColegio, ahora, tenue = false }: PropsTabla) {
  return (
    <section className={styles.bloqueTrabajos}>
      <h2 className={styles.subtitulo}>{titulo}</h2>
      <p className={styles.bajada}>{bajada}</p>
      <div className={styles.marco}>
        <table className={styles.tabla}>
          <thead>
            <tr>
              <th scope="col">Trabajo</th>
              <th scope="col">Recibido</th>
              <th scope="col">Colegio</th>
              <th scope="col">Grado</th>
              <th scope="col" className={styles.num}>
                Pendientes
              </th>
              <th scope="col">
                <span className={styles.oculto}>Acción</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {entradas.map((entrada) => {
              const colegios = entrada.colegios.map((id) => nombreColegio.get(id) ?? id).join(", ");
              const grados = entrada.grados.join(", ");
              return (
                <tr key={entrada.trabajo_id} className={tenue ? "" : styles.filaEspera}>
                  {/* El id completo no se lee: basta el prefijo, y el completo
                      queda en el title para copiarlo. */}
                  <th scope="row" className={styles.identificador}>
                    <Link href={`/trabajos/${entrada.trabajo_id}`} title={entrada.trabajo_id}>
                      Trabajo <code>#{entrada.trabajo_id.slice(0, 8)}</code>
                    </Link>
                  </th>
                  <td>
                    <div className={styles.fecha}>
                      <span>{haceCuanto(entrada.recibido_en, ahora)}</span>
                      <span className={styles.fechaExacta}>{formatearFecha(entrada.recibido_en)}</span>
                    </div>
                  </td>
                  <td className={colegios ? styles.lista : `${styles.lista} ${styles.tenue}`}>
                    {colegios || "Sin identificar"}
                  </td>
                  <td className={grados ? undefined : styles.tenue}>{grados || "—"}</td>
                  <td className={`${styles.num} cifra`}>
                    {entrada.lineas_pendientes > 0 ? (
                      <span className={styles.pendientes}>{entrada.lineas_pendientes}</span>
                    ) : (
                      <span className={styles.cero}>0</span>
                    )}
                  </td>
                  <td className={styles.accionCelda}>
                    <div className={styles.accionesFila}>
                      <Link href={`/trabajos/${entrada.trabajo_id}`} className={styles.accion}>
                        {TITULO_ESTADO_TRABAJO[entrada.estado] ? "Revisar" : "Ver"}
                      </Link>
                      <BorrarTrabajo trabajoId={entrada.trabajo_id} estado={entrada.estado} enFila />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
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
  // La previsualizacion del revisor tambien queda en espera, pero nadie la
  // espera: se aparta para no hacerla pasar por la lista de un acudiente.
  const previsualizaciones = trabajosEnEspera.filter((e) => e.origen === "preview_onboarding");
  const trabajosAcudiente = trabajosEnEspera.filter((e) => e.origen !== "preview_onboarding");

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
              <dd className="cifra">{trabajosAcudiente.length}</dd>
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
                        <div className={styles.accionesFila}>
                          <Link
                            href={`/onboarding/${encodeURIComponent(v.version_id)}`}
                            className={styles.accion}
                          >
                            Revisar
                          </Link>
                          <BorrarVersionLista
                            versionId={v.version_id}
                            grado={v.grado}
                            acudienteEsperando={Boolean(v.tiene_contacto)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {trabajosAcudiente.length > 0 ? (
            <TablaTrabajos
              titulo="Trabajos de acudiente en espera"
              bajada="Listas que subió un acudiente y esperan revisión. Cada una se revisa contra la versión de su colegio y grado."
              entradas={trabajosAcudiente}
              nombreColegio={nombreColegio}
              ahora={ahora}
            />
          ) : null}

          {previsualizaciones.length > 0 ? (
            <TablaTrabajos
              titulo="Previsualizaciones abiertas"
              bajada="Los kits que se armaron al pulsar «Previsualizar» en el revisor de una lista. Ningún acudiente los espera: queda una por colegio y grado, y se pueden eliminar sin problema."
              entradas={previsualizaciones}
              nombreColegio={nombreColegio}
              ahora={ahora}
              tenue
            />
          ) : null}
        </>
      )}
    </div>
  );
}
