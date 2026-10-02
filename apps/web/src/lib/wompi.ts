// El widget de Wompi: carga su script una sola vez y abre el pago en un modal.
//
// Con tarjeta o Nequi el modal no saca al acudiente de Tukit y el callback
// entrega la transaccion. PSE si se lleva la pestana al banco: ahi el callback
// se pierde y Wompi vuelve por `redirectUrl` a `/pago/resultado?id=...`. Lo que
// llega por cualquiera de los dos caminos es informativo: la pagina de
// resultado confirma con el servidor.

import type { WidgetWompi } from "@tukit/contrato";

const SCRIPT_WIDGET = "https://checkout.wompi.co/widget.js";

interface ResultadoWidget {
  transaction?: { id?: string; status?: string } | null;
}

// Lo que el constructor recibe: las opciones firmadas mas el transporte.
type OpcionesWidget = WidgetWompi & { bootstrapTransport: "postmessage" };

interface WidgetCheckoutInstancia {
  open(callback: (resultado: ResultadoWidget) => void): void;
}

declare global {
  interface Window {
    WidgetCheckout?: new (opciones: OpcionesWidget) => WidgetCheckoutInstancia;
  }
}

/**
 * Las opciones con que se abre el widget. Por omision Wompi serializa toda la
 * configuracion en la URL de su iframe, y su CDN responde 403 cuando ahi va un
 * `redirect-url` a localhost: el iframe no carga y el modal se queda girando.
 * Con `bootstrapTransport: "postmessage"` la configuracion viaja por mensaje y
 * la URL del iframe queda limpia.
 */
export function opcionesWidget(opciones: WidgetWompi): OpcionesWidget {
  return { ...opciones, bootstrapTransport: "postmessage" };
}

let cargando: Promise<void> | null = null;

function cargarScript(): Promise<void> {
  if (window.WidgetCheckout) return Promise.resolve();
  if (cargando) return cargando;
  cargando = new Promise<void>((resolver, rechazar) => {
    const script = document.createElement("script");
    script.src = SCRIPT_WIDGET;
    script.async = true;
    script.onload = () => resolver();
    script.onerror = () => {
      // Se permite reintentar: el siguiente clic vuelve a pedir el script.
      cargando = null;
      script.remove();
      rechazar(new Error("No se pudo cargar el widget de Wompi."));
    };
    document.head.appendChild(script);
  });
  return cargando;
}

/**
 * Abre el widget y llama `alTerminar` con el id de la transaccion cuando Wompi
 * la reporta. Si el acudiente cierra el modal sin pagar, Wompi no entrega
 * transaccion y `alTerminar` no se llama.
 */
export async function abrirWidgetWompi(
  opciones: WidgetWompi,
  alTerminar: (transaccionId: string) => void,
): Promise<void> {
  await cargarScript();
  if (!window.WidgetCheckout) throw new Error("El widget de Wompi no quedo disponible.");
  new window.WidgetCheckout(opcionesWidget(opciones)).open((resultado) => {
    const id = resultado?.transaction?.id;
    if (id) alTerminar(id);
  });
}
