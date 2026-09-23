// El panel del acudiente. El saludo y los pedidos ya salen del backend real
// (identidad emite la sesion, comercio sirve `/v1/comercio/mis-pedidos`); solo
// "Mis hijos" sigue sobre datos de muestra, y a proposito: esa superficie toca
// nombres de menores y identidad la mantiene cerrada (Anexo M, Ley 1581). El
// aviso de muestra se recorta a esa unica seccion para no mentir sobre lo que
// ya es real ni fingir lo que todavia no se puede abrir.
//
// Es un Server Component: lee la sesion de la cookie httponly (`sesionActual`)
// y pide los pedidos por el `usuario_id` del portador. Sin sesion, redirige a
// /ingresar, fail-closed como el resto de las rutas protegidas.
import Link from "next/link";
import { redirect } from "next/navigation";
import {
  FlaskConical,
  GraduationCap,
  UserPlus,
  LifeBuoy,
} from "lucide-react";
import {
  ETIQUETA_ESTADO_PEDIDO,
  formatearPesos,
  type Pedido,
} from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import Sidebar from "@/components/Sidebar";
import { sesionActual } from "@/lib/sesion";
import { mockHijos } from "@/lib/mock-data";
import styles from "./Dashboard.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Mi cuenta — Tukit" };

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

  // Los pedidos del portador. Si comercio esta caido, no se tumba el panel
  // entero: se muestran las demas secciones y una fila vacia, igual de honesta
  // que el aviso de muestra.
  let pedidos: Pedido[] = [];
  try {
    pedidos = await origenDeDatos().misPedidos(sesion.usuario_id);
  } catch {
    pedidos = [];
  }

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
                <p>Tus pedidos y los perfiles de tus hijos, en un solo lugar.</p>
              </div>
              <Link href="/empezar" className={styles.btnNuevoPedido}>
                <UserPlus size={16} strokeWidth={2.4} aria-hidden="true" />
                Nuevo pedido
              </Link>
            </div>

            {/* ---- Mis hijos ---- */}
            <section id="hijos" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Mis hijos</h2>
              </div>

              {/* Aviso honesto, acotado a esta seccion: los perfiles de menores
                  son datos de muestra. Identidad mantiene cerrada la superficie
                  de menores (Anexo M, Ley 1581); no se abre solo para pintar
                  una tarjeta. Los pedidos de abajo, en cambio, ya son reales. */}
              <p className={styles.avisoMock}>
                <FlaskConical size={15} aria-hidden="true" strokeWidth={2.2} />
                Datos de muestra: los perfiles de menores están protegidos y aún no
                se publican en esta vista.
              </p>

              <div className={styles.hijosContainer}>
                {mockHijos.map((hijo) => (
                  <div key={hijo.id} className={styles.hijoCard}>
                    <div
                      className={styles.hijoAvatar}
                      style={{ background: hijo.colorInicial }}
                    >
                      {hijo.inicial}
                    </div>

                    <div className={styles.hijoInfo}>
                      <div className={styles.hijoNameRow}>
                        <span className={styles.hijoName}>{hijo.nombre}</span>
                        <span className={styles.gradoBadge}>{hijo.grado}</span>
                      </div>
                      <div className={styles.hijoColegio}>
                        <GraduationCap size={13} strokeWidth={2} aria-hidden="true" />
                        {hijo.colegio}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Accion de muestra: agregar hijo vivira en identidad. */}
              <button type="button" className={styles.agregarHijo} disabled>
                <UserPlus size={18} strokeWidth={2} aria-hidden="true" />
                Agregar otro hijo
              </button>
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
