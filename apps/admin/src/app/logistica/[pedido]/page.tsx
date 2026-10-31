// `/logistica/[pedido]` — el detalle de un pedido para moverlo de estado.
//
// Trae lo que el operador necesita para entregar (la direccion congelada, el
// telefono, el repartidor CON su celular) y el historial de avances. Solo
// staff lo lee: comercio responde 401/403 a cualquier otro, y aqui eso se
// vuelve el mismo aviso del tablero.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { EstadoPedido, PedidoConHistorial, TipoIncidencia } from "@tukit/contrato";
import {
  ETIQUETA_ESTADO_PEDIDO,
  ETIQUETA_TIPO_INCIDENCIA,
  enlaceGoogleMaps,
  formatearPesos,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import AccionesPedido from "@/components/AccionesPedido";
import AvisoAcceso from "@/components/AvisoAcceso";
import { formatearDia, formatearFecha } from "@/lib/formato";
import { motivoDeFallo } from "@/lib/logistica";
import { etiquetasDePedidos, nombresDeColegios } from "@/lib/logistica-servidor";
import { tokenDeSesion } from "@/lib/sesion";
import styles from "./Detalle.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ pedido: string }>;
}

function Migas() {
  return (
    <nav className={styles.migas}>
      <Link href="/logistica">← Logística</Link>
    </nav>
  );
}

function Estado({ estado }: { estado: EstadoPedido }) {
  return (
    <span className={`${styles.estado} ${styles[`estado_${estado}`]}`}>
      {ETIQUETA_ESTADO_PEDIDO[estado]}
    </span>
  );
}

function etiquetaIncidencia(tipo: string): string {
  // Un tipo nuevo en comercio que aun no tenga etiqueta aqui se muestra crudo.
  return ETIQUETA_TIPO_INCIDENCIA[tipo as TipoIncidencia] ?? tipo;
}

/** Nombres de quienes movieron el pedido. Es un adorno: si identidad no los
 *  da (sin permiso de leer nombres, o caida), el historial muestra el id
 *  corto en vez de romper la pagina. */
async function nombresDeActores(pedido: PedidoConHistorial, token: string): Promise<Record<string, string>> {
  const ids = [...new Set(pedido.historial.map((h) => h.actor_id))];
  if (ids.length === 0) return {};
  try {
    return await origenDeDatos().nombresDeUsuarios(ids, token);
  } catch {
    return {};
  }
}

