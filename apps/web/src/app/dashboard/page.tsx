// El panel del acudiente. Todo sale del backend real: identidad emite la
// sesion, comercio sirve los pedidos pagados (`/v1/comercio/mis-pedidos`) e
// inteligencia sirve las solicitudes de kit del portador (`GET /v1/trabajos`,
// autenticado por Bearer). Los hijos se derivan de esas solicitudes —por
// referencia sintetica, colegio y grado, nunca un nombre de menor (Anexo M,
// Ley 1581)—, que es la unica lectura real que expone esos perfiles hoy.
//
// Es un Server Component: lee la sesion de la cookie httponly (`sesionActual`)
// y reenvia el Bearer (`tokenDeSesion`) a inteligencia. Sin sesion, redirige a
// /ingresar, fail-closed como el resto de las rutas protegidas.
import Link from "next/link";
import { redirect } from "next/navigation";
import { UserPlus, LifeBuoy, Users } from "lucide-react";
import {
  ETIQUETA_ESTADO_PEDIDO,
  formatearPesos,
  type Pedido,
  type TrabajoResumen,
} from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import Sidebar from "@/components/Sidebar";
import EtapasSolicitud from "./EtapasSolicitud";
import { sesionActual, tokenDeSesion } from "@/lib/sesion";
import styles from "./Dashboard.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Mi cuenta — Tukit" };

// Como se le nombra al acudiente cada estado de su solicitud, y a donde lo
// lleva. Un kit publicado se abre en su detalle; cualquier otro estado (en
// cola, procesando, en revision o fallido) vive en la pantalla de espera, que
// ya sabe pintar cada uno. La etiqueta es del acudiente, no la tecnica.
const ESTADO_SOLICITUD: Record<TrabajoResumen["estado"], { texto: string; ruta: string }> = {
  encolado: { texto: "En cola", ruta: "/esperando" },
  procesando: { texto: "Armando tu kit", ruta: "/esperando" },
  espera_revision: { texto: "En revisión", ruta: "/esperando" },
  publicado: { texto: "Kit listo", ruta: "/kits" },
  fallido: { texto: "No pudimos terminarlo", ruta: "/esperando" },
};

