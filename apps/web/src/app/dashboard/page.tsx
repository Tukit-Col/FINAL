// El panel del acudiente (Server Component).
//
// Decisiones:
// - Lee la sesión de la cookie httpOnly y, sin sesión, redirige a `/ingresar`: falla cerrado como el
//   resto de las rutas protegidas.
// - De los menores se lee solo la tenencia del propio portador (`matriculasDeLaSesion`): colegio,
//   grado, año y el apodo descifrado; nunca nombre legal, documento ni `estudiante_id`.
// - Si la lectura de hijos falla, la sección degrada a un aviso y el resto del panel sigue vivo.

import Link from "next/link";
import { redirect } from "next/navigation";
import { Fragment } from "react";
import {
  Clock,
  LifeBuoy,
  ArrowRight,
  Users,
  ClipboardList,
  Package,
  type LucideIcon,
} from "lucide-react";
import {
  ETIQUETA_ESTADO_PEDIDO,
  GRADOS_CANONICOS,
  formatearPesos,
  type Colegio,
  type EstadoTrabajo,
  type MiCaso,
  type MatriculaAcudiente,
  type Pedido,
  type Solicitud,
} from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import Sidebar from "@/components/Sidebar";
import Revelar from "@/components/Revelar";
import { conAvisoDeLimite } from "@/components/ConAvisoDeLimite";
import { esLimiteDeTasa } from "@/lib/limite";
import {
  sesionActual,
  matriculasDeLaSesion,
  pedidosDeLaSesion,
  solicitudesDeLaSesion,
  tokenDeSesion,
} from "@/lib/sesion";
import {
  compraDeSolicitud,
  pedidoVencido,
  tonoEstadoPedido,
  type TonoEstado,
} from "@/lib/pagar-pedido";
import { saludoDeCuenta } from "@/lib/cuenta";
import AccionesPedido from "./AccionesPedido";
import ActualizarSolo from "./ActualizarSolo";
import DetallePedido from "./DetallePedido";
import SeguimientoPedido from "./SeguimientoPedido";
import MisCasos from "./MisCasos";
import CancelarSolicitud from "./CancelarSolicitud";
import TarjetaHijo from "./TarjetaHijo";
import styles from "./Dashboard.module.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Mi cuenta — Tukit" };

