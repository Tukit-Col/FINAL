// `/` — la cola de revision (AD-02, AD-03).
//
// Server Component: lee el origen directamente. No hay ningun `fetch` de por
// medio porque no hace falta —la lectura no pasa por el navegador— y meter un
// Route Handler aqui solo agregaria un salto de red contra uno mismo.

import Link from "next/link";
import type { EntradaCola, EstadoTrabajo } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { formatearFecha, haceCuanto, TITULO_ESTADO_TRABAJO } from "@/lib/formato";
import styles from "./Cola.module.css";

export const dynamic = "force-dynamic";

// Lo primero es lo que espera a una persona; despues, lo que mas trabajo
// pide; y a igualdad de trabajo, lo que lleva mas rato esperando, que es lo
// unico que impide que un trabajo pequeno se quede al fondo para siempre.
// Lo publicado sale de la cola: ya no es trabajo, es historial.
const PRIORIDAD: Record<EstadoTrabajo, number> = {
  espera_revision: 0,
  fallido: 1,
  procesando: 2,
  encolado: 3,
  publicado: 4,
};

function ordenar(entradas: readonly EntradaCola[]): EntradaCola[] {
  return [...entradas].sort(
    (a, b) =>
      PRIORIDAD[a.estado] - PRIORIDAD[b.estado] ||
      b.lineas_pendientes - a.lineas_pendientes ||
      Date.parse(a.recibido_en) - Date.parse(b.recibido_en),
  );
}

function ColaVacia() {
  return (
    <div className={styles.vacia}>
      <h2>No hay nada en la cola.</h2>
      <p>
        La cola se llena sola: cada trabajo que un acudiente crea entra aquí y espera a que
        alguien lo revise. Si está vacía es porque todavía no se ha creado ninguno en este
        entorno, no porque algo esté roto.
      </p>
      <p>
        Para crear uno, abre la app del acudiente en{" "}
        <a href="http://localhost:3000/empezar" className={styles.enlaceExterno}>
          http://localhost:3000/empezar
        </a>{" "}
        y arma un kit. Con el origen simulado las dos apps comparten el mismo almacén en
        disco, así que el trabajo aparece aquí en cuanto se cree. La lista más rica del
        corpus es <code>2.13</code> · <code>Sexto</code>: trae útiles, textos, licencias
        digitales, diferidos y uniformes, o sea todos los casos que hay que saber revisar.
      </p>
      <p className={styles.pistaVacia}>
        El trabajo tarda unos segundos en llegar a <code>espera_revision</code>. Si quieres
        que se quede esperando tu decisión en vez de publicarse solo, levanta esta app con{" "}
        <code>TUKIT_SIMULADO_AUTOAPROBAR=false</code>.
      </p>
    </div>
  );
}

export default async function PaginaCola() {
  const { entradas } = await origenDeDatos().cola();
  const ordenadas = ordenar(entradas);
  // Un solo reloj para toda la tabla: si cada fila llamara a `Date.now()`, dos
  // trabajos creados en el mismo instante podrian mostrar minutos distintos.
  //
  // `react-hooks/purity` marca el reloj porque en un componente de cliente
  // produciria un render inestable. Aqui no hay tal: es un Server Component
  // con `force-dynamic` que se renderiza una vez por peticion y nunca se
  // hidrata, asi que "hace 4 min" se calcula una sola vez y no baila.
  // eslint-disable-next-line react-hooks/purity
  const ahora = Date.now();

  const enEspera = ordenadas.filter((e) => e.estado === "espera_revision");
  const pendientes = enEspera.reduce((total, e) => total + e.lineas_pendientes, 0);

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Cola de revisión</h1>
          <p className={styles.bajada}>
            Ningún kit llega al acudiente sin pasar por aquí. Mientras el trabajo esté en
            espera, el acudiente ve una pantalla de espera y no un kit a medias.
          </p>
        </div>
        <dl className={styles.resumen}>
          <div>
            <dt>Esperando a una persona</dt>
            <dd className="cifra">{enEspera.length}</dd>
          </div>
          <div>
            <dt>Líneas por resolver</dt>
            <dd className="cifra">{pendientes}</dd>
          </div>
          <div>
            <dt>Trabajos en total</dt>
            <dd className="cifra">{ordenadas.length}</dd>
          </div>
        </dl>
      </header>

      {ordenadas.length === 0 ? (
        <ColaVacia />
      ) : (
        <div className={styles.marco}>
          <table className={styles.tabla}>
            <caption className={styles.leyenda}>
              Ordenada por lo que más trabajo pide: primero lo que espera revisión, después
              por líneas pendientes, y a igualdad de líneas lo que lleva más rato esperando.
            </caption>
            <thead>
              <tr>
                <th scope="col">Trabajo</th>
                <th scope="col">Estado</th>
                <th scope="col">Recibido</th>
                <th scope="col" className={styles.num}>
                  Hijos
                </th>
                <th scope="col" className={styles.num}>
                  Pendientes
                </th>
                <th scope="col" className={styles.num}>
                  Líneas
                </th>
                <th scope="col">Colegios</th>
                <th scope="col">Grados</th>
                <th scope="col">
                  <span className={styles.oculto}>Acción</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {ordenadas.map((entrada) => {
                const espera = entrada.estado === "espera_revision";
                const publicado = entrada.estado === "publicado";
                return (
                  <tr
                    key={entrada.trabajo_id}
                    className={[
                      espera ? styles.filaEspera : "",
                      publicado ? styles.filaPublicada : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <th scope="row" className={styles.identificador}>
                      <Link href={`/trabajos/${entrada.trabajo_id}`}>
                        <code>{entrada.trabajo_id}</code>
                      </Link>
                    </th>
                    <td>
                      <span className={`${styles.estado} ${styles[`estado_${entrada.estado}`]}`}>
                        {TITULO_ESTADO_TRABAJO[entrada.estado]}
                      </span>
                    </td>
                    <td className={styles.fecha}>
                      <span>{haceCuanto(entrada.recibido_en, ahora)}</span>
                      <span className={styles.fechaExacta}>
                        {formatearFecha(entrada.recibido_en)}
                      </span>
                    </td>
                    <td className={`${styles.num} cifra`}>{entrada.hijos}</td>
                    <td className={`${styles.num} cifra`}>
                      {entrada.lineas_pendientes > 0 ? (
                        <span className={styles.pendientes}>{entrada.lineas_pendientes}</span>
                      ) : (
                        <span className={styles.cero}>0</span>
                      )}
                    </td>
                    <td className={`${styles.num} cifra ${styles.tenue}`}>
                      {entrada.lineas_totales}
                    </td>
                    <td className={styles.lista}>{entrada.colegios.join(", ") || "—"}</td>
                    <td className={styles.lista}>{entrada.grados.join(", ") || "—"}</td>
                    <td className={styles.accionCelda}>
                      <Link
                        href={`/trabajos/${entrada.trabajo_id}`}
                        className={espera ? styles.accion : styles.accionSecundaria}
                      >
                        {publicado ? "Ver" : "Revisar"}
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