// La fecha viene del pedido (dato de servidor, ISO 8601), no del reloj del
// cliente: no hay riesgo de desajuste de zona entre render de servidor y de
// cliente. Misma disciplina que `fechaLegible` en el formulario de casos.
function fechaLegible(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default async function DashboardPage() {
  const sesion = await sesionActual();
  if (!sesion) redirect("/ingresar");

  // Dos lecturas del portador. Cada una es fail-soft: si un servicio esta
  // caido, su seccion queda vacia en vez de tumbar el panel entero, y nunca se
  // inventa lo que no existe. Los pedidos pagados salen de comercio; las
  // solicitudes de kit —lo que /empezar crea— de inteligencia, por el Bearer.
  const token = await tokenDeSesion();
  let pedidos: Pedido[] = [];
  let trabajos: TrabajoResumen[] = [];
  try {
    pedidos = await origenDeDatos().misPedidos(sesion.usuario_id);
  } catch (causa) {
    console.error("dashboard: no se pudieron leer los pedidos", causa);
    pedidos = [];
  }
  try {
    trabajos = await origenDeDatos().misTrabajos(token);
  } catch (causa) {
    console.error("dashboard: no se pudieron leer las solicitudes", causa);
    trabajos = [];
  }

  // Los hijos del hogar, derivados de las solicitudes: cada solicitud trae sus
  // hijos por (referencia, colegio, grado). Se deduplican por esa terna para
  // que dos solicitudes del mismo hijo no lo dupliquen en la tarjeta. El nombre
  // legible del colegio sale de `colegios()`; si no está, se muestra su id.
  const colegios = await origenDeDatos()
    .colegios()
    .catch(() => []);
  const nombreColegio = new Map(colegios.map((c) => [c.colegio_id, c.nombre]));
  const hijos = new Map<string, { colegio: string; grado: string }>();
  for (const t of trabajos) {
    for (const h of t.hijos) {
      hijos.set(`${h.colegio_id}·${h.grado}·${h.referencia}`, {
        colegio: nombreColegio.get(h.colegio_id) ?? h.colegio_id,
        grado: h.grado,
      });
    }
  }
  const perfiles = [...hijos.values()];

  return (
    <div className={styles.shell}>
      <div className={styles.body}>
        <div className={styles.main}>
          <Sidebar />

          {/* ======== Columna de contenido ======== */}
          <div className={styles.content}>
            {/* Encabezado */}
            <div className={styles.pageHeader}>
              <div className={styles.pageHeader__titles}>
                <h1>Hola, {sesion.nombre}</h1>
                <p>Tus hijos y tus kits, en un solo lugar.</p>
              </div>
              <Link href="/empezar" className={styles.btnNuevoPedido}>
                <UserPlus size={16} strokeWidth={2.4} aria-hidden="true" />
                Nuevo pedido
              </Link>
            </div>

            {/* ---- Perfiles de hijos ---- */}
            <section id="hijos" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Perfiles de hijos</h2>
              </div>
              {perfiles.length === 0 ? (
                <p className={styles.sinPedidos}>
                  Todavía no has armado el kit de ningún hijo.{" "}
                  <Link href="/empezar">Empieza aquí</Link>.
                </p>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Hijo</th>
                      <th>Colegio</th>
                      <th>Grado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {perfiles.map((h, i) => (
                      <tr key={`${h.colegio}·${h.grado}·${i}`}>
                        <td className={styles.pedidoId}>
                          <Users size={14} strokeWidth={2.2} aria-hidden="true" /> Hijo {i + 1}
                        </td>
                        <td>{h.colegio}</td>
                        <td>{h.grado}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            {/* ---- Mis solicitudes de kit ---- */}
            <section id="solicitudes" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Mis solicitudes de kit</h2>
              </div>
              {trabajos.length === 0 ? (
                <p className={styles.sinPedidos}>
                  Aún no tienes solicitudes. Cuando armes un kit, aparecerá aquí con su estado.
                </p>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Solicitud</th>
                      <th>Fecha</th>
                      <th>Hijos</th>
                      <th>Progreso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trabajos.map((t) => {
                      const e = ESTADO_SOLICITUD[t.estado];
                      return (
                        <tr key={t.trabajo_id}>
                          <td className={styles.pedidoId}>
                            <Link href={`${e.ruta}/${t.trabajo_id}`}>
                              {t.trabajo_id.slice(0, 8).toUpperCase()}
                            </Link>
                          </td>
                          <td className={styles.pedidoFecha}>{fechaLegible(t.creado_en)}</td>
                          <td>{t.hijos.length}</td>
                          <td>
                            <EtapasSolicitud estado={t.estado} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </section>

            {/* ---- Mis pedidos ---- */}
            <section id="pedidos" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Mis pedidos</h2>
              </div>

              {pedidos.length === 0 ? (
                <p className={styles.sinPedidos}>
                  Todavía no tienes pedidos. Cuando armes tu primer kit, aparecerá aquí.
                </p>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Pedido</th>
                      <th>Fecha</th>
                      <th>Estado</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pedidos.map((pedido) => (
                      <tr key={pedido.pedido_id}>
                        <td className={styles.pedidoId}>
                          {pedido.pedido_id.slice(0, 8).toUpperCase()}
                        </td>
                        <td className={styles.pedidoFecha}>{fechaLegible(pedido.creado_en)}</td>
                        <td>
                          <span className={styles.badgeEntregado}>
                            <span className={styles.badgeDot} />
                            {ETIQUETA_ESTADO_PEDIDO[pedido.estado]}
                          </span>
                        </td>
                        <td className={`${styles.pedidoTotal} cifra`}>
                          {formatearPesos(pedido.total)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            {/* ---- Ayuda ---- */}
            <section className={styles.ayudaCard}>
              <div className={styles.ayudaCard__header}>
                <div className={styles.ayudaCard__icon}>
                  <LifeBuoy size={16} strokeWidth={2} aria-hidden="true" color="white" />
                </div>
                <span className={styles.ayudaCard__title}>¿Necesitas ayuda?</span>
              </div>
              <p>Resolvemos las dudas más comunes sobre cómo armar y recibir tu kit.</p>
              <Link href="/ayuda" className={styles.btnContactar}>
                Ir al centro de ayuda
              </Link>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
