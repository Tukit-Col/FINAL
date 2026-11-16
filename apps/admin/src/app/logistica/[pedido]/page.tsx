// `/logistica/[pedido]` — el detalle de un pedido para moverlo de estado.
//
// Trae lo que el operador necesita para entregar y atender (acudiente con datos
// enmascarados, hijos por colegio y grado, cada linea con su imagen, pago con el
// id de Wompi, la direccion congelada, la linea de tiempo con quien y cuando, y
// los retractos con su plazo de la Ley 1480). Solo staff lo lee: comercio
// responde 401/403 a cualquier otro, y aqui eso se vuelve el mismo aviso del
// tablero.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { AcudienteAdmin, CorreoEnviado, EstadoPedido, PedidoAdmin, TipoIncidencia } from "@tukit/contrato";
import {
  ETIQUETA_ESTADO_PEDIDO,
  ETIQUETA_TIPO_INCIDENCIA,
  enlaceGoogleMaps,
  formatearPesos,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos, urlWeb } from "@tukit/contrato/servidor";
import AccionesPedido from "@/components/AccionesPedido";
import AvisoAcceso from "@/components/AvisoAcceso";
import { ETIQUETA_ESTADO_CORREO, explicarDetalle } from "@/lib/correos";
import { formatearDia, formatearFecha } from "@/lib/formato";
import { motivoDeFallo } from "@/lib/logistica";
import { etiquetasDePedidos, nombresDeColegios } from "@/lib/logistica-servidor";
import {
  construirLineaDeTiempo,
  enmascararCorreo,
  formatearDiaIso,
  lineasConSubtotal,
  rotuloDeHijo,
  totalDescuadrado,
} from "@/lib/pedido-admin";
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
async function nombresDeActores(pedido: PedidoAdmin, token: string): Promise<Record<string, string>> {
  const ids = [...new Set(pedido.historial.map((h) => h.actor_id))];
  if (ids.length === 0) return {};
  try {
    return await origenDeDatos().nombresDeUsuarios(ids, token);
  } catch {
    return {};
  }
}

/** La imagen y la tienda de referencia de cada linea, del catalogo publico. Es
 *  un adorno: sin catalogo la linea se pinta con su sku y sin foto. La tienda es
 *  la de la oferta vigente mas barata, no la que cumplio el pedido (el pedido no
 *  guarda tienda). */
interface ExtraLinea {
  imagen: string | null;
  tienda: string | null;
}

async function productosDeLineas(skus: string[]): Promise<Map<string, ExtraLinea>> {
  const origen = origenDeDatos();
  const vacio: ExtraLinea = { imagen: null, tienda: null };
  const pares = await Promise.all(
    skus.map(async (sku): Promise<[string, ExtraLinea]> => {
      try {
        const producto = await origen.productoPublico(sku);
        if (!producto) return [sku, vacio];
        const conPrecio = producto.ofertas.filter((o) => o.precio !== null);
        conPrecio.sort((a, b) => (a.precio ?? 0) - (b.precio ?? 0));
        return [sku, { imagen: producto.imagen_url, tienda: conPrecio[0]?.tienda_nombre ?? null }];
      } catch {
        return [sku, vacio];
      }
    }),
  );
  return new Map(pares);
}

/** Los avisos que el sistema mandó por este pedido (el código corto del pedido
 *  va en cada aviso). Es un adorno: si operacion no responde, el bloque dice que
 *  no se pudo leer en vez de romper la página. */
async function correosDelPedido(token: string, pedidoId: string): Promise<CorreoEnviado[] | null> {
  try {
    const { correos } = await origenDeDatos().correos(token, { pedido: pedidoId.slice(0, 8).toUpperCase() });
    return correos;
  } catch {
    return null;
  }
}

/** Los hijos del acudiente en los colegios del pedido, con su grado. Del menor
 *  no viaja nada que lo identifique (Ley 1581). */
