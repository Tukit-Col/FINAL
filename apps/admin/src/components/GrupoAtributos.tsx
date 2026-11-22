import type { ParAtributo } from "@/lib/atributos-editor";
import styles from "./CatalogoSpa.module.css";

export default function GrupoAtributos({
  titulo,
  nota,
  filas,
  onEditar,
}: {
  titulo: string;
  nota: string;
  filas: ParAtributo[];
  onEditar: (indice: number, valor: string) => void;
}) {
  if (filas.length === 0) return null;
  return (
    <div className={styles.atributos}>
      <span className={styles.ayuda}>
        <strong>{titulo}</strong> — {nota}
      </span>
      {filas.map((par, i) => (
        <div key={par.clave} className={styles.atributoFila}>
          <input aria-label="Clave" value={par.clave} readOnly disabled />
          <input
            aria-label={`Valor de ${par.clave}`}
            placeholder="(sin valor)"
            value={par.valor}
            onChange={(e) => onEditar(i, e.target.value)}
          />
        </div>
      ))}
    </div>
  );
}
