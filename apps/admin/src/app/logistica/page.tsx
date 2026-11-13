// `/logistica` — el tablero de pedidos y entregas del back-office.
//
// Lee `origenDeDatos().pedidos(token)`: comercio solo se lo da a operador y
// admin, asi que sin cookie, con la sesion vencida o sin rol se muestra el
// aviso que corresponde en vez de reventar. Los filtros viven en la URL
// (formulario GET) y filtran aqui, en el servidor: comercio devuelve el
// tablero entero y las tarjetas de arriba son siempre las globales, para que
// un filtro no esconda que hay incidencias.
//
// Server Component, mismo patron que la Cola.

import Link from "next/link";
import { Truck, PackageCheck, CircleDollarSign, TriangleAlert, Columns3, Rows3 } from "lucide-react";
import type { AlertaPedido, Pedido, TableroComercio } from "@tukit/contrato";
import {
  ALERTAS_PEDIDO,
  ETIQUETA_ALERTA_PEDIDO,
  ETIQUETA_ESTADO_PEDIDO,
  formatearPesos,
  pedidoEnCurso,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos, urlWeb } from "@tukit/contrato/servidor";
import { BarraLote, CasillaPedido, CasillaTodos, ProveedorLote } from "@/components/AvanceEnLote";
import AvisoAcceso from "@/components/AvisoAcceso";
import FiltrosLogistica from "@/components/FiltrosLogistica";
import Revelar from "@/components/Revelar";
import SeccionMapa from "@/components/SeccionMapa";
import TableroPedidos from "@/components/TableroPedidos";
import estilosTablero from "@/components/TableroPedidos.module.css";
import { formatearFecha } from "@/lib/formato";
import {
  claveFiltros,
  filtrarPedidos,
  hayFiltros,
  hrefConAlerta,
  hrefConVista,
  leerFiltros,
  motivoDeFallo,
  ordenarPorPrioridad,
} from "@/lib/logistica";
import {
  etiquetasDePedidos,
  nombresDeColegios,
  opcionesDeColegio,
  type EtiquetasLogistica,
} from "@/lib/logistica-servidor";
import { tokenDeSesion } from "@/lib/sesion";
import Chip, { Chips } from "@/components/ui/Chip";
import EstadoVacio from "@/components/ui/EstadoVacio";
import ui from "@/components/ui/ui.module.css";
import styles from "./Logistica.module.css";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function Encabezado() {
  return (
    <header className={styles.encabezado}>
      <div>
        <h1>Logística</h1>
        <p className={styles.bajada}>
          Pedidos, pagos y entregas con reparto propio. Abre un pedido para moverlo de estado:
          cada paso queda en su historial y le avisa al acudiente. El tablero los agrupa por etapa;
          la tabla sirve para buscar y avanzar en lote.
        </p>
      </div>
    </header>
  );
}