function fechaLegible(iso: string): string {
  return new Date(iso).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const PALABRAS_ESTADO: Record<EstadoTrabajo, string> = {
  encolado: "Estamos armando tu kit",
  procesando: "Estamos armando tu kit",
  espera_revision: "Una persona lo está revisando",
  publicado: "Listo",
  fallido: "Hubo un problema, lo estamos revisando",
  cancelado: "Cancelaste esta solicitud",
};

type TonoChip = TonoEstado | "info" | "neutro";
interface ChipEstado {
  texto: string;
  tono: TonoChip;
}

const CLASE_CHIP: Record<TonoChip, string> = {
  exito: styles.badgeExito,
  aviso: styles.badgeAviso,
  peligro: styles.badgePeligro,
  info: styles.badgeInfo,
  neutro: styles.badgeNeutro,
};

function chipDeSolicitud(
  solicitud: Solicitud,
  compra: { estado: "comprado" | "pendiente_pago" | string } | null,
): ChipEstado {
  if (compra) {
    return compra.estado === "comprado"
      ? { texto: "Comprado", tono: "exito" }
      : { texto: "Pago pendiente", tono: "aviso" };
  }
  if (solicitud.tipo === "recibida")
    return { texto: "En revisión", tono: "aviso" };
  if (solicitud.tipo === "aprobada") return { texto: "Listo", tono: "exito" };
  switch (solicitud.estado) {
    case "publicado":
      return { texto: "Listo", tono: "exito" };
    case "encolado":
    case "procesando":
      return { texto: "Armando", tono: "info" };
    case "cancelado":
      return { texto: "Cancelada", tono: "neutro" };
    default:
      return { texto: "En revisión", tono: "aviso" };
  }
}

const RANGO_CHIP: Record<string, number> = {
  Listo: 4,
  Comprado: 4,
  Armando: 3,
  "Pago pendiente": 2,
  "En revisión": 1,
};

function EstadoVacio(props: {
  Icono: LucideIcon;
  titulo: string;
  texto: string;
  cta?: { href: string; texto: string };
}) {
  return (
    <div className={styles.vacio}>
      <span className={styles.vacioIcono} aria-hidden="true">
        <props.Icono size={44} strokeWidth={1.5} />
      </span>
      <div className={styles.vacioTexto}>
        <p className={styles.vacioTitulo}>{props.titulo}</p>
        <p>{props.texto}</p>
        {props.cta && (
          <Link href={props.cta.href} className={styles.btnPrimario}>
            {props.cta.texto} <ArrowRight size={15} aria-hidden="true" />
          </Link>
        )}
      </div>
    </div>
  );
}

const CLASE_TONO: Record<TonoEstado, string> = {
  exito: styles.badgeExito,
  aviso: styles.badgeAviso,
  peligro: styles.badgePeligro,
};

async function pedidosConVigencia(): Promise<{
  filas: { pedido: Pedido; vencido: boolean }[];
  ahora: number;
}> {
  const ahora = Date.now();
  let pedidos: Pedido[];
  try {
    pedidos = await pedidosDeLaSesion();
  } catch (causa) {
    if (esLimiteDeTasa(causa)) throw causa;
    return { filas: [], ahora };
  }
  return {
    filas: pedidos.map((pedido) => ({
      pedido,
      vencido: pedidoVencido(pedido.creado_en, ahora),
    })),
    ahora,
  };
}

async function casosDeLaSesion(): Promise<MiCaso[] | null> {
  const token = await tokenDeSesion();
  if (!token) return [];
  try {
    return await origenDeDatos().misCasos(token);
  } catch (causa) {
    if (esLimiteDeTasa(causa)) throw causa;
    return null;
  }
}

export default async function DashboardPage() {
  return conAvisoDeLimite(panel);
}

async function panel() {
  const sesion = await sesionActual();
  if (!sesion) redirect("/ingresar");

  const { filas: pedidos, ahora } = await pedidosConVigencia();
  const casos = await casosDeLaSesion();

  let hijos: MatriculaAcudiente[] = [];
  let colegios: Colegio[] = [];
  let errorHijos = false;
  try {
    [hijos, colegios] = await Promise.all([
      matriculasDeLaSesion(),
      origenDeDatos().colegios(),
    ]);
  } catch (causa) {
    if (esLimiteDeTasa(causa)) throw causa;
    errorHijos = true;
  }

  let solicitudes: Solicitud[] = [];
  let listasDisponibles = true;
  let errorSolicitudes = false;
  try {
    const r = await solicitudesDeLaSesion();
    solicitudes = r.solicitudes;
    listasDisponibles = r.listas_disponibles;
  } catch (causa) {
    if (esLimiteDeTasa(causa)) throw causa;
    errorSolicitudes = true;
  }

  const nombrePorColegio = new Map(
    colegios.map((c) => [c.colegio_id, c.nombre]),
  );

  const nombreCuenta = sesion.nombre.trim() || sesion.correo;

  const chipsDeSolicitudes = solicitudes.map((s) => {
    const trabajoId = s.tipo === "recibida" ? null : s.trabajo_id;
    const compra = trabajoId
      ? compraDeSolicitud(
          trabajoId,
          pedidos.map((f) => f.pedido),
          ahora,
        )
      : null;
    return chipDeSolicitud(s, compra);
  });
  const kitsListos = chipsDeSolicitudes.filter(
    (c) => c.tono === "exito",
  ).length;
  const estadoPorHijo = new Map<string, ChipEstado>();
  solicitudes.forEach((s, i) => {
    const chip = chipsDeSolicitudes[i];
    const clave = `${s.colegio_id}|${s.grado}`;
    const previo = estadoPorHijo.get(clave);
    if (
      (RANGO_CHIP[chip.texto] ?? 0) >
      (previo ? (RANGO_CHIP[previo.texto] ?? 0) : 0)
    ) {
      estadoPorHijo.set(clave, chip);
    }
  });

  return (
    <div className={styles.shell}>
      <div className={styles.body}>
        <div className={styles.main}>
          <Sidebar nombreCuenta={nombreCuenta} />

          <Revelar modo="cascada" cadaUno={0.06} className={styles.content}>
            <header className={styles.pageHeader}>
              <div className={styles.pageHeader__titles}>
                <h1>{saludoDeCuenta(sesion.nombre)}</h1>
                <p>Tus hijos y tus kits, en un solo lugar.</p>
              </div>
              <dl className={styles.resumen} aria-label="Resumen de tu cuenta">
                <a href="#hijos" className={styles.resumenItem}>
                  <dd>{errorHijos ? "–" : hijos.length}</dd>
                  <dt>{hijos.length === 1 ? "hijo" : "hijos"}</dt>
                </a>
                <a href="#solicitudes" className={styles.resumenItem}>
                  <dd>{errorSolicitudes ? "–" : kitsListos}</dd>
                  <dt>{kitsListos === 1 ? "kit listo" : "kits listos"}</dt>
                </a>
                <a href="#pedidos" className={styles.resumenItem}>
                  <dd>{pedidos.length}</dd>
                  <dt>{pedidos.length === 1 ? "pedido" : "pedidos"}</dt>
                </a>
              </dl>
            </header>

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
                <EstadoVacio
                  Icono={Users}
                  titulo="Aún no hay hijos en tu cuenta"
                  texto="Cuando armes tu primer kit, su colegio y su grado quedan guardados aquí."
                  cta={{ href: "/empezar", texto: "Armar mi primer kit" }}
                />
              ) : (
                <ul className={styles.hijos}>
                  {hijos.map((hijo, i) => {
                    const titulo = hijo.apodo?.trim() || `Hijo ${i + 1}`;
                    const colegio =
                      nombrePorColegio.get(hijo.colegio_id) ?? hijo.colegio_id;
                    return (
                      <TarjetaHijo
                        key={hijo.matricula_id}
                        matriculaId={hijo.matricula_id}
                        titulo={titulo}
                        colegioId={hijo.colegio_id}
                        colegioNombre={colegio}
                        grado={hijo.grado}
                        colegios={colegios}
                        grados={GRADOS_CANONICOS}
                        estado={
                          estadoPorHijo.get(
                            `${hijo.colegio_id}|${hijo.grado}`,
                          ) ?? null
                        }
                        claseEstado={
                          CLASE_CHIP[
                            estadoPorHijo.get(
                              `${hijo.colegio_id}|${hijo.grado}`,
                            )?.tono ?? "neutro"
                          ]
                        }
                      />
                    );
                  })}
                </ul>
              )}
            </section>

            <section id="solicitudes" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Mis solicitudes</h2>
              </div>

              {errorSolicitudes ? (
                <p className={styles.hijosError}>
                  No pudimos cargar tus solicitudes en este momento. Vuelve a
                  intentarlo en unos minutos.
                </p>
              ) : solicitudes.length === 0 && listasDisponibles ? (
                <EstadoVacio
                  Icono={ClipboardList}
                  titulo="Todavía no has enviado ninguna lista"
                  texto="Cuando subas una, aparecerá aquí mientras la revisamos y armamos tu kit."
                  cta={{ href: "/empezar", texto: "Armar mi primer kit" }}
                />
              ) : (
                <>
                  {!listasDisponibles && (
                    <p className={styles.hijosError}>
                      No pudimos cargar las listas que subiste; vuelve a
                      intentarlo en unos minutos.
                    </p>
                  )}
                  <ul className={styles.solicitudes}>
                    {solicitudes.map((solicitud, i) => {
                      const colegio =
                        nombrePorColegio.get(solicitud.colegio_id) ??
                        solicitud.colegio_nombre ??
                        solicitud.colegio_id;
                      const clave = `${solicitud.tipo}-${solicitud.colegio_id}-${solicitud.grado}-${i}`;
                      const trabajoId =
                        solicitud.tipo === "recibida"
                          ? null
                          : solicitud.trabajo_id;
                      const compra = trabajoId
                        ? compraDeSolicitud(
                            trabajoId,
                            pedidos.map((f) => f.pedido),
                            ahora,
                          )
                        : null;
                      const chip = chipsDeSolicitudes[i];
                      return (
                        <li key={clave} className={styles.solicitudCard}>
                          <div className={styles.solicitudMeta}>
                            <div className={styles.solicitudTitulos}>
                              <span className={styles.solicitudColegio}>
                                {colegio}
                              </span>
                              <span className={styles.solicitudGrado}>
                                Kit de {solicitud.grado}
                              </span>
                            </div>
                            <span
                              className={`${styles.badge} ${CLASE_CHIP[chip.tono]}`}
                            >
                              <span className={styles.badgeDot} />
                              {chip.texto}
                            </span>
                          </div>
                          {compra ? (
                            <>
                              <p className={styles.solicitudEstado}>
                                {compra.estado === "comprado"
                                  ? "Ya compraste este kit. Puedes seguir tu pedido en Mis pedidos."
                                  : "Armaste un pedido con este kit y está esperando tu pago."}
                              </p>
                              <div className={styles.solicitudEnlaces}>
                                <Link
                                  href={`/pedidos/${compra.pedidoId}`}
                                  className={styles.solicitudEnlace}
                                >
                                  {compra.estado === "comprado"
                                    ? "Ver mi pedido"
                                    : "Ir a pagar"}
                                </Link>
                                <Link
                                  href={`/kits/${trabajoId}`}
                                  className={styles.solicitudEnlaceSecundario}
                                >
                                  Ver el kit
                                </Link>
                              </div>
                            </>
                          ) : solicitud.tipo === "recibida" ? (
                            <>
                              <p className={styles.solicitudEstado}>
                                Recibida: una persona está revisando tu lista.
                              </p>
                              {solicitud.tarea_id && (
                                <CancelarSolicitud
                                  tareaId={solicitud.tarea_id}
                                />
                              )}
                            </>
                          ) : solicitud.tipo === "aprobada" ? (
                            <>
                              <p className={styles.solicitudEstado}>
                                Aprobada: tu kit está listo. Te enviamos el
                                enlace a tu correo.
                              </p>
                              <div className={styles.solicitudEnlaces}>
                                <Link
                                  href={`/kits/${solicitud.trabajo_id}`}
                                  className={styles.solicitudEnlace}
                                >
                                  Ver mis kits
                                </Link>
                                <CancelarSolicitud
                                  trabajoId={solicitud.trabajo_id}
                                />
                              </div>
                            </>
                          ) : (
                            <>
                              <p className={styles.solicitudEstado}>
                                {PALABRAS_ESTADO[solicitud.estado]}
                              </p>
                              <div className={styles.solicitudEnlaces}>
                                <Link
                                  href={
                                    solicitud.estado === "publicado"
                                      ? `/kits/${solicitud.trabajo_id}`
                                      : `/esperando/${solicitud.trabajo_id}`
                                  }
                                  className={styles.solicitudEnlace}
                                >
                                  {solicitud.estado === "publicado"
                                    ? "Ver mis kits"
                                    : "Ver el estado"}
                                </Link>
                                {solicitud.estado !== "procesando" && (
                                  <CancelarSolicitud
                                    trabajoId={solicitud.trabajo_id}
                                  />
                                )}
                              </div>
                            </>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </section>

            <section id="pedidos" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Mis pedidos</h2>
              </div>

              {pedidos.length === 0 ? (
                <EstadoVacio
                  Icono={Package}
                  titulo="Aún no tienes pedidos"
                  texto="Cuando compres un kit, aquí sigues cada paso hasta la puerta de tu casa."
                  cta={{ href: "/empezar", texto: "Armar mi primer kit" }}
                />
              ) : (
                <>
                  <ul className={styles.pedidos}>
                    {pedidos.map(({ pedido, vencido }) => {
                      const pendiente = pedido.estado === "pendiente_pago";
                      return (
                        <li
                          key={pedido.pedido_id}
                          id={`pedido-${pedido.pedido_id}`}
                          className={styles.pedidoCard}
                        >
                          <div className={styles.pedidoCabecera}>
                            <div className={styles.pedidoTitulo}>
                              <Link
                                href={`/pedidos/${pedido.pedido_id}`}
                                className={styles.pedidoCodigo}
                              >
                                <span className={styles.paraLectores}>
                                  Ver el pedido{" "}
                                </span>
                                {pedido.pedido_id.slice(0, 8).toUpperCase()}
                              </Link>
                              <span className={styles.pedidoFecha}>
                                {fechaLegible(pedido.creado_en)}
                              </span>
                            </div>
                            <div className={styles.pedidoLado}>
                              {pendiente && vencido ? (
                                <span
                                  className={`${styles.badge} ${styles.badgeAviso}`}
                                >
                                  <Clock size={12} aria-hidden />
                                  Vencido
                                </span>
                              ) : (
                                <span
                                  className={`${styles.badge} ${CLASE_TONO[tonoEstadoPedido(pedido.estado)]}`}
                                >
                                  <span className={styles.badgeDot} />
                                  {ETIQUETA_ESTADO_PEDIDO[pedido.estado]}
                                </span>
                              )}
                              <span className={`${styles.pedidoTotal} cifra`}>
                                {formatearPesos(pedido.total)}
                              </span>
                            </div>
                          </div>

                          {pedido.linea_de_tiempo && !pendiente && (
                            <SeguimientoPedido linea={pedido.linea_de_tiempo} />
                          )}

                          {pendiente ? (
                            <AccionesPedido
                              pedidoId={pedido.pedido_id}
                              trabajoId={pedido.trabajo_id}
                              vencido={vencido}
                            />
                          ) : (
                            <DetallePedido pedido={pedido} />
                          )}

                          <div className={styles.pedidoPie}>
                            <Link href={`/pedidos/${pedido.pedido_id}`}>
                              Ver el pedido completo
                            </Link>
                            <a href="#casos">
                              <LifeBuoy size={14} aria-hidden /> ¿Algo no va
                              bien? Abre un caso
                            </a>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                  <ActualizarSolo
                    activo={pedidos.some(
                      ({ pedido }) =>
                        pedido.estado !== "entregado" &&
                        pedido.estado !== "cancelado",
                    )}
                  />
                </>
              )}
            </section>

            <section id="casos" className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Mis casos</h2>
              </div>
              {casos === null ? (
                <p className={styles.hijosError}>
                  No pudimos cargar tus casos en este momento. Vuelve a
                  intentarlo en unos minutos.
                </p>
              ) : (
                <MisCasos iniciales={casos} />
              )}
            </section>

            <section className={styles.ayudaCard}>
              <div className={styles.ayudaCard__header}>
                <div className={styles.ayudaCard__icon}>
                  <LifeBuoy
                    size={16}
                    strokeWidth={2}
                    aria-hidden="true"
                    color="white"
                  />
                </div>
                <span className={styles.ayudaCard__title}>
                  ¿Necesitas ayuda?
                </span>
              </div>
              <p>
                Resolvemos las dudas más comunes sobre cómo armar y recibir tu
                kit.
              </p>
              <Link href="/ayuda" className={styles.btnContactar}>
                Ir al centro de ayuda
              </Link>
            </section>

            <section className={styles.card}>
              <div className={styles.sectionHeader}>
                <h2>Privacidad y mis datos</h2>
              </div>
              <p className={styles.sinHijos}>
                Mira qué datos tuyos guardamos, descarga una copia o pide que
                los borremos.{" "}
                <Link href="/privacidad">Ir a privacidad y mis datos</Link>
              </p>
            </section>
          </Revelar>
        </div>
      </div>
    </div>
  );
}
