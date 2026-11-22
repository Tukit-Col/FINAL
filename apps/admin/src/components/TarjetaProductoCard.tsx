import { ImageOff } from "lucide-react";
import { ETIQUETA_NIVEL } from "@tukit/contrato";
import type { Nivel } from "@tukit/contrato";
import styles from "./CatalogoSpa.module.css";

interface ProductoVisual {
  sku: string;
  nombre: string;
  nivel: Nivel;
  personaje: string | null;
  imagen_url: string | null;
}

interface Props {
  producto: ProductoVisual;
  activo?: boolean;
  insignia?: string;
  onClick?: () => void;
  children?: React.ReactNode;
}

export default function TarjetaProductoCard({
  producto,
  activo = false,
  insignia,
  onClick,
  children,
}: Props) {
  const Cont = onClick ? "button" : "div";
  return (
    <Cont
      {...(onClick ? { type: "button" as const, onClick, "aria-pressed": activo } : {})}
      className={`${styles.tarjeta} ${activo ? styles.tarjetaActiva : ""}`}
    >
      {producto.imagen_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className={styles.tarjetaFoto} src={producto.imagen_url} alt="" />
      ) : (
        <span className={styles.tarjetaFotoVacia}>
          <ImageOff size={28} aria-hidden="true" />
        </span>
      )}

      <div className={styles.tarjetaPildoras}>
        <span className={`${styles.nivelPildora} ${styles[`nivel_${producto.nivel}`]}`}>
          {ETIQUETA_NIVEL[producto.nivel]}
        </span>
        {producto.personaje && (
          <span className={styles.personajePildora}>{producto.personaje}</span>
        )}
        {insignia && <span className={styles.personajePildora}>{insignia}</span>}
      </div>

      <div className={styles.tarjetaNombre}>{producto.nombre}</div>
      <div className={styles.skuMono}>{producto.sku}</div>

      {children ? <div className={styles.tarjetaPie}>{children}</div> : null}
    </Cont>
  );
}
