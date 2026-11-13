import { cookies } from "next/headers";
import { origenDeDatos, ErrorTukit, type AcudienteAdmin } from "@tukit/contrato/servidor";
import { COOKIE_SESION } from "@/lib/sesion";
import { formatearFecha } from "@/lib/formato";
import { rotuloDeHijo } from "@/lib/pedido-admin";
import styles from "./Clientes.module.css";

export const dynamic = "force-dynamic";

// El padrón de familias registradas. Vive detrás del token: identidad gatea el
// endpoint (401 sin token, 403 sin rol admin/operador), así que esta página lee
// la cookie de sesión —la misma que puso la web al entrar— y la pasa como
// Bearer. Sin sesión o sin permiso NO se muestra un error crudo, sino un aviso
// claro. No muestra ningún dato que identifique a un menor (ni apodo): Ley 1581.

/** El aviso de guardia: nunca un stack trace, siempre una frase que dice qué
 *  hacer. Cubre "no hay sesión", "la sesión expiró" y "no tienes el rol". */
function Aviso({ titulo, cuerpo }: { titulo: string; cuerpo: string }) {
  return (
    <div className={styles.pagina}>
      <div className={styles.aviso}>
        <h2>{titulo}</h2>
        <p>{cuerpo}</p>
      </div>
    </div>
  );
}

/** El texto de un hijo: un rótulo estable con su posición, grado y colegio. Ni
 *  apodo ni nombre de menor llegan a esta vista (Ley 1581). */
function textoHijo(hijo: AcudienteAdmin["hijos"][number], indice: number): string {
  return `${rotuloDeHijo(hijo, indice)} · ${hijo.colegio_nombre}`;
}

export default async function PaginaClientes() {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return (
      <Aviso
        titulo="Inicia sesión para ver a los clientes"
        cuerpo="Este padrón es solo para el equipo interno. Entra con tu cuenta de operador o admin y vuelve a esta pestaña."
      />
    );
  }

  let acudientes: AcudienteAdmin[];
  try {
    acudientes = await origenDeDatos().acudientesAdmin(token);
  } catch (error) {
    if (error instanceof ErrorTukit && error.estado === 401) {
      return (
        <Aviso
          titulo="Tu sesión expiró"
          cuerpo="Vuelve a entrar con tu cuenta para ver el padrón de clientes."
        />
      );
    }
    // El limite de tasa (ADR 0047): ni sesion vencida ni servicio caido. Su
    // mensaje ya dice cuanto esperar.
    if (error instanceof ErrorTukit && error.estado === 429) {
      return <Aviso titulo="Danos un momento" cuerpo={error.message} />;
    }
    if (error instanceof ErrorTukit && error.estado === 403) {
      return (
        <Aviso
          titulo="Esta vista es solo para el equipo interno"
          cuerpo="Tu cuenta no tiene el rol de operador o admin que este padrón requiere."
        />
      );
    }
    return (
      <Aviso
        titulo="No pudimos cargar el padrón"
        cuerpo="El servicio de identidad no respondió. Revisa que los servicios estén arriba (make arriba) e inténtalo de nuevo."
      />
    );
  }

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Clientes</h1>
          <p className={styles.bajada}>
            Las familias registradas en Tukit y los hijos que tienen matriculados. Del menor solo se
            muestra su posición, grado y colegio; ni apodo ni nombre legal.
          </p>
        </div>
        <dl className={styles.resumen}>
          <div>
            <dt>Familias</dt>
            <dd className="cifra">{acudientes.length}</dd>
          </div>
        </dl>
      </header>

      {acudientes.length === 0 ? (
        <p className={styles.vacio}>Todavía no hay familias registradas.</p>
      ) : (
        <div className={styles.marco}>
          <table className={styles.tabla}>
            <caption className={styles.oculto}>Padrón de familias registradas y sus hijos.</caption>
            <thead>
              <tr>
                <th scope="col">Correo</th>
                <th scope="col">Celular</th>
                <th scope="col">Registro</th>
                <th scope="col" className={styles.num}>
                  Hijos
                </th>
                <th scope="col">Hijos matriculados</th>
              </tr>
            </thead>
            <tbody>
              {acudientes.map((acudiente) => (
                <tr key={acudiente.usuario_id}>
                  <th scope="row" className={styles.correo}>
                    {acudiente.correo}
                  </th>
                  <td className={acudiente.celular ? undefined : styles.tenue}>
                    {acudiente.celular ?? "—"}
                  </td>
                  <td className={styles.fechaExacta}>{formatearFecha(acudiente.creado_en)}</td>
                  <td className={`${styles.num} cifra`}>{acudiente.hijos.length}</td>
                  <td>
                    {acudiente.hijos.length === 0 ? (
                      <span className={styles.tenue}>Sin hijos matriculados</span>
                    ) : (
                      <ul className={styles.hijos}>
                        {acudiente.hijos.map((hijo, indice) => (
                          <li key={`${acudiente.usuario_id}-${indice}`}>{textoHijo(hijo, indice)}</li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
