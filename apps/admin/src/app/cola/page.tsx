// `/cola`: la cola de revisión unificada.
//
// Decisiones:
// - El ítem de la cola es una versión de lista pendiente, sin importar si la envió el colegio o la subió
//   un acudiente. Aprobarla la vuelve lista oficial verificada y el pipeline la reusa para todos los
//   acudientes de ese colegio y grado.
// - La pantalla se lee de arriba abajo por urgencia: primero lo que un acudiente espera (tarjetas
//   grandes, porque aprobarlas dispara un kit) y luego el resto de versiones agrupadas por colegio, con
//   los grados en orden pedagógico.

import Link from "next/link";
import type { EntradaCola, VersionListaAdmin } from "@tukit/contrato";
import { GRADOS_CANONICOS } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import BorrarTrabajo from "@/components/BorrarTrabajo";
import AvisoAcceso from "@/components/AvisoAcceso";
import BorrarVersionLista from "@/components/BorrarVersionLista";
import { formatearFecha, haceCuanto } from "@/lib/formato";
import { motivoDeAcceso } from "@/lib/logistica";
import {
  agruparPorColegio,
  filtrarVersiones,
  hayFiltros,
  hrefCola,
  leerFiltrosCola,
  normalizar,
  paginar,
  type FiltrosCola,
  type GrupoColegio,
} from "@/lib/cola";
import SubirLista from "./SubirLista";
import styles from "./Cola.module.css";

export const dynamic = "force-dynamic";

const ETIQUETA_INGRESO: Record<NonNullable<VersionListaAdmin["procedencia"]>, string> = {
  onboarding: "El colegio la envió",
  sugerencia_padre: "Un acudiente la subió",
};

function etiquetaIngreso(v: VersionListaAdmin): string {
  return v.procedencia ? ETIQUETA_INGRESO[v.procedencia] : "Sin procedencia";
}

function ordenGrado(a: string, b: string): number {
  const ia = GRADOS_CANONICOS.indexOf(a);
  const ib = GRADOS_CANONICOS.indexOf(b);
  if (ia === -1 && ib === -1) return a.localeCompare(b);
  if (ia === -1) return 1;
  if (ib === -1) return -1;
  return ia - ib;
}

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

