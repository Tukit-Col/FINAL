import { cookies } from "next/headers";
import Form from "next/form";
import Link from "next/link";
import { origenDeDatos, ErrorTukit, type AcudienteAdmin } from "@tukit/contrato/servidor";
import { ETIQUETA_ESTADO_PEDIDO, logoDeColegio, type EstadoPedido } from "@tukit/contrato";
import { imagenesDelDirectorio } from "@/lib/directorio";
import { COOKIE_SESION } from "@/lib/sesion";
import { formatearFecha } from "@/lib/formato";
import { rotuloDeHijo } from "@/lib/pedido-admin";
import {
  clientesPorColegio,
  esCuentaDePrueba,
  filtrarClientes,
  hayFiltrosClientes,
  hrefClientes,
  leerFiltrosClientes,
  opcionesClientes,
  paginar,
  pedidosPorFamilia,
  type PedidoDeFamilia,
} from "@/lib/clientes";
import { hrefCliente } from "@/lib/cliente-detalle";
import EstadoVacio from "@/components/ui/EstadoVacio";
import ui from "@/components/ui/ui.module.css";
import styles from "./Clientes.module.css";

export const dynamic = "force-dynamic";

// El padrón de familias registradas. Vive detrás del token: identidad gatea el
// endpoint (401 sin token, 403 sin rol admin/operador), así que esta página lee
// la cookie de sesión —la misma que puso la web al entrar— y la pasa como
// Bearer. Sin sesión o sin permiso NO se muestra un error crudo, sino un aviso
// claro. No muestra ningún dato que identifique a un menor (ni apodo): Ley 1581.

/** El aviso de guardia: nunca un stack trace, siempre una frase que dice qué
 *  hacer. Cubre "no hay sesión", "la sesión expiró" y "no tienes el rol". */
function Aviso({ titulo, cuerpo }: { titulo: string; cuerpo: string }) {
  return (
    <div className={styles.pagina}>
      <div className={styles.aviso}>
        <h2>{titulo}</h2>
        <p>{cuerpo}</p>
      </div>
    </div>
  );
}

/** El texto de un hijo: un rótulo estable con su posición, grado y colegio. Ni
 *  apodo ni nombre de menor llegan a esta vista (Ley 1581). */
