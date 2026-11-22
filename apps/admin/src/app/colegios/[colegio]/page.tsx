import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import type {
  AcudienteResumen,
  ColegioDetalle,
  DirectorioColegio,
  MetricasColegio,
  ResumenPedidosColegio,
  Sugerencia,
} from "@tukit/contrato";
import { GRADOS_CANONICOS, formatearPesos, logoDeColegio, logoDelDirectorio } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import LogoColegio from "@/components/LogoColegio";
import PerfilColegio from "@/components/PerfilColegio";
import { imagenesDelDirectorio } from "@/lib/directorio";
import { COOKIE_SESION } from "@/lib/sesion";
import { demandaPorGrado } from "@/lib/metricas-colegio";
import { clientesPorColegio } from "@/lib/clientes";
import { claveDireccion } from "@/lib/geocodificador";
import { geocodificadorDelServidor } from "@/lib/geocodificador-servidor";
import MapaColegioCarga from "@/components/MapaColegioCarga";
import styles from "../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string }>;
}

function resumenPreferencias(p: AcudienteResumen["preferencias"]): string[] {
  const partes: string[] = [];
  if (p.dolor_declarado) partes.push(`Le duele: ${p.dolor_declarado.replace(/_/g, " ")}`);
  return partes;
}

export default async function PaginaColegio({ params }: Props) {
  const { colegio: colegioId } = await params;

  let colegio: ColegioDetalle;
  try {
    colegio = await origenDeDatos().colegio(colegioId);
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) notFound();
    throw causa;
  }

  const colegios = await origenDeDatos().colegios();
  const resumen = colegios.find((c) => c.colegio_id === colegioId);
  const grados = resumen?.grados ?? [];
  const esAliado = resumen?.es_partner ?? grados.length > 0;
  const gradosVerificados = new Set(grados);

  const directorio: DirectorioColegio | null = colegio.dane
    ? await origenDeDatos().directorioCompleto(colegio.dane)
    : null;

  const titulo = directorio?.nombre ?? colegio.nombre;

  const origen = origenDeDatos();
  const token = (await cookies()).get(COOKIE_SESION)?.value;

  let resumenPedidos: ResumenPedidosColegio | null = null;
  if (token) {
    try {
      resumenPedidos = await origen.resumenPedidosColegio(token, colegioId);
    } catch (causa) {
      if (causa instanceof ErrorTukit && (causa.estado === 401 || causa.estado === 403)) {
        resumenPedidos = null;
      } else {
        throw causa;
      }
    }
  }

  const metricas: MetricasColegio = await origen.metricasColegio(colegioId);
  const sugerencias: Sugerencia[] = await origen.sugerencias();
  const demanda = demandaPorGrado(sugerencias, colegioId, gradosVerificados);

  const correos = new Map<string, string>();
  let correosCargados = true;
  const idsPadres = resumenPedidos?.por_padre.map((p) => p.usuario_id) ?? [];
  if (idsPadres.length > 0) {
    if (!token) {
      correosCargados = false;
    } else {
      try {
        const acudientes = await origen.acudientesAdmin(token, idsPadres);
        for (const a of acudientes) correos.set(a.usuario_id, a.correo);
      } catch (causa) {
        if (causa instanceof ErrorTukit && (causa.estado === 401 || causa.estado === 403)) {
          correosCargados = false;
        } else {
          throw causa;
        }
      }
    }
  }

  const direccionColegio = directorio?.direccion
    ? {
        direccion: directorio.direccion,
        ciudad: "Bogotá",
        departamento: "Bogotá D.C.",
        localidad: directorio.localidad ?? null,
      }
    : null;
  const geo = direccionColegio ? geocodificadorDelServidor() : null;
  const resultadoGeo =
    direccionColegio && geo
      ? await geo
          .resolver([direccionColegio])
          .then((r) => r.get(claveDireccion(direccionColegio)) ?? null)
          .catch(() => null)
      : null;
  const puntoColegio = resultadoGeo && resultadoGeo !== "pendiente" ? resultadoGeo : null;

  const clientesDelColegio = token
    ? await origenDeDatos()
        .acudientesAdmin(token)
        .then((padron) => clientesPorColegio(padron).find((c) => c.colegio_id === colegioId) ?? null)
        .catch(() => null)
    : null;
  const conteoPorGrado = new Map((clientesDelColegio?.grados ?? []).map((g) => [g.grado, g]));

  const acudientes = await origenDeDatos()
    .acudientesDeColegio(colegioId)
    .catch(() => []);

  const nombres = token
    ? await origenDeDatos()
        .nombresDeUsuarios(
          acudientes.map((a) => a.usuario_id),
          token,
        )
        .catch(() => ({}) as Record<string, string>)
    : ({} as Record<string, string>);

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href="/colegios">← Colegios y listas</Link>
      </nav>

      <header className={styles.encabezado}>
        <div className={styles.perfilIdentidad}>
          <LogoColegio
            src={logoDeColegio(colegio, imagenesDelDirectorio())}
            nombre={titulo}
            claseImagen={styles.logoGrande}
            claseIniciales={styles.logoVacioGrande}
          />
          <div>
            <h1>{titulo}</h1>
            <span className={esAliado ? styles.insigniaAliado : styles.insigniaBorrador}>
              {esAliado ? "Aliado" : "Sin listas revisadas"}
            </span>
          </div>
        </div>
      </header>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Datos del colegio</h2>
        {!colegio.dane ? (
          <p className={styles.sinGrados}>
            Sin código DANE. Agrégalo en la ficha de arriba para traer los datos oficiales del
            directorio de Bogotá.
          </p>
        ) : !directorio ? (
          <p className={styles.sinGrados}>
            El código DANE {colegio.dane} no está en el directorio de Bogotá (colegio de otra
            ciudad o código escrito a mano).
          </p>
        ) : (
          <dl className={styles.ficha}>
            <div>
              <dt>Código DANE</dt>
              <dd>{directorio.dane ?? colegio.dane}</dd>
            </div>
            {directorio.sector ? (
              <div>
                <dt>Sector</dt>
                <dd>{directorio.sector}</dd>
              </div>
            ) : null}
            {directorio.localidad ? (
              <div>
                <dt>Localidad</dt>
                <dd>{directorio.localidad}</dd>
              </div>
            ) : null}
            {directorio.direccion ? (
              <div>
                <dt>Dirección</dt>
                <dd>
                  {directorio.direccion}
                  {puntoColegio && (
                    <div className={styles.mapaColegio}>
                      <MapaColegioCarga punto={puntoColegio} nombre={titulo} />
                    </div>
                  )}
                </dd>
              </div>
            ) : null}
            {directorio.telefonos && directorio.telefonos.length > 0 ? (
              <div>
                <dt>Teléfonos</dt>
                <dd>
                  <ul className={styles.listaContactos}>
                    {directorio.telefonos.map((tel) => (
                      <li key={tel}>{tel}</li>
                    ))}
                  </ul>
                </dd>
              </div>
            ) : null}
            {directorio.correos && directorio.correos.length > 0 ? (
              <div>
                <dt>Correos</dt>
                <dd>
                  <ul className={styles.listaContactos}>
                    {directorio.correos.map((correo) => (
                      <li key={correo}>{correo}</li>
                    ))}
                  </ul>
                </dd>
              </div>
            ) : null}
            {directorio.sitio_web ? (
              <div>
                <dt>Sitio web</dt>
                <dd>{directorio.sitio_web}</dd>
              </div>
            ) : null}
            {directorio.rector ? (
              <div>
                <dt>Rector</dt>
                <dd>{directorio.rector}</dd>
              </div>
            ) : null}
          </dl>
        )}

        <h3 className={styles.subtitulo}>Editar</h3>
        <PerfilColegio
          colegio={colegio}
          logoDelDirectorio={logoDelDirectorio(colegio, imagenesDelDirectorio())}
        />
      </section>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Grados</h2>
        <ul className={styles.listaGrados}>
          {GRADOS_CANONICOS.map((grado) => {
            const verificado = gradosVerificados.has(grado);
            return (
              <li key={grado}>
                {verificado ? (
                  <Link
                    href={`/colegios/${encodeURIComponent(colegio.colegio_id)}/${encodeURIComponent(grado)}`}
                    className={styles.gradoVerificado}
                  >
                    {grado}
                    {conteoPorGrado.get(grado) && (
                      <span className={styles.conteoGrado}>
                        {" "}· {conteoPorGrado.get(grado)!.hijos}{" "}
                        {conteoPorGrado.get(grado)!.hijos === 1 ? "hijo" : "hijos"}
                      </span>
                    )}
                  </Link>
                ) : (
                  <span
                    className={styles.gradoSinLista}
                    aria-disabled="true"
                    aria-label={`${grado}: sin lista verificada`}
                  >
                    {grado}
                    {conteoPorGrado.get(grado) && (
                      <span className={styles.conteoGrado}>
                        {" "}· {conteoPorGrado.get(grado)!.hijos}{" "}
                        {conteoPorGrado.get(grado)!.hijos === 1 ? "hijo" : "hijos"}
                      </span>
                    )}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Métricas</h2>

        {resumenPedidos ? (
          <>
            <dl className={styles.resumen}>
              <div>
                <dt>Padres con pedido pagado</dt>
                <dd className="cifra">{resumenPedidos.total_padres}</dd>
              </div>
              <div>
                <dt>Niños en esos pedidos</dt>
                <dd className="cifra">{resumenPedidos.total_ninos}</dd>
              </div>
            </dl>

            <h3 className={styles.metricaTitulo}>Padres con pedido pagado</h3>
            {resumenPedidos.por_padre.length === 0 ? (
              <p className={styles.vacio}>Todavía no hay pedidos pagados de este colegio.</p>
            ) : (
              <>
                {!correosCargados ? (
                  <p className={styles.avisoCorreos}>
                    No pudimos cargar los correos (falta sesión o rol de operador/admin). Se
                    muestran los identificadores.
                  </p>
                ) : null}
                <div className={styles.tablaMarco}>
                <table className={styles.tabla}>
                  <thead>
                    <tr>
                      <th scope="col">Padre</th>
                      <th scope="col">Niños</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumenPedidos.por_padre.map((p) => (
                      <tr key={p.usuario_id}>
                        <th scope="row" className={styles.celdaDato}>
                          {correos.get(p.usuario_id) ?? p.usuario_id}
                        </th>
                        <td className="cifra">{p.ninos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </>
            )}

            <h3 className={styles.metricaTitulo}>Solicitudes de kit</h3>
            <div className={styles.estados}>
              <span className={`${styles.estadoPill} ${styles.estadoEspera}`}>
                <span className="cifra">{resumenPedidos.estados_trabajos.espera_revision}</span>{" "}
                esperando revisión
              </span>
              <span className={`${styles.estadoPill} ${styles.estadoPublicado}`}>
                <span className="cifra">{resumenPedidos.estados_trabajos.publicado}</span> publicadas
              </span>
              <span className={`${styles.estadoPill} ${styles.estadoFallido}`}>
                <span className="cifra">{resumenPedidos.estados_trabajos.fallido}</span> fallidas
              </span>
            </div>
          </>
        ) : (
          <p className={styles.avisoCorreos}>
            No pudimos cargar los pedidos pagados (falta sesión o rol de operador/admin).
          </p>
        )}

        <h3 className={styles.metricaTitulo}>Grados sin lista con más demanda</h3>
        {demanda.length === 0 ? (
          <p className={styles.vacio}>No hay solicitudes de padres para grados sin lista.</p>
        ) : (
          <ul className={styles.demanda}>
            {demanda.map((d) => (
              <li key={d.grado}>
                <span>{d.grado}</span>
                <span>
                  <span className="cifra">{d.solicitudes}</span>{" "}
                  {d.solicitudes === 1 ? "solicitud" : "solicitudes"}
                </span>
              </li>
            ))}
          </ul>
        )}

        <h3 className={styles.metricaTitulo}>Cobertura y ahorro</h3>
        <dl className={styles.ficha}>
          <div>
            <dt>Cobertura</dt>
            <dd>
              <span className="cifra">{Math.round(metricas.cobertura * 100)}</span>%
            </dd>
          </div>
          <div>
            <dt>Ahorro total</dt>
            <dd>{formatearPesos(metricas.ahorro_total_cop)}</dd>
          </div>
          <div>
            <dt>Kits armados</dt>
            <dd className="cifra">{metricas.kits_armados}</dd>
          </div>
        </dl>
      </section>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Acudientes</h2>
        <p className={styles.bajada}>
          Quiénes han pedido kits para este colegio, para qué grado y con qué preferencias.
          Sin datos de menores: el identificador del acudiente, el grado que pidió y los
          pesos del hogar —nunca el apodo ni el correo.
        </p>
        {acudientes.length === 0 ? (
          <p className={styles.sinGrados}>Ningún acudiente todavía.</p>
        ) : (
          <ul className={styles.listaAcudientes}>
            {acudientes.map((a) => {
              const prefs = resumenPreferencias(a.preferencias);
              return (
                <li key={a.usuario_id}>
                  {nombres[a.usuario_id] ? (
                    <span className={styles.nombreAcudiente}>{nombres[a.usuario_id]}</span>
                  ) : (
                    <code>{a.usuario_id.slice(0, 8)}</code>
                  )}
                  {a.grados.length > 0 ? (
                    <span className={styles.gradosAcudiente}>{a.grados.join(", ")}</span>
                  ) : null}
                  <Link href={`/trabajos/${a.trabajo_id}`} className={styles.estadoTrabajo}>
                    {a.estado}
                  </Link>
                  <time dateTime={a.actualizado_en}>{a.actualizado_en.slice(0, 10)}</time>
                  {prefs.length > 0 ? (
                    <span className={styles.prefsAcudiente}>{prefs.join(" · ")}</span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