export default async function PaginaLogistica({ searchParams }: Props) {
  const token = await tokenDeSesion();
  if (!token) {
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo="sin_sesion" />
      </div>
    );
  }

  let tablero: TableroComercio;
  try {
    tablero = await origenDeDatos().pedidos(token);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit)) throw causa;
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo={motivoDeFallo(causa.estado)} mensaje={causa.message} />
      </div>
    );
  }

  const { resumen, pedidos } = tablero;
  const filtros = leerFiltros(await searchParams);
  const ordenados = ordenarPorPrioridad(filtrarPedidos(pedidos, filtros));
  const etiquetas = await etiquetasDePedidos(token, pedidos);
  // Un solo reloj para la antiguedad de todas las tarjetas.
  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  const tarjetas = [
    {
      etiqueta: "En curso",
      valor: resumen.entregas_pendientes,
      pista: "Pagados y todavía sin entregar",
      Icono: Truck,
      tono: "info",
    },
    {
      etiqueta: "Con incidencia",
      valor: resumen.por_estado.incidencia,
      pista: "Necesitan intervención",
      Icono: TriangleAlert,
      tono: resumen.por_estado.incidencia > 0 ? "aviso" : "ok",
    },
    {
      etiqueta: "Entregados",
      valor: resumen.por_estado.entregado,
      pista: "Ya en el hogar",
      Icono: PackageCheck,
      tono: "ok",
    },
    {
      etiqueta: "Ingresos confirmados",
      valor: formatearPesos(resumen.ingresos_confirmados),
      pista: "Pagos aprobados",
      Icono: CircleDollarSign,
      tono: "ok",
    },
  ] as const;

  return (
    <div className={styles.pagina}>
      <Encabezado />

      <Revelar>
        <section className={styles.tarjetas} aria-label="Resumen de logística">
          {tarjetas.map(({ etiqueta, valor, pista, Icono, tono }) => (
            <div
              key={etiqueta}
              className={`${styles.tarjeta} ${tono === "aviso" ? styles.tarjetaAviso : ""}`}
            >
              <span className={styles.tarjetaIcono} aria-hidden="true">
                <Icono size={20} strokeWidth={2.2} />
              </span>
              <span className={`${styles.tarjetaValor} cifra`}>{valor}</span>
              <span className={styles.tarjetaEtiqueta}>{etiqueta}</span>
              <span className={styles.tarjetaPista}>{pista}</span>
            </div>
          ))}
        </section>
      </Revelar>

      <SeccionMapa pedidos={pedidos} nombresColegio={etiquetas.colegios} />

      {pedidos.length > 0 ? (
        <nav className={estilosTablero.vistas} aria-label="Vista de pedidos">
          {(
            [
              { vista: "tablero", etiqueta: "Tablero", Icono: Columns3 },
              { vista: "tabla", etiqueta: "Tabla", Icono: Rows3 },
            ] as const
          ).map(({ vista, etiqueta, Icono }) => (
            <Link
              key={vista}
              href={hrefConVista(filtros, vista)}
              className={`${estilosTablero.vista} ${filtros.vista === vista ? estilosTablero.vistaActiva : ""}`}
              aria-current={filtros.vista === vista ? "page" : undefined}
            >
              <Icono size={16} strokeWidth={2.2} aria-hidden="true" />
              {etiqueta}
            </Link>
          ))}
        </nav>
      ) : null}

      {pedidos.length > 0 ? (
        // `next/form` con action de texto no acepta `key`: el envoltorio
        // remonta el formulario cuando cambian los filtros (atras/adelante, o
        // "Limpiar"), para que sus `defaultValue` no queden viejos.
        <div key={claveFiltros(filtros)}>
          <FiltrosLogistica filtros={filtros} colegios={opcionesDeColegio(pedidos, etiquetas.colegios)} />
        </div>
      ) : null}

      {pedidos.length > 0 ? (
        <Chips etiqueta="Pedidos que piden una acción">
          <Chip href={hrefConAlerta(filtros, "")} activo={filtros.alerta === ""}>
            Todos
          </Chip>
          {ALERTAS_PEDIDO.map((alerta: AlertaPedido) => {
            const cantidad = resumen.alertas?.[alerta] ?? pedidos.filter((p) => p.alertas?.includes(alerta)).length;
            return (
              <Chip key={alerta} href={hrefConAlerta(filtros, alerta)} activo={filtros.alerta === alerta} hay={cantidad > 0}>
                {ETIQUETA_ALERTA_PEDIDO[alerta]} <span className="cifra">{cantidad}</span>
              </Chip>
            );
          })}
        </Chips>
      ) : null}

      {pedidos.length > 0 && hayFiltros(filtros) ? (
        <p className={styles.conteo} aria-live="polite">
          Mostrando {ordenados.length} de {pedidos.length} pedidos.
        </p>
      ) : null}

      {pedidos.length === 0 ? (
        <EstadoVacio titulo="No hay pedidos todavía">
          Un pedido aparece cuando un trabajo se aprueba en la cola de revisión y arranca la saga de pago.
        </EstadoVacio>
      ) : ordenados.length === 0 ? (
        <EstadoVacio titulo="Ningún pedido cumple esos filtros">
          <Link href={hrefConVista(leerFiltros({}), filtros.vista)}>Ver todos</Link>
        </EstadoVacio>
      ) : filtros.vista === "tablero" ? (
        <TableroPedidos
          pedidos={ordenados}
          filtros={filtros}
          nombresColegio={etiquetas.colegios}
          urlIngresar={`${urlWeb()}/ingresar`}
          ahora={ahora}
        />
      ) : (
        <ProveedorLote visibles={ordenados.map((p) => ({ pedido_id: p.pedido_id, estado: p.estado }))}>
        <div className={ui.marcoTabla}>
          <table className={styles.tabla}>
            <thead>
              <tr>
                <th scope="col" className={styles.colCasilla}>
                  <CasillaTodos />
                </th>
                <th scope="col">Pedido</th>
                <th scope="col">Estado</th>
                <th scope="col">Acudiente</th>
                <th scope="col">Creado</th>
                <th scope="col" className={styles.num}>
                  Hijos
                </th>
                <th scope="col">Colegios</th>
                <th scope="col">Envío</th>
                <th scope="col" className={styles.num}>
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {ordenados.map((pedido) => (
                <FilaPedido key={pedido.pedido_id} pedido={pedido} etiquetas={etiquetas} />
              ))}
            </tbody>
          </table>
        </div>
        <BarraLote urlIngresar={`${urlWeb()}/ingresar`} />
        </ProveedorLote>
      )}
    </div>
  );
}

