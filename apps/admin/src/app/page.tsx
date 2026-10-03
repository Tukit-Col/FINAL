// `/` — el pulso del back-office (CABLEADO). Es la casa del operador: al entrar
// ve el panel entero, no la cola. La cola vive en `/cola`.
//
// TODAS las cifras salen de datos REALES del backend, leídas por el gateway:
// la cola de revisión (`cola`), el catálogo (`catalogo`), los pedidos
// (`pedidos`), los casos (`casos`), los colegios (`colegios` + `metricasColegio`
// en vivo) y la traza congelada por día (`metricasSerie`). No se inventa ni un
// número.
//
// Cada grupo se lee por separado y con su propio try/catch: si un servicio está
// caído, se cae SU sección con un aviso honesto, no el panel entero. Es la misma
// degradación que el resto del sistema (ver `arquitectura/REVISION_ARQUITECTURA.md`).
//
// La traza de calidad por día no se calcula aquí: la congela `make
// instantanea-metricas` en `operacion.metrica_diaria`, una foto por sesión. La
// cobertura punto-en-el-tiempo NO se puede reconstruir hacia atrás (se recalcula
// contra el catálogo de hoy), así que se guarda hacia adelante. Sin instantáneas
// aún, la sección lo dice y apunta al comando.

import Link from "next/link";
import {
  ClipboardList,
  Gauge,
  PackageX,
  School,
  ShoppingBag,
  Truck,
  TriangleAlert,
  Wallet,
} from "lucide-react";
import {
  fraccionDeBps,
  formatearPesos,
  pedidoEnCurso,
  seriePorMetrica,
  type Colegio,
  type EstadoTrabajo,
  type MetricasColegio,
  type PuntoMetrica,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import Revelar from "@/components/Revelar";
import { tokenDeSesion } from "@/lib/sesion";
import styles from "./Panel.module.css";

export const dynamic = "force-dynamic";

// Una cobertura se lee de un vistazo por su color: verde si el algoritmo ya
// resuelve casi todo, ámbar a medias, rojo cuando hay mucho hueco. El mismo
// umbral que la Cola usa para "esto necesita curación".
function tonoCobertura(fraccion: number): "ok" | "medio" | "bajo" {
  if (fraccion >= 0.9) return "ok";
  if (fraccion >= 0.6) return "medio";
  return "bajo";
}

function pct(fraccion: number): string {
  return `${Math.round(fraccion * 100)}%`;
}

function fechaCorta(iso: string): string {
  // La fecha viene del snapshot (dato de servidor, ISO), no del reloj del
  // cliente: sin riesgo de desajuste de zona entre render de servidor y cliente.
  return new Date(`${iso}T00:00:00`).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "short",
  });
}