async function hijosDelPedido(
  token: string,
  usuarioId: string,
  colegios: string[],
): Promise<AcudienteAdmin["hijos"]> {
  try {
    const [acudiente] = await origenDeDatos().acudientesAdmin(token, [usuarioId]);
    const hijos = acudiente?.hijos ?? [];
    const delPedido = hijos.filter((h) => colegios.includes(h.colegio_nombre));
    return delPedido.length > 0 ? delPedido : hijos;
  } catch {
    return [];
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

  let pedido: PedidoAdmin;
  try {
    pedido = await origenDeDatos().pedidoAdmin(token, pedidoId);
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

  const [nombres, etiquetas, productos, hijos, correos] = await Promise.all([
    nombresDeActores(pedido, token),
    etiquetasDePedidos(token, [pedido]),
    productosDeLineas([...new Set(pedido.lineas.map((l) => l.sku))]),
    hijosDelPedido(token, pedido.usuario_id, pedido.colegios),
    correosDelPedido(token, pedido.pedido_id),
  ]);
  const lineas = lineasConSubtotal(pedido);
  const pasos = construirLineaDeTiempo(pedido);
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
            {pedido.devoluciones.length > 0 ? (
              <span className={styles.alertaRetracto}>Retracto solicitado</span>
            ) : null}
            {pedido.trabajo_id ? <Link href={`/trabajos/${pedido.trabajo_id}`}>ver trabajo</Link> : null}
          </div>
          <code className={styles.idCompleto}>{pedido.pedido_id}</code>
        </div>
      </section>

      <section className={styles.bloque} aria-labelledby="tiempo-titulo">
        <h2 id="tiempo-titulo">Seguimiento</h2>
        <ol className={styles.tiempo}>
          {pasos.map((paso) => (
            <li
              key={paso.estado}
              className={styles[`paso_${paso.situacion}`]}
              aria-current={paso.situacion === "actual" ? "step" : undefined}
            >
              <span className={styles.tiempoEtiqueta}>{paso.etiqueta}</span>
              <span className={styles.tiempoCuando}>{paso.cuando ? formatearFecha(paso.cuando) : "—"}</span>
              <span className={styles.tiempoQuien}>{paso.quien ?? ""}</span>
            </li>
          ))}
        </ol>
        {pedido.estado === "incidencia" || pedido.estado === "cancelado" ? (
          <p className={styles.tenue}>
            El pedido está en «{ETIQUETA_ESTADO_PEDIDO[pedido.estado]}»; el detalle está en el historial de abajo.
          </p>
        ) : null}
      </section>

      <section className={styles.bloque} aria-labelledby="correos-titulo">
        <h2 id="correos-titulo">Correos de este pedido</h2>
        {correos === null ? (
          <p className={styles.tenue}>No pudimos leer los avisos de este pedido. Intenta de nuevo en un momento.</p>
        ) : correos.length === 0 ? (
          <p className={styles.tenue}>Todavía no se ha enviado ningún aviso de este pedido.</p>
        ) : (
          <ul className={styles.correos}>
            {correos.map((c) => (
              <li key={c.id}>
                <span className={styles.correoAsunto}>{c.asunto ?? c.plantilla}</span>
                <span className={`${styles.correoEstado} ${styles[`correo_${c.estado}`]}`}>
                  {ETIQUETA_ESTADO_CORREO[c.estado]}
                </span>
                <span className={styles.tenue}>
                  {c.creado_en ? formatearFecha(c.creado_en) : "—"}
                  {c.destino_dominio ? ` · @${c.destino_dominio}` : ""} · {explicarDetalle(c.detalle)}
                </span>
              </li>
            ))}
          </ul>
        )}
        <Link href={`/correos?pedido=${pedido.pedido_id.slice(0, 8).toUpperCase()}`} className={styles.tenue}>
          Ver en Correos enviados
        </Link>
      </section>

      <AccionesPedido pedidoId={pedido.pedido_id} estado={pedido.estado} urlIngresar={`${urlWeb()}/ingresar`} />

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
          <h2 id="contenido-titulo">Acudiente y pedido</h2>
          <dl className={styles.datos}>
            <dt>Acudiente</dt>
            <dd title="Correo enmascarado: el operador no necesita leerlo entero">
              {enmascararCorreo(correoAcudiente)}
            </dd>
            <dt>Colegios</dt>
            <dd>{nombresDeColegios(pedido.colegios, etiquetas.colegios) || "—"}</dd>
            <dt>Hijos</dt>
            <dd>
              {hijos.length > 0 ? (
                <ul className={styles.hijos}>
                  {hijos.map((h, i) => (
                    <li key={`${h.colegio_id}-${h.grado}-${i}`}>
                      {rotuloDeHijo(h, i)} · {h.colegio_nombre}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="cifra">{pedido.hijos}</span>
              )}
            </dd>
            <dt>Total</dt>
            <dd className="cifra">{formatearPesos(pedido.total)}</dd>
          </dl>
        </section>

        <section className={styles.bloque} aria-labelledby="pago-titulo">
          <h2 id="pago-titulo">Pago</h2>
          {pedido.pago ? (
            <dl className={styles.datos}>
              <dt>Estado</dt>
              <dd>{pedido.pago.estado}</dd>
              <dt>Método</dt>
              <dd>{pedido.pago.metodo.toUpperCase()}</dd>
              <dt>Monto</dt>
              <dd className="cifra">{formatearPesos(pedido.pago.monto)}</dd>
              <dt>Transacción Wompi</dt>
              <dd>
                {pedido.pago.transaccion_wompi ? <code>{pedido.pago.transaccion_wompi}</code> : "Aún sin transacción"}
              </dd>
              <dt>Referencia</dt>
              <dd>
                <code>{pedido.pago.referencia_wompi}</code>
              </dd>
            </dl>
          ) : (
            <p className={styles.tenue}>Todavía no hay un intento de pago.</p>
          )}
        </section>
      </div>

      <section className={styles.bloque} aria-labelledby="lineas-titulo">
        <h2 id="lineas-titulo">Productos</h2>
        <div className={styles.tablaMarco}>
          <table className={styles.tabla}>
            <thead>
              <tr>
                <th scope="col">Producto</th>
                <th scope="col">SKU</th>
                <th scope="col">Tienda de referencia</th>
                <th scope="col" className={styles.num}>
                  Cant.
                </th>
                <th scope="col" className={styles.num}>
                  Unitario
                </th>
                <th scope="col" className={styles.num}>
                  Subtotal
                </th>
              </tr>
            </thead>
            <tbody>
              {lineas.map((l, i) => {
                const extra = productos.get(l.sku);
                return (
                  <tr key={`${i}-${l.sku}`}>
                    <td>
                      <div className={styles.producto}>
                        {extra?.imagen ? (
                          // eslint-disable-next-line @next/next/no-img-element -- imagen externa del catalogo, sin dominio fijo para next/image
                          <img src={extra.imagen} alt="" width={40} height={40} loading="lazy" className={styles.miniatura} />
                        ) : (
                          <span className={styles.miniaturaVacia} aria-hidden="true" />
                        )}
                        <span>{l.nombre}</span>
                      </div>
                    </td>
                    <td>
                      <code>{l.sku}</code>
                    </td>
                    <td>{extra?.tienda ?? "—"}</td>
                    <td className={`${styles.num} cifra`}>{l.cantidad}</td>
                    <td className={`${styles.num} cifra`}>{formatearPesos(l.precio_unitario)}</td>
                    <td className={`${styles.num} cifra`}>{formatearPesos(l.subtotal)}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={5}>
                  Total del pedido
                </th>
                <td className={`${styles.num} cifra`}>{formatearPesos(pedido.total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
        {totalDescuadrado(pedido) ? (
          <p className={styles.tenue}>
            El total congelado no coincide con la suma de las líneas; revísalo antes de reembolsar.
          </p>
        ) : null}
      </section>

      {pedido.devoluciones.length > 0 ? (
        <section className={`${styles.bloque} ${styles.bloqueRetracto}`} aria-labelledby="retracto-titulo">
          <h2 id="retracto-titulo">Retracto y devoluciones (Ley 1480)</h2>
          <ul className={styles.devoluciones}>
            {pedido.devoluciones.map((d) => (
              <li key={d.devolucion_id}>
                <div>
                  <strong>Solicitado {formatearFecha(d.creado_en)}</strong> · {formatearPesos(d.monto)}
                </div>
                {d.motivo ? <p className={styles.nota}>«{d.motivo}»</p> : null}
                <dl className={styles.datos}>
                  <dt>Plazo para retractarse</dt>
                  <dd>
                    {d.plazo_retracto
                      ? `hasta el ${formatearDiaIso(d.plazo_retracto)} (5 días hábiles desde la entrega)`
                      : "Aún no corre: el pedido no se ha entregado"}
                  </dd>
                  <dt>¿A tiempo?</dt>
                  <dd>{d.dentro_de_plazo ? "Sí, dentro del plazo" : "No, llegó después del plazo"}</dd>
                  <dt>Reembolsar a más tardar</dt>
                  <dd>{formatearDiaIso(d.limite_reembolso)} (30 días desde la solicitud)</dd>
                </dl>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

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
