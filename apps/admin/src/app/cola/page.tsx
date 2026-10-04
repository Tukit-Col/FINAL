// `/cola` — la cola de revision unificada (AD-01, AD-03).
//
// El item de la cola es una VERSION DE LISTA pendiente (`revisada=false`): el
// mismo acto —revisar "la lista del colegio X, grado Y"— sin importar si la
// envio el colegio (onboarding) o la subio un acudiente (sugerencia_padre).
// Revisar una version abre el revisor de cuatro paneles; aprobarla la vuelve
// lista oficial verificada y la reusa el pipeline para todos los acudientes de
// ese (colegio, grado).
//
// La pantalla se lee de arriba abajo por urgencia:
//   1. Lo que un acudiente espera (versiones con contacto y trabajos de
//      acudiente): tarjetas grandes, porque aprobarlas dispara un kit.
//   2. El resto de versiones, AGRUPADAS POR COLEGIO: un colegio que envio sus
//      quince grados es un bloque con quince fichas de grado en orden
//      pedagogico, no quince filas que repiten el mismo nombre.
//   3. Las previsualizaciones del revisor, plegadas: nadie las espera.
//
// Server Component: lee el origen directamente. No hay `fetch` de por medio
// porque la lectura no pasa por el navegador.

import Link from "next/link";
import type { EntradaCola, VersionListaAdmin } from "@tukit/contrato";
import { GRADOS_CANONICOS } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import BorrarTrabajo from "@/components/BorrarTrabajo";
import BorrarVersionLista from "@/components/BorrarVersionLista";
import { formatearFecha, haceCuanto } from "@/lib/formato";
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

function etiquetaIngreso(v: VersionListaAdmin): string {
  return v.procedencia ? ETIQUETA_INGRESO[v.procedencia] : "Sin procedencia";
}

// Un grado fuera de la lista canonica va al final, en orden alfabetico.
function ordenGrado(a: string, b: string): number {
  const ia = GRADOS_CANONICOS.indexOf(a);
  const ib = GRADOS_CANONICOS.indexOf(b);
  if (ia === -1 && ib === -1) return a.localeCompare(b);
  if (ia === -1) return 1;
  if (ib === -1) return -1;
  return ia - ib;
}

/** Agrupa por clave conservando el orden de primera aparicion. */
function agrupar<T>(elementos: readonly T[], clave: (e: T) => string): Map<string, T[]> {
  const grupos = new Map<string, T[]>();
  for (const e of elementos) {
    const k = clave(e);
    const actual = grupos.get(k);
    if (actual) actual.push(e);
    else grupos.set(k, [e]);
  }
  return grupos;
}

/** El valor si todos lo comparten; si no, `null` y cada ficha dice el suyo. */
function comun<T>(elementos: readonly T[], valor: (e: T) => string): string | null {
  const primero = elementos[0];
  if (primero === undefined) return null;
  const v = valor(primero);
  return elementos.every((e) => valor(e) === v) ? v : null;
}

function cifra(n: number): string {
  return n.toLocaleString("es-CO");
}

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

function Pendientes({ n }: { n: number }) {
  return n > 0 ? (
    <span className={styles.pendientes}>
      {n} por resolver
    </span>
  ) : (
    <span className={styles.cero}>Nada por resolver</span>
  );
}

// ---------------------------------------------------------- 1. lo urgente

function TarjetaVersionUrgente({ v, nombre }: { v: VersionListaAdmin; nombre: string }) {
  const href = `/onboarding/${encodeURIComponent(v.version_id)}`;
  return (
    <article className={styles.urgente}>
      <div className={styles.urgenteCuerpo}>
        <span className={styles.urgenteEtiqueta}>{etiquetaIngreso(v)}</span>
        <Link href={href} className={styles.urgenteTitulo}>
          {nombre}
        </Link>
        <span className={styles.urgenteMeta}>
          <strong>{v.grado}</strong> · {v.anio_lectivo} · <span className="cifra">{v.items}</span>{" "}
          renglones
        </span>
      </div>
      <div className={styles.accionesFila}>
        <Link href={href} className={styles.accion}>
          Revisar
        </Link>
        <BorrarVersionLista versionId={v.version_id} grado={v.grado} acudienteEsperando />
      </div>
    </article>
  );
}

