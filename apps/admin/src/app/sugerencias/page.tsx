// `/sugerencias` — P4, el backlog de sugerencias de acudientes (P3c).
//
// Cuando un acudiente cuyo (colegio, grado) no tiene lista verificada sugiere la
// suya, cae en este backlog. Cada entrada trae el colegio, el grado, el año, su
// estado, si vino con PDF y quién la pidió —SOLO por `contacto_referencia` (el
// usuario_id que identidad emite), etiquetado como referencia; NUNCA correo ni
// teléfono ni nombre: esa PII vive solo en identidad—. "Onboardear" lanza el
// flujo de /onboarding prefijado con colegio y grado.
//
// Server Component: `sugerencias()` sale del origen directamente
// (`dynamic = "force-dynamic"`).

import Link from "next/link";
import { Inbox } from "lucide-react";
import type { Sugerencia } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import styles from "./Sugerencias.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaSugerencias() {
  const backlog: Sugerencia[] = await origenDeDatos().sugerencias();

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Sugerencias de acudientes</h1>
          <p className={styles.bajada}>
            Listas que pidieron acudientes cuyo colegio y grado aún no están verificados.
            Onboardear una la saca del backlog y la deja disponible para todos.
          </p>
        </div>
      </header>

      {backlog.length === 0 ? (
        <div className={styles.vacio}>
          <Inbox size={22} aria-hidden="true" />
          <p>No hay sugerencias en el backlog.</p>
          <Link className={styles.enlaceOnboarding} href="/onboarding">
            Ir a subir una lista
          </Link>
        </div>
      ) : (
        <table className={styles.tabla}>
          <thead>
            <tr>
              <th>Colegio</th>
              <th>Grado</th>
              <th>Año</th>
              <th>Estado</th>
              <th>Documento</th>
              <th>Referencia del acudiente</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {backlog.map((s) => {
              // "Onboardear" prefija el onboarding con colegio y grado (solo si
              // los hay: una sugerencia puede venir sin ambos).
              const qs = new URLSearchParams();
              if (s.colegio_id) qs.set("colegio", s.colegio_id);
              if (s.grado) qs.set("grado", s.grado);
              const cadena = qs.toString();
              return (
                <tr key={s.tarea_id}>
                  <td>
                    {s.colegio_id ? <code>{s.colegio_id}</code> : <span className={styles.vacioCelda}>—</span>}
                  </td>
                  <td>{s.grado ?? "—"}</td>
                  <td className="cifra">{s.anio_lectivo ?? "—"}</td>
                  <td>{s.estado}</td>
                  <td>
                    <span
                      className={s.tiene_documento ? styles.insigniaDoc : styles.insigniaSinDoc}
                    >
                      {s.tiene_documento ? "Con PDF" : "Sin PDF"}
                    </span>
                  </td>
                  <td>
                    {/* La ÚNICA traza al acudiente permitida: el usuario_id como
                        referencia. Nunca correo, teléfono ni nombre. */}
                    {s.contacto_referencia ? (
                      <code className={styles.referencia}>{s.contacto_referencia}</code>
                    ) : (
                      <span className={styles.vacioCelda}>sin referencia</span>
                    )}
                  </td>
                  <td>
                    <Link
                      className={styles.onboardear}
                      href={`/onboarding${cadena ? `?${cadena}` : ""}`}
                    >
                      Onboardear
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
