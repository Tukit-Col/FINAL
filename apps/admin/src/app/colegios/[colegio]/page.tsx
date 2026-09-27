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
import { notFound } from "next/navigation";
import type { ColegioDetalle, DirectorioColegio } from "@tukit/contrato";
import { GRADOS_CANONICOS } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import PerfilColegio from "@/components/PerfilColegio";
import styles from "../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string }>;
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

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href="/colegios">← Colegios y listas</Link>
      </nav>

      <header className={styles.encabezado}>
        <div className={styles.perfilIdentidad}>
          {colegio.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.logoGrande} src={colegio.logo_url} alt="" />
          ) : (
            <span className={styles.logoVacioGrande} aria-hidden="true">
              {titulo.slice(0, 1)}
            </span>
          )}
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
        <PerfilColegio colegio={colegio} />
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
    </div>
  );
}
