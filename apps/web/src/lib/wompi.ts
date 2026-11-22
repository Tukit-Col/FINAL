import type { WidgetWompi } from "@tukit/contrato";

const SCRIPT_WIDGET = "https://checkout.wompi.co/widget.js";

interface ResultadoWidget {
  transaction?: { id?: string; status?: string } | null;
}

type OpcionesWidget = WidgetWompi & { bootstrapTransport: "postmessage" };

interface WidgetCheckoutInstancia {
  open(callback: (resultado: ResultadoWidget) => void): void;
}

declare global {
  interface Window {
    WidgetCheckout?: new (opciones: OpcionesWidget) => WidgetCheckoutInstancia;
  }
}

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
      cargando = null;
      script.remove();
      rechazar(new Error("No se pudo cargar el widget de Wompi."));
    };
    document.head.appendChild(script);
  });
  return cargando;
}

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
