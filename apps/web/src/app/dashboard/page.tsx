// Pantalla de cuenta heredada del prototipo. Sigue corriendo sobre
// `mock-data`, que NO es el contrato: son los perfiles de hijos y los pedidos
// que el SRS ubica en `identidad` y `comercio`, y ninguno de los dos tiene
// todavia superficie de lectura definida. Se conserva la estructura (lista
// para conectar) y se marca en pantalla como datos de muestra para no
// aparentar informacion que el sistema aun no produce.
import Link from "next/link";
import {
  FlaskConical,
  GraduationCap,
  UserPlus,
  LifeBuoy,
} from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { mockUsuario, mockHijos, mockPedidos } from "@/lib/mock-data";
import styles from "./Dashboard.module.css";

export default function DashboardPage() {
  return (
    <div className={styles.shell}>
      <div className={styles.body}>
        <div className={styles.main}>
          <Sidebar />

          {/* ======== Columna de contenido ======== */}
          <div className={styles.content}>
            {/* Aviso honesto: esta pantalla corre sobre mock-data, no sobre el
                contrato. Se dice en pantalla para no aparentar datos que el
                sistema todavia no produce. */}
            <p className={styles.avisoMock}>
              <FlaskConical size={15} aria-hidden="true" strokeWidth={2.2} />
              Vista de diseño: los perfiles de hijos y los pedidos son datos de
              muestra. Se conectarán cuando identidad y comercio publiquen sus servicios.
            </p>

            {/* Encabezado */}
            <div className={styles.pageHeader}>
              <div className={styles.pageHeader__titles}>
                <h1>Hola, {mockUsuario.nombre}</h1>
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
                  {mockPedidos.map((pedido) => (
                    <tr key={pedido.id}>
                      <td className={styles.pedidoId}>{pedido.id}</td>
                      <td className={styles.pedidoFecha}>{pedido.fecha}</td>
                      <td>
                        <span className={styles.badgeEntregado}>
                          <span className={styles.badgeDot} />
                          {pedido.estado}
                        </span>
                      </td>
                      <td className={`${styles.pedidoTotal} cifra`}>{pedido.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
