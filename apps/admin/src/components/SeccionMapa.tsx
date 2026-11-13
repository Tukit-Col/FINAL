// La seccion "Entregas en el mapa" de /logistica. Server Component: aqui se
// geocodifica (solo en el servidor, con cache y 1 peticion por segundo) y se
// agrupa; el mapa de Leaflet entra por el envoltorio de cliente con ssr:false.
//
// Es un consolidado, no un planificador: cuenta y lista por colegio, y marca
// donde esta cada direccion. No ordena rutas ni calcula tiempos.

import Link from "next/link";
import type { Pedido } from "@tukit/contrato";
import { ETIQUETA_ESTADO_PEDIDO } from "@tukit/contrato";
import {
  agruparPorColegio,
  esEntregaPendiente,
  SIN_COLEGIO,
  marcadoresDe,
  type EntregaPendiente,
} from "@/lib/consolidado";
import { ATRIBUCION, claveDireccion, type ResultadoGeo } from "@/lib/geocodificador";
import { geocodificadorDelServidor } from "@/lib/geocodificador-servidor";
import { hrefColegioEnTabla } from "@/lib/logistica";
import MapaEntregasCarga from "./MapaEntregasCarga";
import styles from "./SeccionMapa.module.css";

/** Cuantos pedidos lista cada colegio antes de mandar a la tabla. */
const VISIBLES_POR_GRUPO = 10;

interface Props {
  pedidos: readonly Pedido[];
  nombresColegio: ReadonlyMap<string, string>;
}

export default async function SeccionMapa({ pedidos, nombresColegio }: Props) {
  const pendientes = pedidos.filter(esEntregaPendiente);
  if (pendientes.length === 0) return null;

  const geocodificador = geocodificadorDelServidor();
  const direcciones = pendientes.map((p) => ({
    direccion: p.envio!.direccion,
    ciudad: p.envio!.ciudad,
    departamento: p.envio!.departamento,
  }));
  // Si Nominatim o el disco fallan, el mapa se degrada a lista sin marcadores.
  const puntos: Map<string, ResultadoGeo> = geocodificador
    ? await geocodificador.resolver(direcciones).catch(() => new Map<string, ResultadoGeo>())
    : new Map<string, ResultadoGeo>();

  const entregas: EntregaPendiente[] = pendientes.map((p, i) => {
    const envio = p.envio!;
    return {
      pedido_id: p.pedido_id,
      estado: p.estado,
      destinatario: envio.destinatario,
      direccion: envio.direccion,
      ciudad: envio.ciudad,
      departamento: envio.departamento,
      colegios: p.colegios.map((id) => nombresColegio.get(id) ?? id),
      hijos: p.hijos,
      punto: puntos.get(claveDireccion(direcciones[i]!)) ?? null,
    };
  });

  const idDeColegio = new Map<string, string>();
  for (const [id, nombre] of nombresColegio) if (!idDeColegio.has(nombre)) idDeColegio.set(nombre, id);
  const grupos = agruparPorColegio(entregas);
  const marcadores = marcadoresDe(grupos);
  const sinMarcador = entregas.filter((e) => typeof e.punto !== "object" || e.punto === null);
  const porConsultar = sinMarcador.filter((e) => e.punto === "pendiente").length;

  return (
    <section className={styles.seccion} aria-labelledby="titulo-mapa">
      <h2 id="titulo-mapa">Entregas pendientes en el mapa</h2>
      <p className={styles.nota}>
        {entregas.length} {entregas.length === 1 ? "pedido pagado" : "pedidos pagados"} sin entregar,
        agrupados por colegio. El mapa solo ubica las direcciones; no define el orden de reparto.
      </p>

      {!geocodificador ? (
        <p className={styles.aviso} role="status">
          El mapa está apagado: falta <code>TUKIT_NOMINATIM_CONTACTO</code> (la política de
          OpenStreetMap exige un contacto en cada consulta). Las direcciones se listan abajo.
        </p>
      ) : null}
      {porConsultar > 0 ? (
        <p className={styles.aviso} role="status">
          {porConsultar} {porConsultar === 1 ? "dirección falta" : "direcciones faltan"} por ubicar:
          se consulta un máximo por visita para respetar el límite de una por segundo. Recarga en un
          momento.
        </p>
      ) : null}

      {marcadores.length > 0 ? (
        <>
          <MapaEntregasCarga marcadores={marcadores} />
          <p className={styles.atribucion}>{ATRIBUCION}</p>
        </>
      ) : null}

      <div className={styles.grupos}>
        {grupos.map((g) => (
          <details key={g.colegio} className={styles.grupo} open={grupos.length <= 3 && g.entregas.length <= VISIBLES_POR_GRUPO}>
            <summary>
              <strong>{g.colegio}</strong>
              <span className={styles.conteo}>
                {g.entregas.length} {g.entregas.length === 1 ? "pedido" : "pedidos"} · {g.hijos}{" "}
                {g.hijos === 1 ? "hijo" : "hijos"}
                {g.sinMarcador > 0 ? ` · ${g.sinMarcador} sin marcador` : ""}
              </span>
            </summary>
            <ul>
              {g.entregas.slice(0, VISIBLES_POR_GRUPO).map((e) => (
                <li key={e.pedido_id}>
                  <Link href={`/logistica/${e.pedido_id}`}>
                    <code>{e.pedido_id}</code>
                  </Link>{" "}
                  <span className={styles.estado}>{ETIQUETA_ESTADO_PEDIDO[e.estado]}</span>
                  <span className={styles.direccion}>
                    {e.destinatario} · {e.direccion}, {e.ciudad}
                  </span>
                </li>
              ))}
            </ul>
            {g.entregas.length > VISIBLES_POR_GRUPO ? (
              <p className={styles.verMas}>
                Mostrando {VISIBLES_POR_GRUPO} de {g.entregas.length}.{" "}
                <Link
                  href={hrefColegioEnTabla(g.colegio === SIN_COLEGIO ? null : (idDeColegio.get(g.colegio) ?? null))}
                >
                  Ver los {g.entregas.length - VISIBLES_POR_GRUPO} restantes en la tabla
                </Link>
              </p>
            ) : null}
          </details>
        ))}
      </div>

      {sinMarcador.length > 0 ? (
        <p className={styles.nota}>
          {sinMarcador.length} {sinMarcador.length === 1 ? "pedido sin marcador" : "pedidos sin marcador"} en
          el mapa. <Link href="/logistica?vista=tabla">Ver los pedidos en la tabla</Link>.
        </p>
      ) : null}
    </section>
  );
}
