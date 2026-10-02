// El widget de Wompi: carga su script una sola vez y abre el pago en un modal.
//
// El modal no saca al acudiente de Tukit y no necesita `redirectUrl` (el
// checkout de Wompi rechaza volver a localhost). Lo que el callback entrega es
// informativo: Wompi pide no validar con eso, asi que el id de la transaccion
// se manda a `/pago/resultado`, que confirma con el servidor.

import type { WidgetWompi } from "@tukit/contrato";

const SCRIPT_WIDGET = "https://checkout.wompi.co/widget.js";

interface ResultadoWidget {
  transaction?: { id?: string; status?: string } | null;
}

interface WidgetCheckoutInstancia {
  open(callback: (resultado: ResultadoWidget) => void): void;
}

declare global {
  interface Window {
    WidgetCheckout?: new (opciones: WidgetWompi) => WidgetCheckoutInstancia;
  }
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
  new window.WidgetCheckout(opciones).open((resultado) => {
    const id = resultado?.transaction?.id;
    if (id) alTerminar(id);
  });
}
