// El panel del acudiente. El saludo, los pedidos y ahora los perfiles de los
// hijos salen del backend real (identidad emite la sesion y sirve
// `/v1/cuenta/matriculas`; comercio sirve `/v1/comercio/mis-pedidos`). La
// superficie de menores ya NO se finge: se lee la tenencia del PROPIO portador
// (`matriculasDeLaSesion`), que expone solo colegio+grado+anio y el `apodo`
// descifrado —nunca nombre legal, documento ni estudiante_id (minimizacion,
// Ley 1581)—, y el `colegio_id` se resuelve a nombre con `colegios()`.
//
// Es un Server Component: lee la sesion de la cookie httponly (`sesionActual`)
// y pide los pedidos por el `usuario_id` del portador. Sin sesion, redirige a
// /ingresar, fail-closed como el resto de las rutas protegidas. Si la lectura
// de hijos falla, la seccion degrada a un aviso y el resto del panel sigue vivo.
import Link from "next/link";
import { redirect } from "next/navigation";
import { UserPlus, LifeBuoy } from "lucide-react";
import {
  ETIQUETA_ESTADO_PEDIDO,
  formatearPesos,
  type Colegio,
  type MatriculaAcudiente,
  type Pedido,
} from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import Sidebar from "@/components/Sidebar";
import { sesionActual, matriculasDeLaSesion } from "@/lib/sesion";
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

  // Los perfiles de los hijos del portador. `matriculasDeLaSesion()` es
  // fail-closed a [] (no distingue "sin hijos" de "lectura fallida"), asi que
  // usamos `colegios()` —que SI lanza— como centinela de salud del backend y,
  // de paso, para resolver el nombre del colegio de cada matricula. Un fallo
  // aqui pinta un aviso y no tumba las demas secciones, igual que pedidos. Gap
  // conocido: si SOLO cae el endpoint de matriculas y catalogo responde,
  // degradamos al mensaje "sin hijos" en vez de romper. Va en su PROPIO
  // try/catch: un fallo de colegios no debe vaciar la tabla de pedidos.
  let hijos: MatriculaAcudiente[] = [];
  let colegios: Colegio[] = [];
  let errorHijos = false;
  try {
    [hijos, colegios] = await Promise.all([
      matriculasDeLaSesion(),
      origenDeDatos().colegios(),
    ]);
  } catch {
    errorHijos = true;
  }

  // colegio_id -> nombre para resolver el colegio de cada hijo sin O(n^2).
  const nombrePorColegio = new Map(colegios.map((c) => [c.colegio_id, c.nombre]));

  // sesion.nombre puede venir vacio; caemos al correo para no mostrar un hueco.
  const nombreCuenta = sesion.nombre.trim() || sesion.correo;

  return (
    <div className={styles.shell}>
      <div className={styles.body}>
        <div className={styles.main}>
          <Sidebar nombreCuenta={nombreCuenta} />

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

            {/* ---- Perfiles de hijos ---- */}
            <section id="hijos" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Perfiles de hijos</h2>
              </div>

              {errorHijos ? (
                <p className={styles.hijosError}>
                  No pudimos cargar los perfiles de tus hijos en este momento.
                  Vuelve a intentarlo en unos minutos.
                </p>
              ) : hijos.length === 0 ? (
                <p className={styles.sinHijos}>
                  Todavía no has registrado a tus hijos.{" "}
                  <Link href="/empezar">Arma tu primer kit</Link> para agregarlos.
                </p>
              ) : (
                <ul className={styles.hijos}>
                  {hijos.map((hijo, i) => {
                    // apodo null, vacio o solo espacios -> "Hijo N" en base 1.
                    const titulo = hijo.apodo?.trim() || `Hijo ${i + 1}`;
                    // Nombre del colegio; el id crudo solo si no se encuentra.
                    const colegio = nombrePorColegio.get(hijo.colegio_id) ?? hijo.colegio_id;
                    return (
                      <li
                        key={`${hijo.colegio_id}-${hijo.grado}-${i}`}
                        className={styles.hijoCard}
                      >
                        <span className={styles.hijoApodo}>{titulo}</span>
                        <span className={styles.hijoMeta}>{colegio}</span>
                        <span className={styles.hijoMeta}>{hijo.grado}</span>
                      </li>
                    );
                  })}
                </ul>
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
