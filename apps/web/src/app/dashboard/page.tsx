// El panel del acudiente. El saludo y los pedidos salen del backend real
// (identidad emite la sesion, comercio sirve `/v1/comercio/mis-pedidos`). La
// superficie de menores la mantiene cerrada identidad (Anexo M, Ley 1581), asi
// que el panel no la finge: no hay tarjeta de "mis hijos" hasta que exista una
// lectura real de esos perfiles.
//
// Es un Server Component: lee la sesion de la cookie httponly (`sesionActual`)
// y pide los pedidos por el `usuario_id` del portador. Sin sesion, redirige a
// /ingresar, fail-closed como el resto de las rutas protegidas.
import Link from "next/link";
import { redirect } from "next/navigation";
import { UserPlus, LifeBuoy } from "lucide-react";
import {
  ETIQUETA_ESTADO_PEDIDO,
  formatearPesos,
  type Pedido,
} from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import Sidebar from "@/components/Sidebar";
import { sesionActual } from "@/lib/sesion";
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
  // entero: se muestran las demas secciones y una fila vacia, sin inventar
  // pedidos que no existen.
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
                <p>Tus pedidos, en un solo lugar.</p>
              </div>
              <Link href="/empezar" className={styles.btnNuevoPedido}>
                <UserPlus size={16} strokeWidth={2.4} aria-hidden="true" />
                Nuevo pedido
              </Link>
            </div>

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
