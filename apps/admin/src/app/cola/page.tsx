// `/cola` — la cola de revision unificada (AD-01, AD-03).
//
// Dos secciones (ver `lib/cola`):
//  - "Listas por verificar": una fila por version de lista pendiente, la envie
//    el colegio o la suba un acudiente. Su vista previa no es otra fila: es el
//    estado de esa lista ("Sin vista previa", "Vista previa: N dudosas", "Lista
//    para aprobar"). El kit del grado que queda en espera tras aprobar una lista
//    tambien va aqui ("Lista verificada · kit con N dudosas").
//  - "Kits de acudientes por aprobar": los trabajos con un acudiente dueño que
//    esperan revision, con su correo (identidad) y los nombres de sus colegios.
//
// Server Component: lee el origen directamente. No hay `fetch` de por medio
// porque la lectura no pasa por el navegador.

import Link from "next/link";
import type { ReactNode } from "react";
import type { EntradaCola, VersionListaAdmin } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import BorrarTrabajo from "@/components/BorrarTrabajo";
import BorrarVersion from "@/components/BorrarVersion";
import { armarCola, textoEstadoLista, type FilaLista } from "@/lib/cola";
import { formatearFecha, haceCuanto } from "@/lib/formato";
import { tokenDeSesion } from "@/lib/sesion";
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

// Los correos de los acudientes, para nombrarlos en la cola. El padron es
// solo para staff: sin sesion, o si identidad no responde, se degrada al id
// del usuario en vez de tumbar la cola.
async function correosDe(ids: string[]): Promise<Map<string, string>> {
  const token = await tokenDeSesion();
  if (!token || ids.length === 0) return new Map();
  const acudientes = await origenDeDatos()
    .acudientesAdmin(token, ids)
    .catch(() => []);
  return new Map(acudientes.map((a) => [a.usuario_id, a.correo]));
}

