// `/colegios/{colegio}` — P4, el perfil de un colegio, EDITABLE (P1b).
//
// Un solo bloque "Datos del colegio": arriba la ficha OFICIAL del directorio DUEB
// (solo lectura, fuente principal), y debajo el formulario editable con lo único
// que Tukit administra —el código DANE (llave del DUEB) y el logo (lo que el padre
// ve en el selector de /empezar)—. Los demás datos (sitio, contactos, dirección)
// salen del directorio y no se editan aquí. La lectura sale de `colegio(colegioId)`
// (`GET /v1/colegios/{id}`, forma `ColegioDetalle`); la EDICIÓN vive en el
// formulario cliente `PerfilColegio`, que manda un PATCH por el Route Handler
// `/api/colegios/{id}` y re-pinta con lo que el backend devuelve.
//
// Server Component: `colegio()` sale del origen directamente. Un 404
// (`colegio_no_existe`) se traduce a `notFound()`.

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
import styles from "../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string }>;
}

// Las preferencias del hogar en frases cortas para el panel: hoy solo el dolor
// que declaró. Vacío si no pidió ninguna.
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

  // Los grados verificados no vienen en el detalle; se derivan del selector
  // (`colegios()`), la única superficie que los publica.
  const colegios = await origenDeDatos().colegios();
  const resumen = colegios.find((c) => c.colegio_id === colegioId);
  const grados = resumen?.grados ?? [];
  const esAliado = resumen?.es_partner ?? grados.length > 0;
  // Set para preguntar en O(1) si un grado canónico está verificado.
  const gradosVerificados = new Set(grados);

  // Ficha oficial del DUEB: solo si el colegio tiene DANE. `directorioCompleto`
  // degrada un 404 a `null` (DANE de otra ciudad o escrito a mano), así que la
  // página distingue tres estados: sin DANE, con DANE pero fuera del directorio,
  // y con datos. Nunca rompe.
  const directorio: DirectorioColegio | null = colegio.dane
    ? await origenDeDatos().directorioCompleto(colegio.dane)
    : null;

  // El título usa el nombre OFICIAL del directorio cuando el colegio tiene DANE y
  // el DUEB lo encuentra; si no, el nombre guardado en Tukit. Es solo presentación
  // —el nombre en la base no cambia—, pero evita mostrar un alias interno cuando
  // existe el nombre oficial.
  const titulo = directorio?.nombre ?? colegio.nombre;

  // ------------------------------------------------ Métricas (pedidos pagados)
  // El cruce de pedidos pagados lista los `usuario_id` de los padres que
  // pagaron, así que ahora exige operador/admin: se pide con la cookie de
  // sesión. Sin sesión o sin el rol degrada a `null` y el panel de pedidos
  // muestra un aviso; cobertura y demanda (sin PII) se pintan igual. Los correos
  // (PII) salen aparte del endpoint protegido de acudientes, con el mismo token.
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

  // Los acudientes del colegio con el estado de su trabajo. Fail-soft: si el
  // backend no responde, el panel queda vacío en vez de tumbar toda la ficha.
  const acudientes = await origenDeDatos()
    .acudientesDeColegio(colegioId)
    .catch(() => []);

  // El nombre del acudiente adulto (PII, §Anexo M) exige el Bearer del admin y
  // el permiso `usuario:leer:nombre`. Fail-soft: sin token o si identidad no
  // responde, el panel cae al id corto que ya mostraba. Reusa el `token` de la
  // cookie de sesión leído arriba (mismo Bearer que pide los pedidos pagados).
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
          {/* El logo de Identidad manda; sin el, el del directorio por DANE. */}
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

      {/* UN SOLO bloque "Datos del colegio": arriba la ficha oficial del DUEB
          (solo lectura, fuente principal), y debajo el formulario editable con
          lo único que Tukit administra (DANE y logo). Así no se duplican los
          datos del directorio en un formulario que nadie edita. */}
      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Datos del colegio</h2>
        {!colegio.dane ? (
          // Sin DANE no hay a quién consultar; se guía a completarlo con la
          // edición de arriba, que ahora acepta el código DANE.
          <p className={styles.sinGrados}>
            Sin código DANE. Agrégalo en la ficha de arriba para traer los datos oficiales del
            directorio de Bogotá.
          </p>
        ) : !directorio ? (
          // Con DANE pero el directorio devolvió 404: colegio de otra ciudad o
          // DANE escrito a mano. No es un error de la página.
          <p className={styles.sinGrados}>
            El código DANE {colegio.dane} no está en el directorio de Bogotá (colegio de otra
            ciudad o código escrito a mano).
          </p>
        ) : (
          // Los 9 campos del DUEB. Cada línea se pinta solo si trae dato: un
          // campo vacío no ensucia la ficha. Teléfonos y correos van en lista
          // porque el directorio trae varios.
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
                <dd>{directorio.direccion}</dd>
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

        {/* Lo editable: solo DANE (llave del directorio) y el logo (lo único que
            el padre ve en el selector de /empezar). El resto sale del DUEB. */}
        <h3 className={styles.subtitulo}>Editar</h3>
        <PerfilColegio
          colegio={colegio}
          logoDelDirectorio={logoDelDirectorio(colegio, imagenesDelDirectorio())}
        />
      </section>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Grados</h2>
        {/* Los 15 grados canónicos, siempre. El verificado enlaza a su lista; el
            que aún no tiene lista se pinta gris y NO es clicable (sin `<a>`),
            con texto accesible que explica por qué. Así se ve la cobertura
            completa del colegio, no solo lo ya revisado. */}
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
                  </Link>
                ) : (
                  <span
                    className={styles.gradoSinLista}
                    aria-disabled="true"
                    aria-label={`${grado}: sin lista verificada`}
                  >
                    {grado}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {/* Métricas: cruza pedidos PAGADOS × trabajos × hijos × correo. Los
          conteos y estados no llevan PII; los correos vienen del endpoint
          protegido de acudientes y degradan a identificador sin sesión/rol. */}
      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Métricas</h2>

        {/* Puntos 1 a 4 (padres, niños, tabla y estados) salen del cruce de
            pedidos, que exige operador/admin. Sin sesión o sin rol degradan a un
            aviso; los puntos 5 y 6 (demanda y cobertura) no llevan PII y se
            pintan igual. */}
        {resumenPedidos ? (
          <>
            {/* Puntos 1 y 2: totales de padres y niños con pedido pagado. */}
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

            {/* Punto 3: cada padre (correo) con su nº de niños en el colegio. */}
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

            {/* Punto 4: estado de las solicitudes de kit del colegio. */}
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

        {/* Punto 5: grados SIN lista verificada con más demanda (una tarea por
            familia; las copias de "Editar" no suman, ver `demandaPorGrado`). */}
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

        {/* Punto 6: cobertura y ahorro (medida en vivo de Inteligencia). */}
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
                  {/* El estado enlaza al trabajo: sus fases (percepción →
                      optimización) y, cuando llega a `publicado`, el kit ya
                      armado. Es la ventana para seguir el avance tras aprobar. */}
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
