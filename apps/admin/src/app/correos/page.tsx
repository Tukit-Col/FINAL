import Form from "next/form";
import Link from "next/link";
import type { BandejaCorreos, EstadoCorreo } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import AvisoAcceso from "@/components/AvisoAcceso";
import Chip, { Chips } from "@/components/ui/Chip";
import EstadoVacio from "@/components/ui/EstadoVacio";
import {
  ESTADOS_CORREO,
  ETIQUETA_ESTADO_CORREO,
  explicarDetalle,
  hayFiltrosCorreos,
  hrefCorreos,
  leerFiltrosCorreos,
} from "@/lib/correos";
import { formatearFecha } from "@/lib/formato";
import { motivoDeFallo } from "@/lib/logistica";
import { tokenDeSesion } from "@/lib/sesion";
import styles from "./Correos.module.css";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const CLASE_ESTADO: Record<EstadoCorreo, string> = {
  enviada: styles.estadoEnviada,
  fallida: styles.estadoFallida,
  omitida: styles.estadoOmitida,
};

function Encabezado() {
  return (
    <header className={styles.encabezado}>
      <h1>Correos enviados</h1>
      <p className={styles.bajada}>
        Cada aviso que mandó el sistema y qué pasó con él. Solo se guarda el dominio del destino, nunca la
        dirección.
      </p>
    </header>
  );
}

export default async function PaginaCorreos({ searchParams }: Props) {
  const token = await tokenDeSesion();
  if (!token) {
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo="sin_sesion" />
      </div>
    );
  }

  const filtros = leerFiltrosCorreos(await searchParams);
  let bandeja: BandejaCorreos;
  try {
    bandeja = await origenDeDatos().correos(token, filtros);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit)) throw causa;
    return (
      <div className={styles.pagina}>
        <Encabezado />
        <AvisoAcceso motivo={motivoDeFallo(causa.estado)} />
      </div>
    );
  }
  const { resumen, correos } = bandeja;

  return (
    <div className={styles.pagina}>
      <Encabezado />

      <Chips etiqueta="Filtrar por estado">
        <Chip href={hrefCorreos(filtros, { estado: "" })} activo={!filtros.estado}>
          Todos
        </Chip>
        {ESTADOS_CORREO.map((estado) => (
          <Chip
            key={estado}
            href={hrefCorreos(filtros, { estado })}
            activo={filtros.estado === estado}
            hay={estado !== "enviada" && (resumen[estado] ?? 0) > 0}
          >
            {ETIQUETA_ESTADO_CORREO[estado]} <span className="cifra">{resumen[estado] ?? 0}</span>
          </Chip>
        ))}
      </Chips>

      <Form action="/correos" className={styles.filtros} aria-label="Buscar avisos" key={JSON.stringify(filtros)}>
        {filtros.estado && <input type="hidden" name="estado" value={filtros.estado} />}
        <div className={styles.campoFiltro}>
          <label htmlFor="c-pedido">Código de pedido</label>
          <input id="c-pedido" name="pedido" defaultValue={filtros.pedido} autoComplete="off" />
        </div>
        <div className={styles.campoFiltro}>
          <label htmlFor="c-caso">Código de caso</label>
          <input id="c-caso" name="caso" defaultValue={filtros.caso} autoComplete="off" />
        </div>
        <div className={styles.campoFiltro}>
          <label htmlFor="c-plantilla">Plantilla</label>
          <input id="c-plantilla" name="plantilla" defaultValue={filtros.plantilla} autoComplete="off" />
        </div>
        <button type="submit">Buscar</button>
        {hayFiltrosCorreos(filtros) && <Link href="/correos">Limpiar</Link>}
      </Form>

      {correos.length === 0 ? (
        <EstadoVacio
          titulo={hayFiltrosCorreos(filtros) ? "Ningún aviso coincide" : "Aún no se ha enviado ningún aviso"}
        >
          {hayFiltrosCorreos(filtros)
            ? "Prueba con otro filtro o limpia la búsqueda."
            : "Aparecen aquí cuando un pago, un despacho o un caso genera un aviso."}
        </EstadoVacio>
      ) : (
        <div className={styles.envolturaTabla}>
          <table className={styles.tabla}>
            <thead>
              <tr>
                <th>Cuándo</th>
                <th>Estado</th>
                <th>Asunto</th>
                <th>Destino</th>
                <th>Qué pasó</th>
              </tr>
            </thead>
            <tbody>
              {correos.map((c) => (
                <tr key={c.id}>
                  <td className={styles.tenue}>{c.creado_en ? formatearFecha(c.creado_en) : "—"}</td>
                  <td>
                    <span className={`${styles.estado} ${CLASE_ESTADO[c.estado]}`}>
                      {ETIQUETA_ESTADO_CORREO[c.estado]}
                    </span>
                  </td>
                  <td>
                    <span className={styles.asunto}>{c.asunto ?? c.plantilla}</span>
                    <br />
                    <span className={styles.tenue}>
                      {c.plantilla}
                      {c.pedido ? ` · pedido ${c.pedido}` : ""}
                      {c.caso ? ` · caso ${c.caso}` : ""}
                    </span>
                  </td>
                  <td>{c.destino_dominio ? `@${c.destino_dominio}` : "—"}</td>
                  <td>{explicarDetalle(c.detalle)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
