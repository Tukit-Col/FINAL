// `/colegios/{colegio}` — P4, el perfil de un colegio, EDITABLE (P1b).
//
// Muestra la ficha del colegio (logo, contactos de la secretaría académica,
// sitio, dirección) y sus grados verificados. La lectura sale de
// `colegio(colegioId)` (`GET /v1/colegios/{id}`, forma `ColegioDetalle`); la
// EDICIÓN vive en el formulario cliente `PerfilColegio`, que manda un PATCH por
// el Route Handler `/api/colegios/{id}` y re-pinta con lo que el backend
// devuelve. Los contactos son del colegio, nunca de un menor (§12.4).
//
// Server Component: `colegio()` sale del origen directamente. Un 404
// (`colegio_no_existe`) se traduce a `notFound()`.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { AcudienteResumen, ColegioDetalle } from "@tukit/contrato";
import { formatearPesos } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import PerfilColegio from "@/components/PerfilColegio";
import { tokenDeSesion } from "@/lib/sesion";
import styles from "../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string }>;
}

// Las preferencias del hogar en frases cortas para el panel: presupuesto por
// hijo (restricción dura) y el dolor que declaró. Vacío si no pidió ninguna.
function resumenPreferencias(p: AcudienteResumen["preferencias"]): string[] {
  const partes: string[] = [];
  if (typeof p.presupuesto_por_hijo === "number") {
    partes.push(`Tope ${formatearPesos(p.presupuesto_por_hijo)}/hijo`);
  }
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

  // Los acudientes del colegio con el estado de su trabajo. Fail-soft: si el
  // backend no responde, el panel queda vacío en vez de tumbar toda la ficha.
  const acudientes = await origenDeDatos()
    .acudientesDeColegio(colegioId)
    .catch(() => []);

  // El nombre del acudiente adulto (PII, §Anexo M) exige el Bearer del admin y
  // el permiso `usuario:leer:nombre`. Fail-soft: sin token o si identidad no
  // responde, el panel cae al id corto que ya mostraba.
  const token = await tokenDeSesion();
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
          {colegio.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.logoGrande} src={colegio.logo_url} alt="" />
          ) : (
            <span className={styles.logoVacioGrande} aria-hidden="true">
              {colegio.nombre.slice(0, 1)}
            </span>
          )}
          <div>
            <h1>{colegio.nombre}</h1>
            <span className={esAliado ? styles.insigniaAliado : styles.insigniaBorrador}>
              {esAliado ? "Aliado" : "Sin listas revisadas"}
            </span>
          </div>
        </div>
      </header>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Ficha del colegio</h2>
        <p className={styles.bajada}>
          Datos de identidad y marca del colegio. Los contactos son de la secretaría académica —
          nunca de un menor. Guardar manda solo lo que cambió.
        </p>
        <PerfilColegio colegio={colegio} />
      </section>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Grados verificados</h2>
        {grados.length === 0 ? (
          <p className={styles.sinGrados}>
            Ningún grado revisado. <Link href="/cola">Sube una lista</Link>.
          </p>
        ) : (
          <ul className={styles.listaGrados}>
            {grados.map((grado) => (
              <li key={grado}>
                <Link
                  href={`/colegios/${encodeURIComponent(colegio.colegio_id)}/${encodeURIComponent(grado)}`}
                >
                  {grado}
                </Link>
              </li>
            ))}
          </ul>
        )}
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
                  <span className={styles.insigniaAliado}>{a.estado}</span>
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
