"use client";

import { useState } from "react";
import { formatearPesos, type Pedido } from "@tukit/contrato";
import { agruparLineas } from "@/lib/pedido-vista";
import styles from "./Pedido.module.css";

export default function ResumenPedido({ pedido, visibles }: { pedido: Pedido; visibles?: number }) {
  const [todos, setTodos] = useState(false);
  const productos = agruparLineas(pedido.lineas);
  const mostrados = todos || visibles === undefined ? productos : productos.slice(0, visibles);
  const ocultos = productos.length - mostrados.length;

  return (
    <section className={styles.tarjeta}>
      <h2 className={styles.subtitulo}>
        Tu pedido{" "}
        <span className={styles.contador}>
          {productos.length} {productos.length === 1 ? "producto" : "productos"}
        </span>
      </h2>
      <ul className={styles.productos}>
        {mostrados.map((p) => (
          <li key={p.clave} className={styles.producto}>
            <span className={styles.productoNombre}>
              {p.nombre}
              <span className={styles.cantidad}>
                {p.cantidad} × <span className="cifra">{formatearPesos(p.precioUnitario)}</span>
              </span>
            </span>
            <span className="cifra">{formatearPesos(p.subtotal)}</span>
          </li>
        ))}
      </ul>
      {ocultos > 0 && (
        <button type="button" className={styles.verTodos} onClick={() => setTodos(true)}>
          {ocultos === 1 ? "Ver el producto restante" : `Ver los ${ocultos} productos restantes`}
        </button>
      )}
      <div className={styles.totalLinea}>
        <span>Total</span>
        <span className="cifra">{formatearPesos(pedido.total)}</span>
      </div>
    </section>
  );
}