export default async function PaginaCola() {
  // Las versiones PENDIENTES (el item de la primera seccion), los trabajos en
  // espera (vistas previas, kits del grado y kits de acudientes) y los colegios
  // para dar el nombre legible de cada `colegio_id`.
  const [pendientes, { entradas }, colegios] = await Promise.all([
    origenDeDatos().listasAdmin({ revisada: false }),
    origenDeDatos().cola(),
    origenDeDatos().colegios(),
  ]);

  const nombreColegio = new Map(colegios.map((c) => [c.colegio_id, c.nombre]));
  const { porVerificar, deAcudientes, conteos } = armarCola({ versiones: pendientes, entradas });
  const correos = await correosDe([
    ...new Set(deAcudientes.flatMap((e) => (e.usuario_id ? [e.usuario_id] : []))),
  ]);

  // Un solo reloj para toda la página: si cada fila llamara a `Date.now()`, dos
  // filas del mismo instante podrían mostrar minutos distintos.
  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  const conAcudiente = porVerificar.filter((f) => f.conAcudiente).length;

  function colegioDeFila(fila: FilaLista) {
    if (fila.version) {
      return (
        nombreColegio.get(fila.version.colegio_id) ??
        fila.version.colegio_nombre ?? <code>{fila.version.colegio_id}</code>
      );
    }
    const id = fila.kitDelGrado?.colegios[0];
    return id ? (nombreColegio.get(id) ?? <code>{id}</code>) : "—";
  }

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
              <dd className="cifra">{conteos.listasPorVerificar}</dd>
            </div>
            <div>
              <dt>Con acudiente esperando</dt>
              <dd className="cifra">{conAcudiente}</dd>
            </div>
            <div>
              <dt>Kits de acudientes por aprobar</dt>
              <dd className="cifra">{conteos.kitsDeAcudientes}</dd>
            </div>
          </dl>
        </div>
      </header>

      {porVerificar.length === 0 && deAcudientes.length === 0 ? (
        <ColaVacia />
      ) : (
        <>
          <section className={styles.bloqueTrabajos}>
            <h2 className={styles.subtitulo}>Listas por verificar</h2>
            {porVerificar.length > 0 ? (
              <div className={styles.marco}>
                <table className={styles.tabla}>
                  <caption className={styles.leyenda}>
                    Una fila por lista pendiente. Primero las que tienen un acudiente
                    esperando —aprobarlas dispara su kit—, después por renglones.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Colegio</th>
                      <th scope="col">Grado</th>
                      <th scope="col">Ingreso</th>
                      <th scope="col">Estado</th>
                      <th scope="col" className={styles.num}>
                        Renglones
                      </th>
                      <th scope="col">
                        <span className={styles.oculto}>Acción</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {porVerificar.map((fila) => (
                      <FilaDeLista
                        key={fila.version?.version_id ?? fila.kitDelGrado?.trabajo_id}
                        fila={fila}
                        colegio={colegioDeFila(fila)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className={styles.bajada}>No hay listas por verificar.</p>
            )}
          </section>

          <section className={styles.bloqueTrabajos}>
            <h2 className={styles.subtitulo}>Kits de acudientes por aprobar</h2>
            {deAcudientes.length > 0 ? (
              <div className={styles.marco}>
                <table className={styles.tabla}>
                  <thead>
                    <tr>
                      <th scope="col">Acudiente</th>
                      <th scope="col">Recibido</th>
                      <th scope="col">Colegios</th>
                      <th scope="col">Grados</th>
                      <th scope="col" className={styles.num}>
                        Dudosas
                      </th>
                      <th scope="col">
                        <span className={styles.oculto}>Acción</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {deAcudientes.map((entrada: EntradaCola) => (
                      <tr key={entrada.trabajo_id} className={styles.filaEspera}>
                        <th scope="row" className={styles.identificador}>
                          <Link href={`/trabajos/${entrada.trabajo_id}`}>
                            {entrada.usuario_id ? (
                              (correos.get(entrada.usuario_id) ?? (
                                <code>{entrada.usuario_id.slice(0, 8).toUpperCase()}</code>
                              ))
                            ) : (
                              <code>{entrada.trabajo_id.slice(0, 8).toUpperCase()}</code>
                            )}
                          </Link>
                        </th>
                        <td className={styles.fecha}>
                          <span>{haceCuanto(entrada.recibido_en, ahora)}</span>
                          <span className={styles.fechaExacta}>
                            {formatearFecha(entrada.recibido_en)}
                          </span>
                        </td>
                        <td className={styles.lista}>
                          {entrada.colegios.map((id) => nombreColegio.get(id) ?? id).join(", ") ||
                            "—"}
                        </td>
                        <td className={styles.lista}>{entrada.grados.join(", ") || "—"}</td>
                        <td className={`${styles.num} cifra`}>
                          {entrada.lineas_sin_decidir > 0 ? (
                            <span className={styles.pendientes}>{entrada.lineas_sin_decidir}</span>
                          ) : (
                            <span className={styles.cero}>0</span>
                          )}
                        </td>
                        <td className={styles.accionCelda}>
                          <div className={styles.accionesFila}>
                            <Link href={`/trabajos/${entrada.trabajo_id}`} className={styles.accion}>
                              Revisar
                            </Link>
                            <BorrarTrabajo trabajoId={entrada.trabajo_id} estado={entrada.estado} />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className={styles.bajada}>No hay kits de acudientes esperando aprobación.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}

// Una lista por verificar. Las acciones dependen de lo que la fila tenga: la
// version se revisa en su revisor y se descarta entera; el kit del grado de una
// lista ya cerrada se revisa en la consola y se descarta como trabajo.
function FilaDeLista({ fila, colegio }: { fila: FilaLista; colegio: ReactNode }) {
  const { version, vistaPrevia, kitDelGrado } = fila;
  const kit = kitDelGrado ?? vistaPrevia;
  const revisar = version
    ? `/onboarding/${encodeURIComponent(version.version_id)}`
    : `/trabajos/${kitDelGrado!.trabajo_id}`;
  const esperando = kitDelGrado?.acudientes_esperando ?? 0;
  return (
    <tr className={fila.conAcudiente ? styles.filaEspera : ""}>
      <th scope="row" className={styles.identificador}>
        <Link href={revisar}>{colegio}</Link>
      </th>
      <td>{version?.grado ?? kitDelGrado?.grados.join(", ") ?? "—"}</td>
      <td>
        <span className={styles.estado}>
          {version
            ? version.procedencia
              ? ETIQUETA_INGRESO[version.procedencia]
              : "Sin procedencia"
            : "Lista ya aprobada"}
        </span>
        {version?.tiene_contacto ? (
          <span className={styles.pistaContacto}> · acudiente esperando</span>
        ) : null}
        {esperando > 0 ? (
          <span className={styles.pistaContacto}>
            {" "}
            · {esperando} {esperando === 1 ? "acudiente esperando" : "acudientes esperando"}
          </span>
        ) : null}
      </td>
      <td>{textoEstadoLista(fila.estado)}</td>
      <td className={`${styles.num} cifra`}>
        {version?.items ?? kitDelGrado?.lineas_totales ?? "—"}
      </td>
      <td className={styles.accionCelda}>
        <div className={styles.accionesFila}>
          <Link href={revisar} className={styles.accion}>
            Revisar
          </Link>
          {kit ? (
            <Link href={`/trabajos/${kit.trabajo_id}`} className={styles.accionSecundaria}>
              Ver kits
            </Link>
          ) : null}
          {version ? (
            <BorrarVersion versionId={version.version_id} />
          ) : (
            <BorrarTrabajo trabajoId={kitDelGrado!.trabajo_id} estado={kitDelGrado!.estado} />
          )}
        </div>
      </td>
    </tr>
  );
}
