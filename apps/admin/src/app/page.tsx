// `/` — el pulso del back-office (CABLEADO). Es la casa del operador: al
// entrar ve el panel, no la cola. La cola vive ahora en `/cola`.
//
// Todas las cifras salen de datos REALES del origen activo: `cola()` (la misma
// que alimenta la Cola) y `catalogo()`. No se inventa ni un número. Cuando el
// origen es simulado son las semillas del repo; cuando `TUKIT_ORIGEN_DATOS=api`
// son las del backend. La pantalla no cambia.
//
// Server Component, igual que la Cola: lee el origen directo, sin `fetch` de
// por medio.

import Link from "next/link";
import {
  ClipboardList,
  PackageX,
  ShoppingBag,
  TriangleAlert,
} from "lucide-react";
import type { EstadoTrabajo } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import Revelar from "@/components/Revelar";
import styles from "./Panel.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaPanel() {
  // Dos lecturas reales del mismo origen que ya usan Cola y (más adelante) el
  // gestor de huecos. Nada aquí es un mock suelto.
  const [{ entradas }, catalogo] = await Promise.all([
    origenDeDatos().cola(),
    origenDeDatos().catalogo(),
  ]);

  const enEspera = entradas.filter((e) => e.estado === "espera_revision");
  const lineasPendientes = enEspera.reduce((t, e) => t + e.lineas_pendientes, 0);
  const publicados = entradas.filter((e) => e.estado === "publicado").length;

  // Reparto de la cola por estado, para la barra de "en qué anda el pipeline".
  const porEstado = entradas.reduce<Record<EstadoTrabajo, number>>(
    (acc, e) => {
      acc[e.estado] += 1;
      return acc;
    },
    { encolado: 0, procesando: 0, espera_revision: 0, publicado: 0, fallido: 0 },
  );

  const tarjetas = [
    {
      etiqueta: "Esperando revisión",
      valor: enEspera.length,
      pista: "Trabajos que necesitan una persona ahora",
      Icono: ClipboardList,
      tono: enEspera.length > 0 ? "aviso" : "ok",
      href: "/cola",
    },
    {
      etiqueta: "Líneas por resolver",
      valor: lineasPendientes,
      pista: "Renglones pendientes en esos trabajos",
      Icono: TriangleAlert,
      tono: lineasPendientes > 0 ? "aviso" : "ok",
      href: "/cola",
    },
    {
      etiqueta: "Huecos de catálogo",
      valor: catalogo.resumen.conceptos_sin_producto,
      pista: "Conceptos sin ningún producto",
      Icono: PackageX,
      tono: catalogo.resumen.conceptos_sin_producto > 0 ? "aviso" : "ok",
      href: "/catalogo",
    },
    {
      etiqueta: "Kits publicados",
      valor: publicados,
      pista: "Trabajos ya aprobados y en el hogar",
      Icono: ShoppingBag,
      tono: "ok",
      href: "/logistica",
    },
  ] as const;

  const totalCola = entradas.length || 1;
  const barras: { estado: EstadoTrabajo; etiqueta: string }[] = [
    { estado: "espera_revision", etiqueta: "Espera revisión" },
    { estado: "procesando", etiqueta: "Procesando" },
    { estado: "encolado", etiqueta: "En cola" },
    { estado: "publicado", etiqueta: "Publicado" },
    { estado: "fallido", etiqueta: "Fallido" },
  ];

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Panel</h1>
          <p className={styles.bajada}>
            El pulso de la operación con las cifras del origen activo. No hay números
            inventados: todo sale de la cola de revisión y del catálogo.
          </p>
        </div>
      </header>

      <Revelar>
        <section className={styles.tarjetas} aria-label="Métricas de la operación">
          {tarjetas.map(({ etiqueta, valor, pista, Icono, tono, href }) => (
            <Link
              key={etiqueta}
              href={href}
              className={`${styles.tarjeta} ${tono === "aviso" ? styles.tarjetaAviso : ""}`}
            >
              <span className={styles.tarjetaIcono} aria-hidden="true">
                <Icono size={20} strokeWidth={2.2} />
              </span>
              <span className={`${styles.tarjetaValor} cifra`}>{valor}</span>
              <span className={styles.tarjetaEtiqueta}>{etiqueta}</span>
              <span className={styles.tarjetaPista}>{pista}</span>
            </Link>
          ))}
        </section>
      </Revelar>

      <section className={styles.bloque} aria-labelledby="pipeline">
        <h2 id="pipeline" className={styles.bloqueTitulo}>
          En qué anda el pipeline
        </h2>
        <ul className={styles.barras}>
          {barras.map(({ estado, etiqueta }) => {
            const n = porEstado[estado];
            const pct = Math.round((n / totalCola) * 100);
            return (
              <li key={estado} className={styles.barraFila}>
                <span className={styles.barraEtiqueta}>{etiqueta}</span>
                <span className={styles.barraCarril}>
                  <span
                    className={`${styles.barraRelleno} ${styles[`relleno_${estado}`]}`}
                    style={{ width: `${pct}%` }}
                  />
                </span>
                <span className={`${styles.barraValor} cifra`}>{n}</span>
              </li>
            );
          })}
        </ul>
        <p className={styles.notaCatalogo}>
          Catálogo: <strong className="cifra">{catalogo.resumen.conceptos}</strong> conceptos ·{" "}
          <strong className="cifra">{catalogo.resumen.productos}</strong> productos ·{" "}
          <strong className="cifra">{catalogo.resumen.conceptos_con_tres_niveles}</strong> con los
          tres niveles ·{" "}
          <strong className="cifra">{catalogo.resumen.productos_sin_revisar}</strong> sin revisar.
        </p>
      </section>
    </div>
  );
}
