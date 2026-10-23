// A donde va el pedido: la copia congelada del envio (ADR 0015), con las
// indicaciones y la localidad cuando el checkout las trajo.

import { MapPin } from "lucide-react";
import type { Envio } from "@tukit/contrato";
import styles from "./Pedido.module.css";

export default function EntregaPedido({ envio }: { envio: Envio }) {
  const lugar = [envio.localidad, envio.ciudad].filter(Boolean).join(", ");
  return (
    <section className={styles.tarjeta}>
      <h2 className={styles.subtitulo}>Entrega</h2>
      <p className={styles.entrega}>
        <MapPin size={18} aria-hidden className={styles.entregaIcono} />
        <span>
          <strong>{envio.destinatario}</strong>
          <br />
          {envio.direccion}
          {envio.indicaciones && (
            <>
              <br />
              <span className={styles.indicaciones}>{envio.indicaciones}</span>
            </>
          )}
          <br />
          {lugar}
        </span>
      </p>
    </section>
  );
}