function TarjetaTrabajoUrgente({
  entrada,
  nombreColegio,
  ahora,
}: {
  entrada: EntradaCola;
  nombreColegio: Map<string, string>;
  ahora: number;
}) {
  const colegios = entrada.colegios.map((id) => nombreColegio.get(id) ?? id).join(", ");
  const href = `/trabajos/${entrada.trabajo_id}`;
  return (
    <article className={styles.urgente}>
      <div className={styles.urgenteCuerpo}>
        <span className={styles.urgenteEtiqueta}>
          Trabajo de acudiente ·{" "}
          <span title={formatearFecha(entrada.recibido_en)}>
            {haceCuanto(entrada.recibido_en, ahora)}
          </span>
        </span>
        <Link href={href} className={styles.urgenteTitulo} title={entrada.trabajo_id}>
          {colegios || "Colegio sin identificar"}
        </Link>
        <span className={styles.urgenteMeta}>
          <strong>{entrada.grados.join(", ") || "Grado sin identificar"}</strong> ·{" "}
          <Pendientes n={entrada.lineas_pendientes} />
        </span>
      </div>
      <div className={styles.accionesFila}>
        <Link href={href} className={styles.accion}>
          Revisar
        </Link>
        <BorrarTrabajo trabajoId={entrada.trabajo_id} estado={entrada.estado} enFila />
      </div>
    </article>
  );
}

// ------------------------------------------------ 2. versiones por colegio

