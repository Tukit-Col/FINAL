// Pantalla de cuenta heredada del prototipo. Sigue corriendo sobre
// `mock-data`, que NO es el contrato: son los perfiles de hijos, pedidos y
// kits guardados que el SRS ubica en `identidad` y `comercio`, y ninguno de
// los dos tiene todavia superficie de lectura definida. Se conserva tal cual
// para no perder trabajo hecho, y se marcara contra el contrato cuando esos
// servicios publiquen sus endpoints.
import Image from "next/image";
import Sidebar from "@/components/Sidebar";
import {
  mockUsuario,
  mockHijos,
  mockPedidos,
  mockKitsGuardados,
  localidades,
  grados,
} from "@/lib/mock-data";
import styles from "./Dashboard.module.css";

export default function DashboardPage() {
  return (
    <div className={styles.shell}>
      <div className={styles.body}>
        <Sidebar />

        {/* Main layout */}
        <div className={styles.main}>
          {/* ======== Left content column ======== */}
          <div className={styles.content}>
            {/* Page header */}
            <div className={styles.pageHeader}>
              <div className={styles["pageHeader__titles"]}>
                <h1>Hola, {mockUsuario.nombre}</h1>
                <p>Gestiona tus pedidos y los perfiles de tus hijos desde aquí.</p>
              </div>
              <a href="/subir">
                <button className={styles.btnNuevoPedido}>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                    <line x1="7" y1="1" x2="7" y2="13" />
                    <line x1="1" y1="7" x2="13" y2="7" />
                  </svg>
                  Nuevo Pedido
                </button>
              </a>
            </div>

            {/* ---- Mis Hijos ---- */}
            <div className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Mis Hijos</h2>
                <span className={styles["sectionHeader__link"]}>Ver todos</span>
              </div>

              <div className={styles.hijosContainer}>
                {mockHijos.map((hijo) => (
                  <div key={hijo.id} className={styles.hijoCard}>
                    {/* Avatar */}
                    <div
                      className={styles.hijoAvatar}
                      style={{ background: hijo.colorInicial }}
                    >
                      {hijo.inicial}
                    </div>

                    {/* Info */}
                    <div className={styles.hijoInfo}>
                      <div className={styles.hijoNameRow}>
                        <span className={styles.hijoName}>{hijo.nombre}</span>
                        <span className={styles.gradoBadge}>{hijo.grado}</span>
                      </div>
                      <div className={styles.hijoColegio}>
                        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M7 1l6 3v3c0 3.5-2.7 6.8-6 7.5C1.7 13.8-.0 10.5 1 7V4L7 1z" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        {hijo.colegio}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className={styles.hijoActions}>
                      <button className={styles.btnHijo}>Editar</button>
                      <button className={styles.btnHijo}>Ver Kit</button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Agregar otro hijo */}
              <button className={styles.agregarHijo}>
                <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="10" cy="10" r="8" />
                  <line x1="10" y1="6" x2="10" y2="14" strokeLinecap="round" />
                  <line x1="6" y1="10" x2="14" y2="10" strokeLinecap="round" />
                </svg>
                Agregar otro hijo
              </button>
            </div>

            {/* ---- Pedidos Recientes ---- */}
            <div className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Pedidos Recientes</h2>
              </div>

              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>ID Pedido</th>
                    <th>Fecha</th>
                    <th>Estado</th>
                    <th>Total</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {mockPedidos.map((pedido, i) => (
                    <tr key={pedido.id}>
                      <td style={{ fontWeight: 600 }}>{pedido.id}</td>
                      <td style={{ color: "var(--color-text-secondary)" }}>{pedido.fecha}</td>
                      <td>
                        {i === 0 ? (
                          <span className={styles.badgeEntregado}>
                            <span className={styles.badgeDot} />
                            {pedido.estado}
                          </span>
                        ) : (
                          <span className={styles.badgeEntregadoAlt}>
                            {pedido.estado}
                          </span>
                        )}
                      </td>
                      <td style={{ fontWeight: 600 }}>{pedido.total}</td>
                      <td>
                        <a href="#" className={styles.linkVer}>
                          Ver<br />Detalles
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <a href="/pedidos" className={styles.historialLink}>
                Ver historial completo
              </a>
            </div>
          </div>

          {/* ======== Right column ======== */}
          <div className={styles.rightColumn}>
            {/* Buscador de Colegios */}
            <div className={styles.buscadorCard}>
              <h3>Buscador de Colegios</h3>
              <p>
                Encuentra la lista oficial de útiles escolares según la
                localidad y grado.
              </p>

              <label className={styles.buscadorLabel}>Localidad</label>
              <select className={styles.buscadorSelect} defaultValue="Usaquén">
                {localidades.map((loc) => (
                  <option key={loc} value={loc}>{loc}</option>
                ))}
              </select>

              <label className={styles.buscadorLabel}>Grado</label>
              <select className={styles.buscadorSelect} defaultValue="Jardín">
                {grados.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>

              <button className={styles.btnBuscarLista}>Buscar Lista</button>
            </div>

            {/* Kits Guardados */}
            <div className={styles.kitsSection}>
              <h3>Kits Guardados</h3>
              {mockKitsGuardados.map((kit) => (
                <div key={kit.id} className={styles.kitItem}>
                  <div className={styles.kitImgWrapper}>
                    <Image
                      src={kit.imagen}
                      alt={kit.nombre}
                      width={52}
                      height={52}
                      style={{ objectFit: "cover" }}
                    />
                  </div>
                  <div className={styles.kitInfo}>
                    <div className={styles.kitNombre}>{kit.nombre}</div>
                    <div className={styles.kitArticulos}>
                      {kit.articulos} artículos
                    </div>
                    <div className={styles.kitPrecioRow}>
                      <span className={styles.kitPrecio}>{kit.precio}</span>
                      <button
                        className={styles.btnAgregarCarrito}
                        aria-label={`Agregar ${kit.nombre} al carrito`}
                      >
                        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                          <circle cx="5.5" cy="11.5" r="1" fill="white" stroke="none" />
                          <circle cx="10.5" cy="11.5" r="1" fill="white" stroke="none" />
                          <path d="M1 1h2l1.5 7h6L12 4H4" strokeLinejoin="round" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Ayuda card */}
            <div className={styles.ayudaCard}>
              <div className={styles["ayudaCard__header"]}>
                <div className={styles["ayudaCard__icon"]}>
                  <svg viewBox="0 0 15 15" fill="none" stroke="white" strokeWidth="1.6">
                    <circle cx="7.5" cy="7.5" r="6.5" />
                    <path d="M7.5 5.5a2 2 0 00-2 2h2a0 0 0 000 0V9.5" strokeLinecap="round" />
                    <circle cx="7.5" cy="11" r="0.8" fill="white" stroke="none" />
                  </svg>
                </div>
                <span className={styles["ayudaCard__title"]}>¿Necesitas ayuda?</span>
              </div>
              <p>
                Nuestro equipo está disponible para asesorarte con tu lista.
              </p>
              <button className={styles.btnContactar}>Contactar soporte</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
