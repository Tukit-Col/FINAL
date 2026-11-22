import Form from "next/form";
import Link from "next/link";
import type { EstadoPedido } from "@tukit/contrato";
import { ESTADOS_PEDIDO, ETIQUETA_ESTADO_PEDIDO } from "@tukit/contrato";
import { COLEGIO_NINGUNO, hrefConVista, leerFiltros, VISTA_POR_DEFECTO, type FiltrosLogistica as Filtros } from "@/lib/logistica";
import styles from "./FiltrosLogistica.module.css";

interface Props {
  filtros: Filtros;
  colegios: readonly { id: string; nombre: string }[];
}

export default function FiltrosLogistica({ filtros, colegios }: Props) {
  return (
    <Form action="/logistica" className={styles.filtros} aria-label="Filtrar pedidos">
      {filtros.vista !== VISTA_POR_DEFECTO ? <input type="hidden" name="vista" value={filtros.vista} /> : null}
      <div className={`${styles.campo} ${styles.busqueda}`}>
        <label htmlFor="filtro-q">Código del pedido</label>
        <input
          id="filtro-q"
          name="q"
          type="search"
          defaultValue={filtros.q}
          placeholder="ABCD1234"
          autoComplete="off"
        />
      </div>
      <div className={styles.campo}>
        <label htmlFor="filtro-estado">Estado</label>
        <select id="filtro-estado" name="estado" defaultValue={filtros.estado}>
          <option value="">Todos</option>
          {ESTADOS_PEDIDO.map((estado: EstadoPedido) => (
            <option key={estado} value={estado}>
              {ETIQUETA_ESTADO_PEDIDO[estado]}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.campo}>
        <label htmlFor="filtro-colegio">Colegio</label>
        <select id="filtro-colegio" name="colegio" defaultValue={filtros.colegio}>
          <option value="">Todos</option>
          <option value={COLEGIO_NINGUNO}>Sin colegio</option>
          {colegios.map((colegio) => (
            <option key={colegio.id} value={colegio.id}>
              {colegio.nombre}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.campo}>
        <label htmlFor="filtro-desde">Creado desde</label>
        <input id="filtro-desde" name="desde" type="date" defaultValue={filtros.desde} />
      </div>
      <div className={styles.campo}>
        <label htmlFor="filtro-hasta">Hasta</label>
        <input id="filtro-hasta" name="hasta" type="date" defaultValue={filtros.hasta} />
      </div>
      <div className={styles.botonera}>
        <button type="submit" className={styles.filtrar}>
          Filtrar
        </button>
        <Link href={hrefConVista(leerFiltros({}), filtros.vista)} className={styles.limpiar}>
          Limpiar
        </Link>
      </div>
    </Form>
  );
}