export default async function DetallePedido({ params }: Props) {
  const { pedido: pedidoId } = await params;
  const token = await tokenDeSesion();
  if (!token) {
    return (
      <div className={styles.pagina}>
        <Migas />
        <AvisoAcceso motivo="sin_sesion" />
      </div>
    );
  }

  let pedido: PedidoConHistorial;
  try {
    pedido = await origenDeDatos().pedido(token, pedidoId);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit)) throw causa;
    // 400: el id ni siquiera es un UUID; para quien lo pego es lo mismo que no existir.
    if (causa.estado === 404 || causa.estado === 400) notFound();
    return (
      <div className={styles.pagina}>
        <Migas />
        <AvisoAcceso motivo={motivoDeFallo(causa.estado)} mensaje={causa.message} />
      </div>
    );
  }

  const [nombres, etiquetas] = await Promise.all([
    nombresDeActores(pedido, token),
    etiquetasDePedidos(token, [pedido]),
  ]);
  const correoAcudiente = etiquetas.correos.get(pedido.usuario_id);
  const envio = pedido.envio;
  // El historial llega en orden de avance; lo mas reciente arriba es lo que
  // el operador busca primero.
  const historial = [...pedido.historial].reverse();

  return (
    <div className={styles.pagina}>
      <Migas />

      <section className={styles.encabezado}>
        <div className={styles.identidad}>
          <h1>
            Pedido <code>{pedido.pedido_id.slice(0, 8).toUpperCase()}</code>
          </h1>
          <div className={styles.hechos}>
            <Estado estado={pedido.estado} />
            <span>Creado {formatearFecha(pedido.creado_en)}</span>
            <span className="cifra">{formatearPesos(pedido.total)}</span>
            {pedido.pago ? <span>Pago: {pedido.pago.estado}</span> : null}
            {pedido.trabajo_id ? <Link href={`/trabajos/${pedido.trabajo_id}`}>ver trabajo</Link> : null}
          </div>
          <code className={styles.idCompleto}>{pedido.pedido_id}</code>
        </div>
      </section>

      <AccionesPedido pedidoId={pedido.pedido_id} estado={pedido.estado} />

      <div className={styles.columnas}>
        <section className={styles.bloque} aria-labelledby="entrega-titulo">
          <h2 id="entrega-titulo">Entrega</h2>
          {envio ? (
            <dl className={styles.datos}>
              <dt>Recibe</dt>
              <dd>{envio.destinatario}</dd>
              <dt>Dirección</dt>
              <dd>
                {envio.direccion}
                {/* Sin coordenadas: Maps busca por el texto y, si el checkout
                    guardo el lugar de Google, abre ese exacto (ADR 0044). */}
                <a
                  href={enlaceGoogleMaps(envio)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.enlaceMapa}
                >
                  Ver en Google Maps
                </a>
              </dd>
              <dt>Localidad</dt>
              <dd>{envio.localidad || "—"}</dd>
              <dt>Ciudad</dt>
              <dd>
                {envio.ciudad}
                {envio.departamento ? `, ${envio.departamento}` : ""}
              </dd>
              <dt>Teléfono</dt>
              <dd>{envio.telefono ? <a href={`tel:${envio.telefono}`}>{envio.telefono}</a> : "—"}</dd>
              <dt>Indicaciones</dt>
              <dd>{envio.indicaciones || "—"}</dd>
              <dt>Repartidor</dt>
              <dd>
                {envio.repartidor_nombre ? (
                  <>
                    {envio.repartidor_nombre}
                    {envio.repartidor_celular ? (
                      <>
                        {" · "}
                        <a href={`tel:${envio.repartidor_celular}`}>{envio.repartidor_celular}</a>
                      </>
                    ) : null}
                  </>
                ) : envio.transportadora ? (
                  // Envio viejo, de cuando se despachaba por transportadora.
                  `${envio.transportadora}${envio.guia ? ` · guía ${envio.guia}` : ""}`
                ) : (
                  "Sin asignar"
                )}
              </dd>
              <dt>Entrega estimada</dt>
              <dd>{envio.entrega_estimada ? formatearDia(envio.entrega_estimada) : "—"}</dd>
              {envio.entregado_en ? (
                <>
                  <dt>Entregado</dt>
                  <dd>{formatearFecha(envio.entregado_en)}</dd>
                </>
              ) : null}
            </dl>
          ) : (
            <p className={styles.tenue}>Este pedido no tiene datos de entrega.</p>
          )}
        </section>

        <section className={styles.bloque} aria-labelledby="contenido-titulo">
          <h2 id="contenido-titulo">Contenido</h2>
          <dl className={styles.datos}>
            <dt>Acudiente</dt>
            <dd>{correoAcudiente ? <a href={`mailto:${correoAcudiente}`}>{correoAcudiente}</a> : "—"}</dd>
            <dt>Colegios</dt>
            <dd>{nombresDeColegios(pedido.colegios, etiquetas.colegios) || "—"}</dd>
            <dt>Hijos</dt>
            <dd className="cifra">{pedido.hijos}</dd>
            <dt>Total</dt>
            <dd className="cifra">{formatearPesos(pedido.total)}</dd>
          </dl>
        </section>
      </div>

      <section className={styles.bloque} aria-labelledby="historial-titulo">
        <h2 id="historial-titulo">Historial</h2>
        {historial.length === 0 ? (
          <p className={styles.tenue}>
            Todavía nadie del equipo lo ha movido. El historial empieza con el primer paso de
            logística (el pago lo confirma Wompi y no queda aquí).
          </p>
        ) : (
          <ol className={styles.historial}>
            {historial.map((h, i) => (
              <li key={`${h.creado_en}-${i}`}>
                <div className={styles.paso}>
                  <Estado estado={h.estado_desde} />
                  <span aria-label="a">→</span>
                  <Estado estado={h.estado_hacia} />
                </div>
                <div className={styles.quien}>
                  {h.actor_correo ?? nombres[h.actor_id] ?? <code>{h.actor_id.slice(0, 8)}</code>} ·{" "}
                  {formatearFecha(h.creado_en)}
                </div>
                {h.tipo_incidencia ? (
                  <div className={styles.incidencia}>{etiquetaIncidencia(h.tipo_incidencia)}</div>
                ) : null}
                {h.nota ? <p className={styles.nota}>{h.nota}</p> : null}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
