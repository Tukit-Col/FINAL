// Panel de re-clasificación de un producto (P4c): mover el producto bajo otro
// concepto. Es una escritura aparte del PATCH de campos porque tiene un efecto
// distinto —el backend limpia el `texto_embedding` para que se recalcule— y
// conviene que el revisor lo vea como una acción deliberada, no un campo más.
//
// Presentación pura: recibe la lista de conceptos y el concepto actual, avisa
// hacia arriba con el código elegido. La llamada la hace `GestorCatalogo`.

import { useState } from "react";
import Desplegable from "./Desplegable";
import styles from "./CatalogoSpa.module.css";

export interface OpcionConcepto {
  codigo: string;
  nombre: string;
  // El esquema de atributos que el concepto declara. Lo consume el editor para
  // pre-poblar todas las claves (discriminantes + descriptivos), no solo las
  // que el producto ya trae. El selector de re-clasificación no lo usa; por eso
  // son opcionales y no rompen a los consumidores que solo arman `{codigo, nombre}`.
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