function FilaPedido({ pedido, etiquetas }: { pedido: Pedido; etiquetas: EtiquetasLogistica }) {
  const enCurso = pedidoEnCurso(pedido);
  const correo = etiquetas.correos.get(pedido.usuario_id);
  return (
    <tr className={enCurso ? styles.filaCurso : pedido.estado === "incidencia" ? styles.filaIncidencia : ""}>
      <td className={styles.colCasilla}>
        <CasillaPedido pedidoId={pedido.pedido_id} />
      </td>
      <th scope="row" className={styles.identificador}>
        <Link href={`/logistica/${pedido.pedido_id}`} className={styles.enlacePedido}>
          <code>{pedido.pedido_id}</code>
        </Link>
        {pedido.trabajo_id ? (
          <Link href={`/trabajos/${pedido.trabajo_id}`} className={styles.enlaceTrabajo}>
            ver trabajo
          </Link>
        ) : null}
      </th>
      <td>
        <span className={`${styles.estado} ${styles[`estado_${pedido.estado}`]}`}>
          {ETIQUETA_ESTADO_PEDIDO[pedido.estado]}
        </span>
        {(pedido.alertas ?? []).map((alerta) => (
          <span key={alerta} className={styles.marcaAlerta}>
            {ETIQUETA_ALERTA_PEDIDO[alerta]}
          </span>
        ))}
      </td>
      <td className={styles.correo}>{correo ?? <span className={styles.tenue}>—</span>}</td>
      <td className={styles.fechaExacta}>{formatearFecha(pedido.creado_en)}</td>
      <td className={`${styles.num} cifra`}>{pedido.hijos}</td>
      <td className={styles.lista}>{nombresDeColegios(pedido.colegios, etiquetas.colegios) || "—"}</td>
      <td className={styles.envio}>
        {pedido.envio ? (
          // La localidad ordena la ruta del dia; fuera de Bogota, la ciudad.
          <span className={styles.lugar}>{pedido.envio.localidad || pedido.envio.ciudad}</span>
        ) : null}
        {pedido.envio?.repartidor_nombre ? (
          <span>{pedido.envio.repartidor_nombre}</span>
        ) : pedido.envio?.transportadora ? (
          // Envio viejo, de cuando se despachaba por transportadora.
          <>
            <span>{pedido.envio.transportadora}</span>
            {pedido.envio.guia ? (
              <code className={styles.guia}>{pedido.envio.guia}</code>
            ) : null}
          </>
        ) : (
          <span className={styles.tenue}>—</span>
        )}
      </td>
      <td className={`${styles.num} cifra ${styles.total}`}>{formatearPesos(pedido.total)}</td>
    </tr>
  );
}
