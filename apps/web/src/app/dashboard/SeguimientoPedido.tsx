import {
  Ban,
  BadgeCheck,
  Check,
  House,
  PackageCheck,
  PackageOpen,
  TriangleAlert,
  Truck,
  type LucideIcon,
} from "lucide-react";
import type { LineaDeTiempoPedido, PasoPedido } from "@tukit/contrato";
import { fechaCortaBogota, fechaHoraBogota, diaBogota } from "@/lib/pedido-vista";
import { seguimientoDePedido, type FaseVista } from "@/lib/fases-pedido";
import styles from "./Seguimiento.module.css";

const ICONO: Record<PasoPedido, LucideIcon> = {
  creado: BadgeCheck,
  pagado: BadgeCheck,
  en_preparacion: PackageOpen,
  despachado: PackageCheck,
  en_reparto: Truck,
  entregado: House,
};

const CLASE: Record<FaseVista["situacion"], string> = {
  hecho: styles.hecha,
  actual: styles.actual,
  futuro: styles.futura,
};

const TEXTO: Record<FaseVista["situacion"], string> = {
  hecho: "completada",
  actual: "en curso",
  futuro: "pendiente",
};

export default function SeguimientoPedido({ linea }: { linea: LineaDeTiempoPedido }) {
  const v = seguimientoDePedido(linea);
  const cancelado = v.desvio?.tipo === "cancelado";
  const incidencia = v.desvio?.tipo === "incidencia";

  return (
    <div className={`${styles.seguimiento} ${cancelado ? styles.cancelado : ""}`}>
      <p className={styles.resumen} role="status">
        {v.desvio ? (
          <>
            {cancelado ? <Ban size={16} aria-hidden /> : <TriangleAlert size={16} aria-hidden />}
            <span className={styles.resumenTexto}>{v.resumen}</span>
          </>
        ) : (
          v.resumen
        )}
      </p>

      <ol className={`${styles.fases} ${incidencia ? styles.conIncidencia : ""}`} aria-label="Fases de tu pedido">
        {v.fases.map((f) => {
          const Icono = ICONO[f.paso];
          return (
            <li
              key={f.paso}
              className={`${styles.fase} ${CLASE[f.situacion]}`}
              aria-current={f.situacion === "actual" ? "step" : undefined}
            >
              <span className={styles.marca} aria-hidden>
                <Icono size={20} strokeWidth={2.2} />
                {f.situacion === "hecho" && (
                  <span className={styles.check}>
                    <Check size={10} strokeWidth={4} />
                  </span>
                )}
              </span>
              <span className={styles.texto}>
                <span className={styles.nombre}>
                  {f.etiqueta}
                  <span className={styles.paraLectores}> ({TEXTO[f.situacion]})</span>
                </span>
                {f.fecha && (
                  <time dateTime={f.fecha} className={styles.fecha}>
                    {fechaCortaBogota(f.fecha)}
                  </time>
                )}
                {f.repartidor && <span className={styles.detalle}>Lo lleva {f.repartidor}</span>}
              </span>
            </li>
          );
        })}
      </ol>

      {v.entregaEstimada && (
        <p className={styles.estimada}>
          <Truck size={14} aria-hidden /> Entrega estimada: <strong>{diaBogota(v.entregaEstimada)}</strong>
        </p>
      )}
      {v.desvio?.fecha && (
        <p className={styles.estimada}>
          Registrado el <time dateTime={v.desvio.fecha}>{fechaHoraBogota(v.desvio.fecha)}</time>
        </p>
      )}
    </div>
  );
}