function textoHijo(hijo: AcudienteAdmin["hijos"][number], indice: number): string {
  return `${rotuloDeHijo(hijo, indice)} · ${hijo.colegio_nombre}`;
}

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function PaginaClientes({ searchParams }: Props) {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return (
      <Aviso
        titulo="Inicia sesión para ver a los clientes"
        cuerpo="Este padrón es solo para el equipo interno. Entra con tu cuenta de operador o admin y vuelve a esta pestaña."
      />
    );
  }

  let acudientes: AcudienteAdmin[];
  try {
    acudientes = await origenDeDatos().acudientesAdmin(token);
  } catch (error) {
    if (error instanceof ErrorTukit && error.estado === 401) {
      return (
        <Aviso
          titulo="Tu sesión expiró"
          cuerpo="Vuelve a entrar con tu cuenta para ver el padrón de clientes."
        />
      );
    }
    // El limite de tasa (ADR 0047): ni sesion vencida ni servicio caido. Su
    // mensaje ya dice cuanto esperar.
    if (error instanceof ErrorTukit && error.estado === 429) {
      return <Aviso titulo="Danos un momento" cuerpo={error.message} />;
    }
    if (error instanceof ErrorTukit && error.estado === 403) {
      return (
        <Aviso
          titulo="Esta vista es solo para el equipo interno"
          cuerpo="Tu cuenta no tiene el rol de operador o admin que este padrón requiere."
        />
      );
    }
    return (
      <Aviso
        titulo="No pudimos cargar el padrón"
        cuerpo="El servicio de identidad no respondió. Revisa que los servicios estén arriba (make arriba) e inténtalo de nuevo."
      />
    );
  }

  const filtros = leerFiltrosClientes(await searchParams);
  const filtrados = filtrarClientes(acudientes, filtros);
  const pagina = paginar(filtrados, filtros.pagina);
  const opciones = opcionesClientes(acudientes);
  const pruebas = acudientes.filter(esCuentaDePrueba).length;
  // Cuantas familias e hijos hay en cada colegio y grado, sobre el padron entero
  // (no sobre la pagina filtrada): es el mapa de donde estan los clientes.
  const porColegio = clientesPorColegio(acudientes);
  // El estado del pedido de cada familia (el tablero de comercio, solo staff). Si
  // comercio no responde, la columna sale vacia y el padron sigue.
  const tablero = await origenDeDatos().pedidos(token).catch(() => null);
  const pedidos = pedidosPorFamilia(tablero?.pedidos ?? []);
  // El logo de cada colegio (Identidad o el directorio de Bogota) y las cifras de arriba.
  const colegios = await origenDeDatos().colegios().catch(() => []);
  const logos = new Map(colegios.map((c) => [c.colegio_id, logoDeColegio(c, imagenesDelDirectorio())] as const));
  const hijosTotales = acudientes.reduce((n, a) => n + a.hijos.length, 0);
  const conPedido = acudientes.filter((a) => pedidos.has(a.usuario_id)).length;
  const entregados = acudientes.filter((a) => pedidos.get(a.usuario_id)?.estado === "entregado").length;
  const maxHijosColegio = Math.max(1, ...porColegio.map((c) => c.hijos));

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Clientes</h1>
          <p className={styles.bajada}>
            Las familias registradas en Tukit y los hijos que tienen matriculados. Del menor solo se
            muestra su posición, grado y colegio; ni apodo ni nombre legal.
          </p>
        </div>
        <dl className={styles.kpis}>
          <div>
            <dt>Familias</dt>
            <dd className="cifra">{acudientes.length}</dd>
          </div>
          <div>
            <dt>Hijos</dt>
            <dd className="cifra">{hijosTotales}</dd>
          </div>
          <div>
            <dt>Con pedido</dt>
            <dd className="cifra">{conPedido}</dd>
          </div>
          <div className={styles.kpiExito}>
            <dt>Entregados</dt>
            <dd className="cifra">{entregados}</dd>
          </div>
        </dl>
      </header>

      {porColegio.length > 0 && (
        <section className={styles.porColegio} aria-labelledby="titulo-por-colegio">
          <h2 id="titulo-por-colegio">Por colegio y grado</h2>
          <p className={styles.bajada}>
            Familias e hijos en cada colegio. Toca un colegio o un grado para filtrar la tabla.
          </p>
          <ul className={styles.tarjetasColegio}>
            {porColegio.map((c) => {
              const logo = logos.get(c.colegio_id) ?? null;
              const maxGrado = Math.max(1, ...c.grados.map((g) => g.hijos));
              return (
                <li key={c.colegio_id} className={styles.tarjetaColegio}>
                  <Link
                    href={hrefClientes({ ...filtros, colegio: c.colegio_id, grado: "", pagina: 1 })}
                    className={styles.cabezaColegio}
                  >
                    {logo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={logo} alt="" className={styles.logoColegio} loading="lazy" />
                    ) : (
                      <span className={styles.logoColegio} aria-hidden="true">
                        {c.colegio_nombre.replace(/^(COLEGIO|GIMNASIO|UNIDAD EDUCATIVA|JARDIN INFANTIL)\s+/i, "").charAt(0)}
                      </span>
                    )}
                    <span className={styles.nombreColegio}>{c.colegio_nombre}</span>
                    <span className={styles.cifrasColegio}>
                      <strong className="cifra">{c.acudientes}</strong> {c.acudientes === 1 ? "familia" : "familias"}
                      <span aria-hidden="true"> · </span>
                      <strong className="cifra">{c.hijos}</strong> {c.hijos === 1 ? "hijo" : "hijos"}
                    </span>
                  </Link>
                  <span className={styles.barraColegio} aria-hidden="true">
                    <span style={{ width: `${(c.hijos / maxHijosColegio) * 100}%` }} />
                  </span>
                  <ul className={styles.gradosColegio} aria-label={`Grados en ${c.colegio_nombre}`}>
                    {c.grados.map((g) => (
                      <li key={g.grado}>
                        <Link
                          href={hrefClientes({ ...filtros, colegio: c.colegio_id, grado: g.grado, pagina: 1 })}
                          className={styles.chipGrado}
                          style={{ ["--peso" as string]: String(g.hijos / maxGrado) }}
                        >
                          {g.grado} <span className="cifra">{g.hijos}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {acudientes.length > 0 ? (
        // El `key` remonta el formulario cuando cambia la URL (Limpiar, atras).
        <Form
          key={hrefClientes({ ...filtros, pagina: 1 })}
          action="/clientes"
          className={styles.filtros}
          aria-label="Filtrar familias"
        >
          <div className={`${styles.campo} ${styles.busqueda}`}>
            <label htmlFor="cli-q">Correo</label>
            <input id="cli-q" name="q" type="search" defaultValue={filtros.q} placeholder="nombre@correo.com" autoComplete="off" />
          </div>
          <div className={styles.campo}>
            <label htmlFor="cli-colegio">Colegio</label>
            <select id="cli-colegio" name="colegio" defaultValue={filtros.colegio}>
              <option value="">Todos</option>
              {opciones.colegios.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.campo}>
            <label htmlFor="cli-grado">Grado</label>
            <select id="cli-grado" name="grado" defaultValue={filtros.grado}>
              <option value="">Todos</option>
              {opciones.grados.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.campo}>
            <label htmlFor="cli-hijos">Hijos</label>
            <select id="cli-hijos" name="hijos" defaultValue={filtros.hijos}>
              <option value="">Cualquiera</option>
              <option value="0">Sin hijos</option>
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3+">3 o más</option>
            </select>
          </div>
          <div className={styles.campo}>
            <label htmlFor="cli-orden">Registro</label>
            <select id="cli-orden" name="orden" defaultValue={filtros.orden}>
              <option value="nuevo">Más recientes primero</option>
              <option value="antiguo">Más antiguos primero</option>
            </select>
          </div>
          <label className={styles.casilla}>
            <input type="checkbox" name="sinprueba" value="1" defaultChecked={filtros.sinPrueba} />
            Ocultar cuentas de prueba{pruebas > 0 ? ` (${pruebas})` : ""}
          </label>
          <div className={styles.botonera}>
            <button type="submit" className={styles.filtrar}>
              Filtrar
            </button>
            <Link href="/clientes" className={styles.limpiar}>
              Limpiar
            </Link>
          </div>
        </Form>
      ) : null}

      {acudientes.length > 0 ? (
        <p className={styles.conteo} aria-live="polite">
          {pagina.total === 0
            ? "Ninguna familia cumple esos filtros."
            : `Mostrando ${pagina.desde}–${pagina.hasta} de ${pagina.total} ${pagina.total === 1 ? "familia" : "familias"}${hayFiltrosClientes(filtros) ? ` (de ${acudientes.length})` : ""}.`}
        </p>
      ) : null}

      {acudientes.length === 0 ? (
        <EstadoVacio titulo="Todavía no hay familias registradas">
          Aparecen aquí cuando un acudiente crea su cuenta en la app.
        </EstadoVacio>
      ) : pagina.total === 0 ? null : (
        <div className={ui.marcoTabla}>
          <table className={styles.tabla}>
            <caption className={styles.oculto}>Padrón de familias registradas y sus hijos.</caption>
            <thead>
              <tr>
                <th scope="col">Correo</th>
                <th scope="col">Celular</th>
                <th scope="col">Registro</th>
                <th scope="col" className={styles.num}>
                  Hijos
                </th>
                <th scope="col">Hijos matriculados</th>
                <th scope="col">Pedido</th>
              </tr>
            </thead>
            <tbody>
              {pagina.items.map((acudiente) => (
                <tr key={acudiente.usuario_id}>
                  <th scope="row" className={styles.correo}>
                    <Link href={hrefCliente(acudiente.usuario_id)} className={styles.enlaceFila}>
                      <span className={styles.avatar} aria-hidden="true">
                        {acudiente.correo.charAt(0).toUpperCase()}
                      </span>
                      {acudiente.correo}
                    </Link>
                  </th>
                  <td className={acudiente.celular ? undefined : styles.tenue}>
                    {acudiente.celular ?? "—"}
                  </td>
                  <td className={styles.fechaExacta}>{formatearFecha(acudiente.creado_en)}</td>
                  <td className={`${styles.num} cifra`}>{acudiente.hijos.length}</td>
                  <td>
                    {acudiente.hijos.length === 0 ? (
                      <span className={styles.tenue}>Sin hijos matriculados</span>
                    ) : (
                      <ul className={styles.hijos}>
                        {acudiente.hijos.map((hijo, indice) => (
                          <li key={`${acudiente.usuario_id}-${indice}`}>
                            <span className={styles.gradoHijo}>{hijo.grado}</span>
                            <span className={styles.colegioHijo}>{textoHijo(hijo, indice).split(" · ").slice(-1)[0]}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td>
                    <PastillaPedido pedido={pedidos.get(acudiente.usuario_id)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pagina.paginas > 1 ? (
        <nav className={styles.paginacion} aria-label="Páginas del padrón">
          {pagina.pagina > 1 ? (
            <Link href={hrefClientes(filtros, { pagina: pagina.pagina - 1 })} rel="prev">
              ← Anterior
            </Link>
          ) : (
            <span className={styles.tenue}>← Anterior</span>
          )}
          <span className="cifra">
            Página {pagina.pagina} de {pagina.paginas}
          </span>
          {pagina.pagina < pagina.paginas ? (
            <Link href={hrefClientes(filtros, { pagina: pagina.pagina + 1 })} rel="next">
              Siguiente →
            </Link>
          ) : (
            <span className={styles.tenue}>Siguiente →</span>
          )}
        </nav>
      ) : null}
    </div>
  );
}

function PastillaPedido({ pedido }: { pedido: PedidoDeFamilia | undefined }) {
  if (!pedido) return <span className={styles.tenue}>Sin pedido</span>;
  const etiqueta = ETIQUETA_ESTADO_PEDIDO[pedido.estado as EstadoPedido] ?? pedido.estado;
  return (
    <span className={`${styles.pastillaPedido} ${styles[`pedido_${pedido.tono}`]}`}>
      {etiqueta}
      {pedido.pedidos > 1 ? <span className={styles.tenue}> · {pedido.pedidos}</span> : null}
    </span>
  );
}
