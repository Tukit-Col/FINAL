"use client";

// Los productos del pedido, agrupados, con su precio unitario, subtotal y el
// total. `visibles` corta la lista con un "Ver los N restantes": un kit trae
// decenas de productos y la pantalla del pago no es para leerlos todos.

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
        Tu pedido <span className={styles.contador}>{productos.length} productos</span>
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
          Ver los {ocultos} productos restantes
        </button>
      )}
      <div className={styles.totalLinea}>
        <span>Total</span>
        <span className="cifra">{formatearPesos(pedido.total)}</span>
      </div>
    </section>
  );
}
