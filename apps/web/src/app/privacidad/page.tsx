import Link from "next/link";
import { redirect } from "next/navigation";
import { origenDeDatos } from "@tukit/contrato/servidor";
import { totalDeSeccion, type MisDatos, type SeccionRemota } from "@tukit/contrato";
import Sidebar from "@/components/Sidebar";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import { esLimiteDeTasa } from "@/lib/limite";
import { sesionActual, tokenDeSesion } from "@/lib/sesion";
import dashboard from "../dashboard/Dashboard.module.css";
import styles from "./Privacidad.module.css";
import AccionesPrivacidad from "./AccionesPrivacidad";

export const dynamic = "force-dynamic";
export const metadata = { title: "Privacidad y mis datos | Tukit" };

function fecha(iso: string | null): string {
  if (!iso) return "sin fecha";
  return new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}

function conteo(seccion: SeccionRemota, una: string, varias: string): string {
  const total = totalDeSeccion(seccion);
  if (total === null) return "No pudimos consultarlo ahora.";
  if (total === 0) return `No tienes ${varias}.`;
  return total === 1 ? `1 ${una}.` : `${total} ${varias}.`;
}

const REGIMEN: Record<string, string> = {
  registro_titular: "Política de datos y términos de tu cuenta",
  registro_menor: "Autorización para los datos de un hijo",
};

export default async function PaginaPrivacidad() {
  return conAvisoDeLimite(panel);
}

async function panel() {
  const sesion = await sesionActual();
  if (!sesion) redirect("/ingresar");

  let datos: MisDatos | null = null;
  try {
    const token = await tokenDeSesion();
    if (token) datos = await origenDeDatos().misDatos(token);
  } catch (causa) {
    if (esLimiteDeTasa(causa)) throw causa;
  }

  const nombreCuenta = sesion.nombre.trim() || sesion.correo;
  const vigentes = datos?.consentimientos.filter((c) => !c.revocado_en).length ?? 0;

  return (
    <div className={dashboard.shell}>
      <div className={dashboard.body}>
        <div className={dashboard.main}>
          <Sidebar nombreCuenta={nombreCuenta} />

          <div className={dashboard.content}>
            <div className={dashboard.pageHeader}>
              <div className={dashboard.pageHeader__titles}>
                <h1>Privacidad y mis datos</h1>
                <p>
                  Aquí ves qué datos tuyos guardamos, puedes descargar una copia y puedes pedir que los
                  borremos. Así lo dice la Ley 1581 de 2012.{" "}
                  <Link href="/legal/privacidad">Lee la política completa</Link>.
                </p>
              </div>
            </div>

            {!datos ? (
              <section className={dashboard.card}>
                <p className={dashboard.hijosError}>
                  No pudimos cargar tus datos en este momento. Vuelve a intentarlo en unos minutos o
                  escríbenos desde la <Link href="/legal/privacidad">política de datos</Link>.
                </p>
              </section>
            ) : (
              <>
                <section id="cuenta" className={dashboard.card}>
                  <div className={dashboard.sectionHeader}>
                    <h2>Tu cuenta</h2>
                  </div>
                  <dl className={styles.datos}>
                    <dt>Nombre</dt>
                    <dd>{datos.cuenta.nombre || "Sin nombre"}</dd>
                    <dt>Correo</dt>
                    <dd>{datos.cuenta.correo ?? "Sin correo"}</dd>
                    <dt>Celular</dt>
                    <dd>{datos.cuenta.celular ?? "Sin celular"}</dd>
                    <dt>Cuenta creada</dt>
                    <dd>{fecha(datos.cuenta.creado_en)}</dd>
                  </dl>
                  <p className={styles.nota}>
                    Por seguridad mostramos tu correo y tu celular a medias. En la copia que descargues van
                    completos.
                  </p>
                </section>

                <section id="hijos" className={dashboard.card}>
                  <div className={dashboard.sectionHeader}>
                    <h2>Tus hijos</h2>
                  </div>
                  {datos.hijos.length === 0 ? (
                    <p className={dashboard.sinPedidos}>No tienes hijos registrados.</p>
                  ) : (
                    <ul className={styles.lista}>
                      {datos.hijos.map((h, i) => (
                        <li key={h.matricula_id}>
                          <strong>{h.apodo?.trim() || `Hijo ${i + 1}`}</strong>
                          <span>{h.grado}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className={styles.nota}>
                    De tus hijos solo guardamos el apodo que escribiste, el colegio y el grado. Nunca su nombre
                    legal ni su documento.
                  </p>
                </section>

                <section id="direcciones" className={dashboard.card}>
                  <div className={dashboard.sectionHeader}>
                    <h2>Tus direcciones</h2>
                  </div>
                  {datos.direcciones.length === 0 ? (
                    <p className={dashboard.sinPedidos}>No tienes direcciones guardadas.</p>
                  ) : (
                    <ul className={styles.lista}>
                      {datos.direcciones.map((d) => (
                        <li key={d.direccion_id}>
                          <strong>{d.etiqueta}</strong>
                          <span>
                            {d.ciudad}
                            {d.localidad ? `, ${d.localidad}` : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section id="autorizaciones" className={dashboard.card}>
                  <div className={dashboard.sectionHeader}>
                    <h2>Tus autorizaciones</h2>
                  </div>
                  {datos.consentimientos.length === 0 ? (
                    <p className={dashboard.sinPedidos}>No hay autorizaciones registradas.</p>
                  ) : (
                    <ul className={styles.lista}>
                      {datos.consentimientos.map((c, i) => (
                        <li key={`${c.regimen}-${c.aceptado_en}-${i}`}>
                          <strong>{REGIMEN[c.regimen] ?? c.regimen}</strong>
                          <span>
                            Versión {c.version}, aceptada el {fecha(c.aceptado_en)}
                            {c.revocado_en ? `. Revocada el ${fecha(c.revocado_en)}.` : "."}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section id="actividad" className={dashboard.card}>
                  <div className={dashboard.sectionHeader}>
                    <h2>Tu actividad en Tukit</h2>
                  </div>
                  <dl className={styles.datos}>
                    <dt>Pedidos</dt>
                    <dd>{conteo(datos.pedidos, "pedido", "pedidos")}</dd>
                    <dt>Casos de ayuda</dt>
                    <dd>{conteo(datos.casos, "caso", "casos")}</dd>
                    <dt>Solicitudes de kit</dt>
                    <dd>{conteo(datos.trabajos_kit, "solicitud", "solicitudes")}</dd>
                  </dl>
                  <p className={styles.nota}>
                    El detalle de cada uno está en <Link href="/dashboard">Mi cuenta</Link>.
                  </p>
                </section>

                <AccionesPrivacidad
                  frase={datos.supresion.frase_confirmacion}
                  suprimido={datos.supresion.suprimido}
                  conservado={datos.supresion.conservado}
                  autorizacionesVigentes={vigentes}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
