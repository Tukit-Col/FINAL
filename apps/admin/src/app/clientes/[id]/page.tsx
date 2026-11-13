// `/clientes/[id]` — la ficha de una familia: cuenta, hijos matriculados,
// pedidos, tickets y actividad. Solo staff (identidad, comercio y operacion
// validan el Bearer). Del menor solo se muestra posicion, grado y colegio:
// nunca apodo ni nombre (Ley 1581).

import Link from "next/link";
import { notFound } from "next/navigation";
import type { AcudienteAdmin, BandejaOperacion, Pedido } from "@tukit/contrato";
import {
  ETIQUETA_CATEGORIA_CASO,
  ETIQUETA_ESTADO_PEDIDO,
  formatearPesos,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import AvisoAcceso from "@/components/AvisoAcceso";
import EstadoVacio from "@/components/ui/EstadoVacio";
import {
  construirActividad,
  esUuid,
  hijosSeguros,
  pedidosDelCliente,
  resumenDelCliente,
  solicitudesDePedidos,
} from "@/lib/cliente-detalle";
import { formatearFecha } from "@/lib/formato";
import { motivoDeFallo } from "@/lib/logistica";
import { tokenDeSesion } from "@/lib/sesion";
import { ETIQUETA_ESTADO_TICKET } from "@/lib/tickets";
import styles from "./Cliente.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

function Migas({ correo }: { correo?: string }) {
  return (
    <nav className={styles.migas} aria-label="Ruta">
      <Link href="/clientes">Clientes</Link>
      {correo ? (
        <>
          <span aria-hidden="true"> › </span>
          <span aria-current="page">{correo}</span>
        </>
      ) : null}
    </nav>
  );
}

/** Pedidos y casos del titular son un adorno de la ficha: si un servicio no
 *  responde, esa seccion dice que no cargo y el resto sigue. */
async function intentar<T>(promesa: Promise<T>): Promise<T | null> {
  try {
    return await promesa;
  } catch {
    return null;
  }
}

export default async function FichaCliente({ params }: Props) {
  const { id } = await params;
  if (!esUuid(id)) notFound();

  const token = await tokenDeSesion();
  if (!token) {
    return (
      <div className={styles.pagina}>
        <Migas />
        <AvisoAcceso motivo="sin_sesion" />
      </div>
    );
  }

  const origen = origenDeDatos();
  let acudiente: AcudienteAdmin | undefined;
  try {
    [acudiente] = await origen.acudientesAdmin(token, [id]);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit)) throw causa;
    return (
      <div className={styles.pagina}>
        <Migas />
        <AvisoAcceso motivo={motivoDeFallo(causa.estado)} mensaje={causa.message} />
      </div>
    );
  }
  if (!acudiente) notFound();

  const [tablero, bandeja]: [{ pedidos: Pedido[] } | null, BandejaOperacion | null] = await Promise.all([
    intentar(origen.pedidos(token)),
    intentar(origen.casos(token, id)),
  ]);
  const pedidos = tablero ? pedidosDelCliente(tablero.pedidos, id) : [];
  const casos = bandeja?.casos ?? [];
  const hijos = hijosSeguros(acudiente.hijos);
  const resumen = resumenDelCliente(pedidos);
  const solicitudes = solicitudesDePedidos(pedidos);
  const actividad = construirActividad({
    acudiente,
    pedidos,
    casos,
    etiquetaEstado: (e) => ETIQUETA_ESTADO_PEDIDO[e] ?? e,
  });

  return (
    <div className={styles.pagina}>
      <Migas correo={acudiente.correo} />

      <header className={styles.cabecera}>
        <h1>{acudiente.correo}</h1>
        <dl className={styles.datos}>
          <div>
            <dt>Celular</dt>
            <dd>{acudiente.celular ?? "—"}</dd>
          </div>
          <div>
            <dt>Registro</dt>
            <dd>{formatearFecha(acudiente.creado_en)}</dd>
          </div>
          <div>
            <dt>Pedidos</dt>
            <dd className="cifra">{tablero ? resumen.pedidos : "—"}</dd>
          </div>
          <div>
            <dt>Facturado</dt>
            <dd className="cifra">{tablero ? formatearPesos(resumen.facturado) : "—"}</dd>
          </div>
        </dl>
        <p className={styles.nota}>
          El estado de consentimiento no está disponible todavía en el padrón de identidad.
        </p>
      </header>

      <div className={styles.columnas}>
        <section className={styles.bloque} aria-labelledby="h-hijos">
          <h2 id="h-hijos">Hijos matriculados</h2>
          {hijos.length === 0 ? (
            <EstadoVacio titulo="Sin hijos matriculados">Aún no ha registrado a ningún hijo.</EstadoVacio>
          ) : (
            <ul className={styles.lista}>
              {hijos.map((h) => (
                <li key={h.posicion}>
                  <strong>Hijo {h.posicion}</strong>
                  <span>
                    grado {h.grado} · {h.colegio}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={styles.bloque} aria-labelledby="h-solic">
          <h2 id="h-solic">Solicitudes de lista</h2>
          {!tablero ? (
            <p className={styles.tenue}>No pudimos cargar los pedidos de este cliente.</p>
          ) : solicitudes.length === 0 ? (
            <EstadoVacio titulo="Sin solicitudes">
              Ningún pedido suyo salió de una solicitud de kit.
            </EstadoVacio>
          ) : (
            <ul className={styles.lista}>
              {solicitudes.map((t) => (
                <li key={t}>
                  <Link href={`/trabajos/${t}`} className="cifra">
                    Solicitud {t.slice(0, 8)}
                  </Link>
                  <span>origen de {pedidos.filter((p) => p.trabajo_id === t).length} pedido(s)</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className={styles.bloque} aria-labelledby="h-pedidos">
        <h2 id="h-pedidos">Pedidos</h2>
        {!tablero ? (
          <p className={styles.tenue}>No pudimos cargar los pedidos. Revisa que comercio esté arriba.</p>
        ) : pedidos.length === 0 ? (
          <EstadoVacio titulo="Todavía no tiene pedidos">Aparecen aquí cuando pague un kit.</EstadoVacio>
        ) : (
          <div className={styles.marcoTabla}>
            <table className={styles.tabla}>
              <thead>
                <tr>
                  <th scope="col">Pedido</th>
                  <th scope="col">Fecha</th>
                  <th scope="col">Estado</th>
                  <th scope="col" className={styles.num}>
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {pedidos.map((p) => (
                  <tr key={p.pedido_id}>
                    <th scope="row">
                      <Link href={`/logistica/${p.pedido_id}`} className="cifra">
                        {p.pedido_id.slice(0, 8)}
                      </Link>
                    </th>
                    <td className={styles.tenue}>{formatearFecha(p.creado_en)}</td>
                    <td>
                      <span className={`${styles.estado} ${styles[`estado_${p.estado}`] ?? ""}`}>
                        {ETIQUETA_ESTADO_PEDIDO[p.estado] ?? p.estado}
                      </span>
                    </td>
                    <td className={`${styles.num} cifra`}>{formatearPesos(p.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={styles.bloque} aria-labelledby="h-casos">
        <h2 id="h-casos">Tickets</h2>
        {!bandeja ? (
          <p className={styles.tenue}>
            No pudimos cargar los tickets. Si operación no se ha reiniciado, falta `make reanudar`.
          </p>
        ) : casos.length === 0 ? (
          <EstadoVacio titulo="Sin tickets">Este cliente no ha abierto casos.</EstadoVacio>
        ) : (
          <ul className={styles.lista}>
            {casos.map((c) => (
              <li key={c.caso_id}>
                <Link href={`/tickets/${c.caso_id}`}>{c.asunto}</Link>
                <span>
                  {ETIQUETA_CATEGORIA_CASO[c.categoria] ?? c.categoria} ·{" "}
                  {ETIQUETA_ESTADO_TICKET[c.estado] ?? c.estado} · {formatearFecha(c.abierto_en)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.bloque} aria-labelledby="h-act">
        <h2 id="h-act">Actividad</h2>
        <ol className={styles.tiempo}>
          {actividad.map((a, i) => (
            <li key={`${a.tipo}-${i}`}>
              <time dateTime={a.cuando} className={styles.tenue}>
                {formatearFecha(a.cuando)}
              </time>
              {a.href ? <Link href={a.href}>{a.titulo}</Link> : <span>{a.titulo}</span>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
