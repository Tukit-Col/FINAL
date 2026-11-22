import { PRIORIDADES, type ClavePrioridad } from "@/lib/formulario-empezar";
import type { PropsSeccion } from "./SeccionRegistro";
import styles from "./Empezar.module.css";

export default function SeccionPreferencias({
  propsSeccion,
  idBase,
  numeroPaso,
  prioridad,
  onPrioridad,
  marcasExcluidas,
  soloDisponibles,
  onQuitarFiltros,
  presupuesto,
  onPresupuesto,
  conTope,
}: {
  propsSeccion: PropsSeccion;
  idBase: string;
  numeroPaso: number;
  prioridad: ClavePrioridad;
  onPrioridad: (clave: ClavePrioridad) => void;
  marcasExcluidas: string[];
  soloDisponibles: boolean;
  onQuitarFiltros: () => void;
  presupuesto: string;
  onPresupuesto: (valor: string) => void;
  conTope: boolean;
}) {
  const hayFiltros = marcasExcluidas.length > 0 || soloDisponibles;
  return (
    <section {...propsSeccion} aria-labelledby={`${idBase}-preferencias`}>
      <h2 id={`${idBase}-preferencias`} className={styles.tituloBloque}>
        <span className={styles.paso}>{numeroPaso}</span> Cuál kit te marcamos
      </h2>
      <p className={styles.explicacion}>
        Todos los kits llevan la misma lista; lo que cambia es la marca de cada
        producto y, con ella, cuánto gastas. Siempre verás el Ahorrador y el
        Premium, y te marcamos el que va con lo que elijas aquí. No preguntamos por
        el estrato ni por nada del hogar.
      </p>

      <fieldset className={styles.opciones}>
        <legend className={styles.leyendaSimple}>Cuánto quieres gastar</legend>
        {PRIORIDADES.map((opcion) => (
          <label
            key={opcion.clave}
            className={`${styles.tarjetaPrioridad} ${
              prioridad === opcion.clave ? styles.opcionActiva : ""
            }`}
          >
            <input
              type="radio"
              name="prioridad"
              value={opcion.clave}
              checked={prioridad === opcion.clave}
              onChange={() => onPrioridad(opcion.clave)}
            />
            <span className={styles.prioridadTexto}>
              <strong>{opcion.titulo}</strong>
              <span className={styles.prioridadDetalle}>{opcion.detalle}</span>
            </span>
          </label>
        ))}
      </fieldset>

      {hayFiltros && (
        <p className={styles.explicacion}>
          Tu kit va {marcasExcluidas.length > 0 ? `sin ${marcasExcluidas.join(", ")}` : ""}
          {marcasExcluidas.length > 0 && soloDisponibles ? " y " : ""}
          {soloDisponibles ? "solo con productos que hay hoy" : ""}.{" "}
          <button type="button" className={styles.quitar} onClick={onQuitarFiltros}>
            Quitar
          </button>
        </p>
      )}

      {prioridad === "equilibrio" && (
        <div className={styles.panelTope}>
          <label className={styles.campo}>
            <span>
              Tope para tu kit «A tu Medida» <em>(opcional)</em>
            </span>
            <input
              type="text"
              inputMode="numeric"
              value={presupuesto ? `$ ${Number(presupuesto).toLocaleString("es-CO")}` : ""}
              onChange={(e) => onPresupuesto(e.target.value.replace(/\D/g, "").slice(0, 9))}
              placeholder="Ej.: 350.000"
              aria-describedby={`${idBase}-ayuda-presupuesto`}
            />
          </label>
          <p id={`${idBase}-ayuda-presupuesto`} className={styles.ayudaTope}>
            {conTope
              ? "Te armamos la mejor marca que no pase de este tope. Si ni el kit más barato cabe, te lo decimos con su precio."
              : "Sin tope, «A tu Medida» sube de marca donde vale la pena, sin pasar de la mitad de camino entre el precio del Ahorrador y el del Premium."}
          </p>
        </div>
      )}
    </section>
  );
}
