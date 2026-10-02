"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CreditCard,
  Home,
  Landmark,
  Loader2,
  MapPin,
  Package,
  PackageCheck,
  Smartphone,
  Truck,
} from "lucide-react";
import {
  formatearPesos,
  type Pedido,
  type ResultadoPago as Resultado,
} from "@tukit/contrato";
import { FalloApi, sincronizarPago, verPedido } from "@/lib/api-navegador";
import styles from "../Pago.module.css";

const INTERVALO_MS = 3000;
const MAX_INTENTOS = 20;
const ESTADOS_REINTENTABLES = [502, 503, 504];
// Cuantos productos se ven antes de "Ver todos": un kit trae decenas.
const PRODUCTOS_VISIBLES = 5;

type Vista =
  | { tipo: "cargando" }
  | { tipo: "resultado"; datos: Resultado }
  | { tipo: "reintento" }
  | { tipo: "agotado" }
  | { tipo: "error"; mensaje: string };

export default function ResultadoPago({ id }: { id: string | undefined }) {
  const [vista, setVista] = useState<Vista>({ tipo: "cargando" });
  const [pedido, setPedido] = useState<Pedido | null>(null);

  useEffect(() => {
    if (!id) return;
    let vivo = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function consultar(intento: number) {
      let siguiente: Vista;
      let reintentar = false;
      try {
        const datos = await sincronizarPago(id as string);
        siguiente = { tipo: "resultado", datos };
        reintentar = datos.estado_pago === "iniciado";
      } catch (causa) {
        if (causa instanceof FalloApi && ESTADOS_REINTENTABLES.includes(causa.estado)) {
          siguiente = { tipo: "reintento" };
          reintentar = true;
        } else {
          siguiente = {
            tipo: "error",
            mensaje:
              causa instanceof FalloApi ? causa.message : "No pudimos confirmar tu pago.",
          };
        }
      }
      if (!vivo) return;
      if (reintentar && intento >= MAX_INTENTOS) {
        setVista({ tipo: "agotado" });
        return;
      }
      setVista(siguiente);
      if (reintentar) timer = setTimeout(() => void consultar(intento + 1), INTERVALO_MS);
    }

    void consultar(1);
    return () => {
      vivo = false;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  // El detalle (productos, medio, entrega) se pide una vez que el pago tiene
  // desenlace. Es un adorno: si falla, la pantalla se muestra sin el.
  const pedidoId =
    vista.tipo === "resultado" && vista.datos.estado_pago !== "iniciado"
      ? vista.datos.pedido_id
      : null;
  useEffect(() => {
    if (!pedidoId) return;
    let vivo = true;
    verPedido(pedidoId)
      .then((p) => vivo && setPedido(p))
      .catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, [pedidoId]);

  let contenido: React.ReactNode;
  if (!id) {
    contenido = (
      <Aviso
        titulo="No encontramos el pago que intentas ver"
        texto="El enlace no trae el identificador de la transacción."
      />
    );
  } else if (vista.tipo === "cargando") {
    contenido = <Confirmando transaccion={id} />;
  } else if (vista.tipo === "reintento") {
    contenido = <Confirmando transaccion={id} texto="No pudimos confirmar todavía. Lo seguimos intentando." />;
  } else if (vista.tipo === "agotado") {
    contenido = (
      <Aviso
        titulo="Aún no tenemos la confirmación"
        texto="Vuelve a abrir esta página en unos minutos o revisa tu panel."
      />
    );
  } else if (vista.tipo === "error") {
    contenido = <Aviso titulo="No pudimos confirmar tu pago" texto={vista.mensaje} />;
  } else {
    const { datos } = vista;
    switch (datos.estado_pago) {
      case "aprobado":
        contenido = <Aprobado datos={datos} pedido={pedido} />;
        break;
      case "rechazado":
        contenido = <Rechazado datos={datos} pedido={pedido} />;
        break;
      case "reembolsado":
        contenido = <Aviso titulo="Este pago fue reembolsado" texto="El dinero volvió a tu medio de pago." />;
        break;
      case "iniciado":
        contenido = <Confirmando transaccion={id} />;
        break;
    }
  }

  return (
    <div className={styles.pagina}>
      <div role="status" aria-live="polite" className={styles.contenedor}>
        {contenido}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Aprobado

function Aprobado({ datos, pedido }: { datos: Resultado; pedido: Pedido | null }) {
  return (
    <>
      <section className={`${styles.tarjeta} ${styles.cabecera}`}>
        <span className={`${styles.icono} ${styles.iconoExito}`} aria-hidden>
          <CheckCircle2 size={44} strokeWidth={2.2} />
        </span>
        <h1 className={styles.titulo}>¡Pago aprobado!</h1>
        <p className={styles.texto}>
          Recibimos tu pago y ya empezamos a preparar tu kit.
        </p>
        <Franja datos={datos} pedido={pedido} />
      </section>

      <Pasos />

      {pedido && <Resumen pedido={pedido} />}
      {pedido?.envio && <Entrega pedido={pedido} />}

      <div className={styles.acciones}>
        <Link href="/dashboard" className={styles.boton}>
          <Package size={18} aria-hidden /> Ver mis pedidos
        </Link>
        <Link href="/" className={`${styles.boton} ${styles.secundario}`}>
          <Home size={18} aria-hidden /> Volver al inicio
        </Link>
      </div>
      <p className={styles.nota}>Wompi te envió el comprobante del pago a tu correo.</p>
    </>
  );
}

// Los pasos que siguen al pago, con "Pagado" ya cumplido.
function Pasos() {
  const pasos = [
    { nombre: "Pagado", Icono: Check },
    { nombre: "En preparación", Icono: Package },
    { nombre: "Despachado", Icono: Truck },
    { nombre: "Entregado", Icono: PackageCheck },
  ];
  return (
    <section className={styles.tarjeta} aria-label="Lo que sigue">
      <h2 className={styles.subtitulo}>Lo que sigue</h2>
      <ol className={styles.pasos}>
        {pasos.map(({ nombre, Icono }, i) => (
          <li key={nombre} className={i === 0 ? styles.pasoHecho : styles.paso}>
            <span className={styles.pasoIcono} aria-hidden>
              <Icono size={18} />
            </span>
            <span>{nombre}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ---------------------------------------------------------------- Rechazado

function Rechazado({ datos, pedido }: { datos: Resultado; pedido: Pedido | null }) {
  const reintentar = datos.trabajo_id ? `/kits/${datos.trabajo_id}` : null;
  return (
    <>
      <section className={`${styles.tarjeta} ${styles.cabecera}`}>
        <span className={`${styles.icono} ${styles.iconoAviso}`} aria-hidden>
          <AlertTriangle size={40} strokeWidth={2.2} />
        </span>
        <h1 className={styles.titulo}>Tu pago no fue aprobado</h1>
        <p className={styles.texto}>No se hizo ningún cobro. Puedes intentarlo de nuevo.</p>
        <Franja datos={datos} pedido={pedido} />
      </section>

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Por qué suele pasar</h2>
        <ul className={styles.causas}>
          <li>El saldo o el cupo no alcanzaba para el total.</li>
          <li>Algún dato de la tarjeta o de la cuenta no coincidía.</li>
          <li>El banco bloqueó la operación o superaste tu límite diario.</li>
        </ul>
        <p className={styles.consejo}>
          Puedes intentarlo con otro medio: tarjeta, PSE o Nequi.
        </p>
      </section>

      <div className={styles.acciones}>
        {reintentar && (
          <Link href={reintentar} className={styles.boton}>
            Intentar de nuevo
          </Link>
        )}
        <Link
          href="/dashboard"
          className={reintentar ? `${styles.boton} ${styles.secundario}` : styles.boton}
        >
          Ir a mi panel
        </Link>
      </div>
    </>
  );
}

// ------------------------------------------------------------ Piezas comunes

const MEDIOS = {
  tarjeta: { nombre: "Tarjeta", Icono: CreditCard },
  pse: { nombre: "PSE", Icono: Landmark },
  nequi: { nombre: "Nequi", Icono: Smartphone },
} as const;

// Total, medio de pago, fecha y numero de pedido, en una franja.
function Franja({ datos, pedido }: { datos: Resultado; pedido: Pedido | null }) {
  const medio = pedido?.pago ? MEDIOS[pedido.pago.metodo] : null;
  const fecha = pedido
    ? new Date(pedido.creado_en).toLocaleString("es-CO", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;
  return (
    <dl className={styles.franja}>
      <div className={styles.franjaTotal}>
        <dt>Total</dt>
        <dd className="cifra">{formatearPesos(datos.total)}</dd>
      </div>
      {medio && (
        <div>
          <dt>Medio</dt>
          <dd className={styles.medio}>
            <medio.Icono size={16} aria-hidden /> {medio.nombre}
          </dd>
        </div>
      )}
      {fecha && (
        <div>
          <dt>Fecha</dt>
          <dd>{fecha}</dd>
        </div>
      )}
      <div>
        <dt>Pedido</dt>
        <dd className={styles.codigo}>{datos.pedido_id.slice(0, 8).toUpperCase()}</dd>
      </div>
    </dl>
  );
}

// Los productos del pedido. Un kit repite el mismo producto por hijo: se
// agrupan por sku para que la lista diga "x 3" y no lo mismo tres veces.
function Resumen({ pedido }: { pedido: Pedido }) {
  const [todos, setTodos] = useState(false);
  const agrupados = new Map<string, { sku: string; nombre: string; cantidad: number; subtotal: number }>();
  for (const l of pedido.lineas) {
    const previo = agrupados.get(l.sku);
    const subtotal = l.cantidad * l.precio_unitario;
    if (previo) {
      previo.cantidad += l.cantidad;
      previo.subtotal += subtotal;
    } else {
      agrupados.set(l.sku, { sku: l.sku, nombre: l.nombre, cantidad: l.cantidad, subtotal });
    }
  }
  const productos = [...agrupados.values()];
  const visibles = todos ? productos : productos.slice(0, PRODUCTOS_VISIBLES);
  const ocultos = productos.length - visibles.length;

  return (
    <section className={styles.tarjeta}>
      <h2 className={styles.subtitulo}>
        Tu pedido <span className={styles.contador}>{productos.length} productos</span>
      </h2>
      <ul className={styles.productos}>
        {visibles.map((p) => (
          <li key={p.sku} className={styles.producto}>
            <span className={styles.productoNombre}>
              {p.nombre}
              <span className={styles.cantidad}> × {p.cantidad}</span>
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

function Entrega({ pedido }: { pedido: Pedido }) {
  const envio = pedido.envio!;
  return (
    <section className={styles.tarjeta}>
      <h2 className={styles.subtitulo}>Entrega</h2>
      <p className={styles.entrega}>
        <MapPin size={18} aria-hidden className={styles.entregaIcono} />
        <span>
          <strong>{envio.destinatario}</strong>
          <br />
          {envio.direccion}, {envio.ciudad}
        </span>
      </p>
    </section>
  );
}

function Confirmando({ transaccion, texto }: { transaccion: string; texto?: string }) {
  return (
    <section className={`${styles.tarjeta} ${styles.cabecera}`}>
      <span className={`${styles.icono} ${styles.iconoInfo}`} aria-hidden>
        <Loader2 size={40} className={styles.girando} />
      </span>
      <h1 className={styles.titulo}>Estamos confirmando tu pago</h1>
      <p className={styles.texto}>
        {texto ?? "Tu banco está confirmando la operación. Esto puede tardar unos segundos."}
      </p>
      <p className={styles.referencia}>Transacción {transaccion}</p>
    </section>
  );
}

function Aviso({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <>
      <section className={`${styles.tarjeta} ${styles.cabecera}`}>
        <span className={`${styles.icono} ${styles.iconoAviso}`} aria-hidden>
          <AlertTriangle size={40} strokeWidth={2.2} />
        </span>
        <h1 className={styles.titulo}>{titulo}</h1>
        <p className={styles.texto}>{texto}</p>
      </section>
      <div className={styles.acciones}>
        <Link href="/dashboard" className={styles.boton}>
          Ir a mi panel
        </Link>
      </div>
    </>
  );
}
