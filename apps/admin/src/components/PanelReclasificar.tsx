import { useState } from "react";
import Desplegable from "./Desplegable";
import styles from "./CatalogoSpa.module.css";

export interface OpcionConcepto {
  codigo: string;
  nombre: string;
  atributos_discriminantes?: string[];
  atributos_descriptivos?: string[];
}

interface Props {
  conceptos: OpcionConcepto[];
  conceptoActual: string;
  enProgreso: boolean;
  onReclasificar: (concepto: string) => void;
}

export default function PanelReclasificar({
  conceptos,
  conceptoActual,
  enProgreso,
  onReclasificar,
}: Props) {
  const [destino, setDestino] = useState("");

  return (
    <section className={styles.reclasificar}>
      <h3>Re-clasificar</h3>
      <p className={styles.nota}>
        Mueve el producto a otro concepto. Al guardarlo se recalculará el embedding, así que
        empezará a aparecer en las búsquedas del nuevo concepto.
      </p>
      <div className={styles.reclasificarFila}>
        <div className={styles.campo} style={{ flex: 1 }}>
          <label htmlFor="reclasificar-concepto">Concepto destino</label>
          <Desplegable
            id="reclasificar-concepto"
            tamano="compacto"
            buscable
            textoVacio="— elegir concepto —"
            opciones={conceptos.map((c) => ({
              valor: c.codigo,
              texto: c.codigo === conceptoActual ? `${c.nombre} (actual)` : c.nombre,
              deshabilitada: c.codigo === conceptoActual,
            }))}
            valor={destino}
            onCambio={setDestino}
          />
        </div>
        <button
          type="button"
          className={styles.secundario}
          disabled={!destino || destino === conceptoActual || enProgreso}
          onClick={() => onReclasificar(destino)}
        >
          {enProgreso ? "Moviendo…" : "Re-clasificar"}
        </button>
      </div>
    </section>
  );
}