export default async function PaginaPanel() {
  const api = origenDeDatos();
  // Los pedidos son solo de operador/admin: comercio exige la sesion. Sin
  // cookie ni se pregunta; un 401/403 se pinta como "sin permiso", no como
  // servicio caido, porque el arreglo es otro (entrar, o pedir el rol).
  const token = await tokenDeSesion();

  // Un solo golpe de lecturas independientes. `allSettled` para que una caída no
  // tumbe a las demás: cada sección decide qué pintar con lo que llegó.
  const [colaR, catalogoR, pedidosR, casosR, colegiosR, serieR] = await Promise.allSettled([
    api.cola(),
    api.catalogo(),
    token ? api.pedidos(token) : Promise.reject(new ErrorTukit(401, "sesion_invalida", "Sin sesion.")),
    api.casos(),
    api.colegios(),
    api.metricasSerie({ dimension: "global" }),
  ]);

  const cola = colaR.status === "fulfilled" ? colaR.value : null;
  const catalogo = catalogoR.status === "fulfilled" ? catalogoR.value : null;
  const pedidos = pedidosR.status === "fulfilled" ? pedidosR.value : null;
  const pedidosSinPermiso =
    pedidosR.status === "rejected" &&
    pedidosR.reason instanceof ErrorTukit &&
    (pedidosR.reason.estado === 401 || pedidosR.reason.estado === 403);
  const casos = casosR.status === "fulfilled" ? casosR.value : null;
  const colegios = colegiosR.status === "fulfilled" ? colegiosR.value : null;
  const serie = serieR.status === "fulfilled" ? serieR.value : null;

  // --- Cola de revisión ---
  const entradas = cola?.entradas ?? [];
  const enEspera = entradas.filter((e) => e.estado === "espera_revision");
  const lineasPendientes = enEspera.reduce((t, e) => t + e.lineas_pendientes, 0);
  const publicados = entradas.filter((e) => e.estado === "publicado").length;
  const porEstado = entradas.reduce<Record<EstadoTrabajo, number>>(
    (acc, e) => {
      acc[e.estado] += 1;
      return acc;
    },
    { encolado: 0, procesando: 0, espera_revision: 0, publicado: 0, fallido: 0 },
  );
  const totalCola = entradas.length || 1;
  const barras: { estado: EstadoTrabajo; etiqueta: string }[] = [
    { estado: "espera_revision", etiqueta: "Espera revisión" },
    { estado: "procesando", etiqueta: "Procesando" },
    { estado: "encolado", etiqueta: "En cola" },
    { estado: "publicado", etiqueta: "Publicado" },
    { estado: "fallido", etiqueta: "Fallido" },
  ];

  // --- Colegios aliados + cobertura EN VIVO ---
  // Solo los aliados (con al menos un grado verificado): un colegio sin grados
  // no tiene kits ni cobertura que mostrar. La medida es de Inteligencia y se
  // recalcula al vuelo; se pide en paralelo y cada una degrada a null por su
  // cuenta, así una caída no borra la fila del resto.
  const aliados = (colegios ?? []).filter((c: Colegio) => (c.grados?.length ?? 0) > 0);
  const metricasAliados = await Promise.allSettled(
    aliados.map((c) => api.metricasColegio(c.colegio_id)),
  );
  const filasColegio = aliados
    .map((c, i) => {
      const r = metricasAliados[i];
      const m: MetricasColegio | null = r.status === "fulfilled" ? r.value : null;
      return { colegio: c, metricas: m };
    })
    .sort((a, b) => (b.metricas?.kits_armados ?? 0) - (a.metricas?.kits_armados ?? 0));

  // --- Traza de calidad por día (congelada) ---
  const seriePorNombre = serie ? seriePorMetrica(serie) : new Map<string, PuntoMetrica[]>();
  const trazaCobertura = (seriePorNombre.get("cobertura_bps") ?? []).slice(-14);

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Panel</h1>
          <p className={styles.bajada}>
            El pulso de la operación con las cifras del backend real: cola, catálogo,
            pedidos, casos y colegios. Todo sale de los servicios, no de un mock.
          </p>
        </div>
      </header>

      {/* ============ Cola de revisión ============ */}
      <h2 className={styles.grupoTitulo}>Cola de revisión</h2>
      {cola ? (
        <>
          <Revelar>
            <section className={styles.tarjetas} aria-label="Métricas de la cola">
              <Tarjeta
                etiqueta="Esperando revisión"
                valor={enEspera.length}
                pista="Trabajos que necesitan una persona ahora"
                Icono={ClipboardList}
                aviso={enEspera.length > 0}
                href="/cola"
              />
              <Tarjeta
                etiqueta="Líneas por resolver"
                valor={lineasPendientes}
                pista="Renglones pendientes en esos trabajos"
                Icono={TriangleAlert}
                aviso={lineasPendientes > 0}
                href="/cola"
              />
              <Tarjeta
                etiqueta="Kits publicados"
                valor={publicados}
                pista="Trabajos ya aprobados y en el hogar"
                Icono={ShoppingBag}
                href="/logistica"
              />
              <Tarjeta
                etiqueta="Huecos de catálogo"
                valor={catalogo?.resumen.conceptos_sin_producto ?? "—"}
                pista="Conceptos sin ningún producto"
                Icono={PackageX}
                aviso={(catalogo?.resumen.conceptos_sin_producto ?? 0) > 0}
                href="/catalogo"
              />
            </section>
          </Revelar>

          <section className={styles.bloque} aria-labelledby="pipeline">
            <h3 id="pipeline" className={styles.bloqueTitulo}>
              En qué anda el pipeline
            </h3>
            <ul className={styles.barras}>
              {barras.map(({ estado, etiqueta }) => {
                const n = porEstado[estado];
                const ancho = Math.round((n / totalCola) * 100);
                return (
                  <li key={estado} className={styles.barraFila}>
                    <span className={styles.barraEtiqueta}>{etiqueta}</span>
                    <span className={styles.barraCarril}>
                      <span
                        className={`${styles.barraRelleno} ${styles[`relleno_${estado}`]}`}
                        style={{ width: `${ancho}%` }}
                      />
                    </span>
                    <span className={`${styles.barraValor} cifra`}>{n}</span>
                  </li>
                );
              })}
            </ul>
          </section>
        </>
      ) : (
        <SeccionCaida que="la cola de revisión (inteligencia)" />
      )}

      {/* ============ Catálogo y calidad del algoritmo ============ */}
      <h2 className={styles.grupoTitulo}>Catálogo y calidad del algoritmo</h2>
      {catalogo ? (
        <section className={styles.bloque}>
          <p className={styles.notaCatalogo}>
            <strong className="cifra">{catalogo.resumen.conceptos}</strong> conceptos ·{" "}
            <strong className="cifra">{catalogo.resumen.productos}</strong> productos ·{" "}
            <strong className="cifra">{catalogo.resumen.conceptos_con_tres_niveles}</strong> con los
            tres niveles ·{" "}
            <strong className="cifra">{catalogo.resumen.productos_con_foto}</strong> con foto ·{" "}
            <strong className="cifra">{catalogo.resumen.tiendas}</strong> tiendas ·{" "}
            <strong className="cifra">{catalogo.resumen.productos_sin_revisar}</strong> sin revisar.
          </p>
        </section>
      ) : (
        <SeccionCaida que="el catálogo" />
      )}

      {/* ============ Pedidos (comercio) ============ */}
      <h2 className={styles.grupoTitulo}>Pedidos</h2>
      {pedidos ? (
        <Revelar>
          <section className={styles.tarjetas} aria-label="Métricas de pedidos">
            <Tarjeta
              etiqueta="Pedidos totales"
              valor={pedidos.resumen.pedidos_totales}
              pista="Todos los pedidos, en cualquier estado"
              Icono={ShoppingBag}
              href="/logistica"
            />
            <Tarjeta
              etiqueta="En curso"
              valor={pedidos.pedidos.filter(pedidoEnCurso).length}
              pista="Pagados y todavía sin entregar"
              Icono={Truck}
              href="/logistica"
            />
            <Tarjeta
              etiqueta="Entregas pendientes"
              valor={pedidos.resumen.entregas_pendientes}
              pista="Envíos que aún no llegan"
              Icono={Truck}
              aviso={pedidos.resumen.entregas_pendientes > 0}
              href="/logistica"
            />
            <Tarjeta
              etiqueta="Ingresos confirmados"
              valor={formatearPesos(pedidos.resumen.ingresos_confirmados)}
              pista="Pagos aprobados (Wompi)"
              Icono={Wallet}
              href="/logistica"
            />
          </section>
        </Revelar>
      ) : pedidosSinPermiso ? (
        <SeccionSinPermiso que="los pedidos" />
      ) : (
        <SeccionCaida que="los pedidos (comercio)" />
      )}

      {/* ============ Casos / PQRS (operacion) ============ */}
      <h2 className={styles.grupoTitulo}>Casos y PQRS</h2>
      {casos ? (
        <Revelar>
          <section className={styles.tarjetas} aria-label="Métricas de casos">
            <Tarjeta
              etiqueta="Casos abiertos"
              valor={casos.resumen.abiertos}
              pista="Sin resolver todavía"
              Icono={ClipboardList}
              aviso={casos.resumen.abiertos > 0}
              href="/tickets"
            />
            <Tarjeta
              etiqueta="Urgentes"
              valor={casos.resumen.urgentes}
              pista="Prioridad máxima, atender primero"
              Icono={TriangleAlert}
              aviso={casos.resumen.urgentes > 0}
              href="/tickets"
            />
            <Tarjeta
              etiqueta="Vencen hoy"
              valor={casos.resumen.vencen_hoy}
              pista="Término legal que se cumple hoy (Ley 1755)"
              Icono={TriangleAlert}
              aviso={casos.resumen.vencen_hoy > 0}
              href="/tickets"
            />
            <Tarjeta
              etiqueta="Resueltos (7 días)"
              valor={casos.resumen.resueltos_semana}
              pista="Cerrados en la última semana"
              Icono={ClipboardList}
              href="/tickets"
            />
          </section>
        </Revelar>
      ) : (
        <SeccionCaida que="los casos (operación)" />
      )}

      {/* ============ Colegios + cobertura en vivo ============ */}
      <h2 className={styles.grupoTitulo}>Colegios aliados</h2>
      {colegios ? (
        filasColegio.length === 0 ? (
          <p className={styles.vacio}>
            Aún no hay colegios con grados verificados. Revisa una lista en la{" "}
            <Link href="/cola">cola</Link> para que su colegio aparezca aquí.
          </p>
        ) : (
          <section className={styles.bloque}>
            <h3 className={styles.bloqueTitulo}>
              Cobertura del algoritmo por colegio, ahora mismo
            </h3>
            <ul className={styles.colegios}>
              {filasColegio.map(({ colegio, metricas }) => {
                const cobertura = metricas?.cobertura ?? 0;
                const tono = tonoCobertura(cobertura);
                const sinKits = (metricas?.kits_armados ?? 0) === 0;
                return (
                  <li key={colegio.colegio_id} className={styles.colegioFila}>
                    <span className={styles.colegioIcono} aria-hidden="true">
                      <School size={16} strokeWidth={2.2} />
                    </span>
                    <Link href={`/colegios/${colegio.colegio_id}`} className={styles.colegioNombre}>
                      {colegio.nombre}
                    </Link>
                    <span className={styles.colegioKits}>
                      {sinKits ? "Sin kits aún" : `${metricas!.kits_armados} kits`}
                    </span>
                    {!sinKits && (
                      <span className={`${styles.cobertura} ${styles[`cobertura_${tono}`]}`}>
                        <Gauge size={13} strokeWidth={2.4} aria-hidden="true" />
                        {pct(cobertura)}
                      </span>
                    )}
                    {!sinKits && metricas!.ahorro_total_cop > 0 && (
                      <span className={`${styles.colegioAhorro} cifra`}>
                        {formatearPesos(metricas!.ahorro_total_cop)} ahorrados
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )
      ) : (
        <SeccionCaida que="los colegios (identidad)" />
      )}

      {/* ============ Traza de calidad por día ============ */}
      <h2 className={styles.grupoTitulo}>Cómo mejora, día a día</h2>
      <section className={styles.bloque}>
        <h3 className={styles.bloqueTitulo}>Cobertura global congelada por sesión</h3>
        {trazaCobertura.length === 0 ? (
          <p className={styles.vacio}>
            Aún no hay instantáneas. Al terminar una sesión de curación corre{" "}
            <code className={styles.codigo}>make instantanea-metricas</code> para congelar la
            cobertura de hoy: la cobertura punto-en-el-tiempo no se puede reconstruir hacia atrás,
            así que se guarda hacia adelante.
          </p>
        ) : (
          <div className={styles.traza} role="img" aria-label="Cobertura global por día">
            {trazaCobertura.map((p) => {
              const fraccion = fraccionDeBps(p.valor);
              return (
                <div key={p.fecha} className={styles.trazaColumna}>
                  <span className={`${styles.trazaValor} cifra`}>{pct(fraccion)}</span>
                  <span className={styles.trazaCarril}>
                    <span
                      className={`${styles.trazaBarra} ${styles[`trazaBarra_${tonoCobertura(fraccion)}`]}`}
                      style={{ height: `${Math.max(4, Math.round(fraccion * 100))}%` }}
                    />
                  </span>
                  <span className={styles.trazaFecha}>{fechaCorta(p.fecha)}</span>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

// Una tarjeta de métrica: un número real con su ícono y pista. `aviso` cambia el
// marco (anillo ámbar), no el número. Es el mismo patrón que ya tenía el panel,
// extraído a un componente porque ahora hay cuatro grupos que lo reusan.
function Tarjeta({
  etiqueta,
  valor,
  pista,
  Icono,
  aviso = false,
  href,
}: {
  etiqueta: string;
  valor: number | string;
  pista: string;
  Icono: typeof ClipboardList;
  aviso?: boolean;
  href: string;
}) {
  return (
    <Link href={href} className={`${styles.tarjeta} ${aviso ? styles.tarjetaAviso : ""}`}>
      <span className={styles.tarjetaIcono} aria-hidden="true">
        <Icono size={20} strokeWidth={2.2} />
      </span>
      <span className={`${styles.tarjetaValor} cifra`}>{valor}</span>
      <span className={styles.tarjetaEtiqueta}>{etiqueta}</span>
      <span className={styles.tarjetaPista}>{pista}</span>
    </Link>
  );
}

// Aviso honesto cuando un servicio no responde: se cae SU sección, no el panel.
function SeccionCaida({ que }: { que: string }) {
  return (
    <p className={styles.caida} role="status">
      <TriangleAlert size={15} strokeWidth={2.2} aria-hidden="true" />
      No pudimos leer {que}. Revisa que el servicio esté arriba (<code className={styles.codigo}>make estado</code>).
    </p>
  );
}

// No es una caida: el servicio respondio, pero esta sesion no puede ver esto
// (sin sesion, vencida, o sin rol de operador/admin).
function SeccionSinPermiso({ que }: { que: string }) {
  return (
    <p className={styles.caida} role="status">
      <TriangleAlert size={15} strokeWidth={2.2} aria-hidden="true" />
      Tu sesión no puede ver {que}: hace falta ingresar con una cuenta de operador o admin.
    </p>
  );
}