function BloqueColegio({
  grupo,
  abierto,
}: {
  grupo: GrupoColegio<VersionListaAdmin>;
  abierto: boolean;
}) {
  const { versiones, nombre, esperando, renglones } = grupo;
  const ingreso = comun(versiones, etiquetaIngreso);
  const anio = comun(versiones, (v) => String(v.anio_lectivo));
  const siguiente = versiones[0]!;
  const hrefSiguiente = `/onboarding/${encodeURIComponent(siguiente.version_id)}`;
  return (
    <details className={styles.colegio} open={abierto}>
      <summary className={styles.colegioCabecera}>
        <span className={styles.colegioNombre}>{nombre}</span>
        <span className={styles.colegioMeta}>
          <span className="cifra">{versiones.length}</span>{" "}
          {versiones.length === 1 ? "lista" : "listas"} ·{" "}
          <span className="cifra">{cifra(renglones)}</span> renglones
          {anio ? ` · ${anio}` : null}
        </span>
        {esperando > 0 ? (
          <span className={`${styles.conteo} ${styles.conteoAviso}`}>
            {esperando} {esperando === 1 ? "acudiente espera" : "acudientes esperan"}
          </span>
        ) : ingreso ? (
          <span className={styles.estado}>{ingreso}</span>
        ) : null}
        <Link href={hrefSiguiente} className={styles.accionChica} title={`${siguiente.grado}`}>
          Revisar siguiente
        </Link>
      </summary>
      <ul className={styles.grados}>
        {versiones.map((v) => {
          const href = `/onboarding/${encodeURIComponent(v.version_id)}`;
          return (
            <li key={v.version_id} className={styles.grado}>
              <Link href={href} className={styles.gradoEnlace}>
                <span className={styles.gradoNombre}>{v.grado}</span>
                <span className={styles.gradoMeta}>
                  <span className="cifra">{v.items}</span> renglones
                  {anio ? null : ` · ${v.anio_lectivo}`}
                </span>
                {v.tiene_contacto ? (
                  <span className={styles.gradoMeta}>Acudiente esperando</span>
                ) : ingreso ? null : (
                  <span className={styles.gradoMeta}>{etiquetaIngreso(v)}</span>
                )}
              </Link>
              <div className={styles.gradoAcciones}>
                <Link href={href} className={styles.accionChica}>
                  Revisar
                </Link>
                <BorrarVersionLista
                  versionId={v.version_id}
                  grado={v.grado}
                  acudienteEsperando={v.tiene_contacto}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

function BarraFiltros({
  f,
  grados,
  anios,
}: {
  f: FiltrosCola;
  grados: string[];
  anios: number[];
}) {
  return (
    <form method="get" action="/cola" className={styles.filtros} role="search">
      <label className={styles.campoFiltro}>
        <span>Buscar colegio</span>
        <input type="search" name="q" defaultValue={f.q} placeholder="Nombre del colegio" />
      </label>
      <label className={styles.campoFiltro}>
        <span>Grado</span>
        <select name="grado" defaultValue={f.grado}>
          <option value="">Todos</option>
          {grados.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.campoFiltro}>
        <span>Año</span>
        <select name="anio" defaultValue={f.anio ?? ""}>
          <option value="">Todos</option>
          {anios.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.campoFiltro}>
        <span>Origen</span>
        <select name="origen" defaultValue={f.origen}>
          <option value="todos">Todos</option>
          <option value="acudiente">Acudiente esperando</option>
          <option value="colegio">Colegio / sin acudiente</option>
        </select>
      </label>
      <button type="submit" className={styles.filtrar}>
        Filtrar
      </button>
      {hayFiltros(f) ? (
        <Link href="/cola" className={styles.limpiar}>
          Limpiar
        </Link>
      ) : null}
    </form>
  );
}

function Paginacion({ f, pagina, paginas }: { f: FiltrosCola; pagina: number; paginas: number }) {
  if (paginas <= 1) return null;
  return (
    <nav className={styles.paginacion} aria-label="Paginación de colegios">
      {pagina > 1 ? (
        <Link href={hrefCola(f, pagina - 1)} className={styles.accionChica}>
          Anterior
        </Link>
      ) : null}
      <span className={styles.paginaActual}>
        Página <span className="cifra">{pagina}</span> de <span className="cifra">{paginas}</span>
      </span>
      {pagina < paginas ? (
        <Link href={hrefCola(f, pagina + 1)} className={styles.accionChica}>
          Siguiente
        </Link>
      ) : null}
    </nav>
  );
}

function Previsualizaciones({
  entradas,
  nombreColegio,
  ahora,
  edicion = false,
}: {
  entradas: EntradaCola[];
  nombreColegio: Map<string, string>;
  ahora: number;
  edicion?: boolean;
}) {
  const porColegio = agrupar(entradas, (e) =>
    e.colegios.map((id) => nombreColegio.get(id) ?? id).join(", ") || "Sin identificar",
  );
  return (
    <details className={styles.plegable}>
      <summary className={styles.plegableTitulo}>
        <span>{edicion ? "Ediciones de kits abiertas" : "Previsualizaciones abiertas"}</span>
        <span className={styles.conteo}>{entradas.length}</span>
        <span className={styles.plegablePista}>
          {edicion
            ? "Versiones nuevas de kits ya publicados, abiertas con «Editar kits». Los kits vigentes no cambian hasta publicarlas; descartarlas no toca nada."
            : "Kits de prueba armados con «Previsualizar». Ningún acudiente los espera: se pueden eliminar sin problema."}
        </span>
      </summary>
      <div className={styles.plegableCuerpo}>
        {[...porColegio].map(([nombre, grupo]) => (
          <section key={nombre} className={styles.colegio}>
            <header className={styles.colegioCabecera}>
              <h3 className={styles.colegioNombre}>{nombre}</h3>
              <span className={styles.colegioMeta}>
                <span className="cifra">{grupo.length}</span>{" "}
                {edicion
                  ? grupo.length === 1
                    ? "edición"
                    : "ediciones"
                  : grupo.length === 1
                    ? "previsualización"
                    : "previsualizaciones"}
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

const MAX_URGENTES = 12;

export default async function PaginaCola({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const filtros = leerFiltrosCola(await searchParams);
  let lecturas;
  try {
    lecturas = await Promise.all([
      origenDeDatos().listasAdmin({ revisada: false }),
      origenDeDatos().cola(),
      origenDeDatos().colegios(),
    ]);
  } catch (causa) {
    const motivo = motivoDeAcceso(causa);
    if (motivo) return <AvisoAcceso motivo={motivo} mensaje={(causa as Error).message} />;
    throw causa;
  }
  const [pendientes, { entradas }, colegios] = lecturas;

  const nombreColegio = new Map(colegios.map((c) => [c.colegio_id, c.nombre]));
  const nombreDe = (v: VersionListaAdmin): string =>
    nombreColegio.get(v.colegio_id) ?? v.colegio_nombre ?? v.colegio_id;

  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  const filtradas = filtrarVersiones(pendientes, filtros, nombreDe);
  const conAcudiente = filtradas
    .filter((v) => v.tiene_contacto)
    .sort((a, b) => b.items - a.items);
  const grupos = agruparPorColegio(filtradas, nombreDe, ordenGrado);
  const pag = paginar(grupos, filtros.pagina);
  const grados = [...new Set(pendientes.map((v) => v.grado))].sort(ordenGrado);
  const anios = [...new Set(pendientes.map((v) => v.anio_lectivo))].sort((a, b) => b - a);

  const trabajosEnEspera = entradas.filter((e) => e.estado === "espera_revision");
  const previsualizaciones = trabajosEnEspera.filter((e) => e.origen === "preview_onboarding");
  const ediciones = trabajosEnEspera.filter((e) => e.edicion_de);
  const qNorm = normalizar(filtros.q);
  const trabajosAcudiente = trabajosEnEspera.filter(
    (e) =>
      e.origen !== "preview_onboarding" &&
      !e.edicion_de &&
      filtros.origen !== "colegio" &&
      (!filtros.grado || e.grados.includes(filtros.grado)) &&
      (!qNorm ||
        normalizar(e.colegios.map((id) => nombreColegio.get(id) ?? id).join(" ")).includes(qNorm)),
  );

  const esperando =
    pendientes.filter((v) => v.tiene_contacto).length +
    trabajosEnEspera.filter((e) => e.origen !== "preview_onboarding" && !e.edicion_de).length;
  const urgentesVisibles = conAcudiente.length + trabajosAcudiente.length;

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
          <BarraFiltros f={filtros} grados={grados} anios={anios} />

          {urgentesVisibles > 0 && pag.pagina === 1 ? (
            <section className={styles.bloque}>
              <h2 className={styles.subtitulo}>
                Un acudiente está esperando
                <span className={`${styles.conteo} ${styles.conteoAviso}`}>{urgentesVisibles}</span>
              </h2>
              <p className={styles.bajada}>
                Aprobar estas listas arma el kit que el acudiente está esperando. Van primero.
              </p>
              <div className={styles.urgentes}>
                {conAcudiente.slice(0, MAX_URGENTES).map((v) => (
                  <TarjetaVersionUrgente key={v.version_id} v={v} nombre={nombreDe(v)} />
                ))}
                {trabajosAcudiente.slice(0, Math.max(0, MAX_URGENTES - conAcudiente.length)).map((e) => (
                  <TarjetaTrabajoUrgente
                    key={e.trabajo_id}
                    entrada={e}
                    nombreColegio={nombreColegio}
                    ahora={ahora}
                  />
                ))}
              </div>
              {urgentesVisibles > MAX_URGENTES ? (
                <p className={styles.bajada}>
                  Se muestran {MAX_URGENTES} de {urgentesVisibles}. Los demás están dentro de su
                  colegio, abajo, o filtra por «Acudiente esperando».
                </p>
              ) : null}
            </section>
          ) : null}

          <section className={styles.bloque}>
            <h2 className={styles.subtitulo}>
              Listas por verificar, por colegio
              <span className={styles.conteo}>{filtradas.length}</span>
            </h2>
            <p className={styles.bajada}>
              {hayFiltros(filtros)
                ? `${cifra(grupos.length)} colegios con resultados.`
                : "Con acudiente esperando primero, luego por nombre."}{" "}
              Abre un colegio para ver sus grados, o usa «Revisar siguiente».
            </p>
            {grupos.length === 0 ? (
              <p className={styles.sinResultados}>
                Ninguna lista coincide con estos filtros.{" "}
                <Link href="/cola" className={styles.enlaceExterno}>
                  Limpiar filtros
                </Link>
              </p>
            ) : null}
            {pag.items.map((g) => (
              <BloqueColegio key={g.colegio_id} grupo={g} abierto={pag.total <= 3} />
            ))}
            <Paginacion f={filtros} pagina={pag.pagina} paginas={pag.paginas} />
          </section>

          {ediciones.length > 0 ? (
            <Previsualizaciones
              entradas={ediciones}
              nombreColegio={nombreColegio}
              ahora={ahora}
              edicion
            />
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