function BloqueColegio({
  nombre,
  versiones,
}: {
  nombre: string;
  versiones: VersionListaAdmin[];
}) {
  const ordenadas = [...versiones].sort((a, b) => ordenGrado(a.grado, b.grado));
  const renglones = versiones.reduce((suma, v) => suma + v.items, 0);
  const ingreso = comun(versiones, etiquetaIngreso);
  const anio = comun(versiones, (v) => String(v.anio_lectivo));
  return (
    <section className={styles.colegio}>
      <header className={styles.colegioCabecera}>
        <h3 className={styles.colegioNombre}>{nombre}</h3>
        <span className={styles.colegioMeta}>
          <span className="cifra">{versiones.length}</span>{" "}
          {versiones.length === 1 ? "lista" : "listas"} ·{" "}
          <span className="cifra">{cifra(renglones)}</span> renglones
          {anio ? ` · ${anio}` : null}
        </span>
        {ingreso ? <span className={styles.estado}>{ingreso}</span> : null}
      </header>
      <ul className={styles.grados}>
        {ordenadas.map((v) => {
          const href = `/onboarding/${encodeURIComponent(v.version_id)}`;
          return (
            <li key={v.version_id} className={styles.grado}>
              <Link href={href} className={styles.gradoEnlace}>
                <span className={styles.gradoNombre}>{v.grado}</span>
                <span className={styles.gradoMeta}>
                  <span className="cifra">{v.items}</span> renglones
                  {anio ? null : ` · ${v.anio_lectivo}`}
                </span>
                {ingreso ? null : <span className={styles.gradoMeta}>{etiquetaIngreso(v)}</span>}
              </Link>
              <div className={styles.gradoAcciones}>
                <Link href={href} className={styles.accionChica}>
                  Revisar
                </Link>
                <BorrarVersionLista
                  versionId={v.version_id}
                  grado={v.grado}
                  acudienteEsperando={false}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// ------------------------------------------------- 3. previsualizaciones

function Previsualizaciones({
  entradas,
  nombreColegio,
  ahora,
}: {
  entradas: EntradaCola[];
  nombreColegio: Map<string, string>;
  ahora: number;
}) {
  const porColegio = agrupar(entradas, (e) =>
    e.colegios.map((id) => nombreColegio.get(id) ?? id).join(", ") || "Sin identificar",
  );
  return (
    <details className={styles.plegable}>
      <summary className={styles.plegableTitulo}>
        <span>Previsualizaciones abiertas</span>
        <span className={styles.conteo}>{entradas.length}</span>
        <span className={styles.plegablePista}>
          Kits de prueba armados con «Previsualizar». Ningún acudiente los espera: se pueden
          eliminar sin problema.
        </span>
      </summary>
      <div className={styles.plegableCuerpo}>
        {[...porColegio].map(([nombre, grupo]) => (
          <section key={nombre} className={styles.colegio}>
            <header className={styles.colegioCabecera}>
              <h3 className={styles.colegioNombre}>{nombre}</h3>
              <span className={styles.colegioMeta}>
                <span className="cifra">{grupo.length}</span>{" "}
                {grupo.length === 1 ? "previsualización" : "previsualizaciones"}
              </span>
            </header>
            <ul className={styles.grados}>
              {[...grupo]
                .sort((a, b) => ordenGrado(a.grados[0] ?? "", b.grados[0] ?? ""))
                .map((e) => {
                  const href = `/trabajos/${e.trabajo_id}`;
                  return (
                    <li key={e.trabajo_id} className={styles.grado}>
                      <Link href={href} className={styles.gradoEnlace} title={e.trabajo_id}>
                        <span className={styles.gradoNombre}>
                          {e.grados.join(", ") || "—"}
                        </span>
                        <span className={styles.gradoMeta}>
                          <span title={formatearFecha(e.recibido_en)}>
                            {haceCuanto(e.recibido_en, ahora)}
                          </span>{" "}
                          · <code>#{e.trabajo_id.slice(0, 8)}</code>
                        </span>
                        <Pendientes n={e.lineas_pendientes} />
                      </Link>
                      <div className={styles.gradoAcciones}>
                        <Link href={href} className={styles.accionChica}>
                          Abrir
                        </Link>
                        <BorrarTrabajo trabajoId={e.trabajo_id} estado={e.estado} enFila />
                      </div>
                    </li>
                  );
                })}
            </ul>
          </section>
        ))}
      </div>
    </details>
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
  const nombreDe = (v: VersionListaAdmin): string =>
    nombreColegio.get(v.colegio_id) ?? v.colegio_nombre ?? v.colegio_id;

  // Un solo reloj para toda la página: si cada fila llamara a `Date.now()`, dos
  // filas del mismo instante podrían mostrar minutos distintos.
  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  // Lo que un acudiente espera va aparte y primero (aprobar dispara su kit);
  // el resto se agrupa por colegio, con el colegio de más renglones arriba.
  const conAcudiente = pendientes
    .filter((v) => v.tiene_contacto)
    .sort((a, b) => b.items - a.items);
  const sinAcudiente = pendientes.filter((v) => !v.tiene_contacto);
  const porColegio = [...agrupar(sinAcudiente, (v) => v.colegio_id).values()].sort(
    (a, b) =>
      b.reduce((s, v) => s + v.items, 0) - a.reduce((s, v) => s + v.items, 0),
  );

  // Solo los trabajos que esperan una persona: lo publicado es historial y lo
  // que aún procesa no necesita acción. Un trabajo es el ingreso de acudiente
  // sin migrar; se muestra aparte, no mezclado con las versiones.
  const trabajosEnEspera = entradas.filter((e) => e.estado === "espera_revision");
  // La previsualizacion del revisor tambien queda en espera, pero nadie la
  // espera: se aparta para no hacerla pasar por la lista de un acudiente.
  const previsualizaciones = trabajosEnEspera.filter((e) => e.origen === "preview_onboarding");
  const trabajosAcudiente = trabajosEnEspera.filter((e) => e.origen !== "preview_onboarding");

  const esperando = conAcudiente.length + trabajosAcudiente.length;

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
              <dd className="cifra">{pendientes.length}</dd>
            </div>
            <div className={esperando > 0 ? styles.resumenAviso : undefined}>
              <dt>Acudientes esperando</dt>
              <dd className="cifra">{esperando}</dd>
            </div>
            <div>
              <dt>Colegios</dt>
              <dd className="cifra">
                {new Set(pendientes.map((v) => v.colegio_id)).size}
              </dd>
            </div>
          </dl>
        </div>
      </header>

      {pendientes.length === 0 && trabajosEnEspera.length === 0 ? (
        <ColaVacia />
      ) : (
        <>
          {esperando > 0 ? (
            <section className={styles.bloque}>
              <h2 className={styles.subtitulo}>
                Un acudiente está esperando
                <span className={`${styles.conteo} ${styles.conteoAviso}`}>{esperando}</span>
              </h2>
              <p className={styles.bajada}>
                Aprobar estas listas arma el kit que el acudiente está esperando. Van primero.
              </p>
              <div className={styles.urgentes}>
                {conAcudiente.map((v) => (
                  <TarjetaVersionUrgente key={v.version_id} v={v} nombre={nombreDe(v)} />
                ))}
                {trabajosAcudiente.map((e) => (
                  <TarjetaTrabajoUrgente
                    key={e.trabajo_id}
                    entrada={e}
                    nombreColegio={nombreColegio}
                    ahora={ahora}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {porColegio.length > 0 ? (
            <section className={styles.bloque}>
              <h2 className={styles.subtitulo}>
                Listas por verificar
                <span className={styles.conteo}>{sinAcudiente.length}</span>
              </h2>
              <p className={styles.bajada}>
                Agrupadas por colegio y en orden de grado. Nadie las espera todavía, pero
                aprobarlas deja la lista lista para el próximo acudiente.
              </p>
              {porColegio.map((grupo) => (
                <BloqueColegio
                  key={grupo[0]!.colegio_id}
                  nombre={nombreDe(grupo[0]!)}
                  versiones={grupo}
                />
              ))}
            </section>
          ) : null}

          {previsualizaciones.length > 0 ? (
            <Previsualizaciones
              entradas={previsualizaciones}
              nombreColegio={nombreColegio}
              ahora={ahora}
            />
          ) : null}
        </>
      )}
    </div>
  );
}
