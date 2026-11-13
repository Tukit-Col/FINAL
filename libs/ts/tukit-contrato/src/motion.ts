// Motion compartido — el tacto de plastilina, en un solo lugar.
//
// Vive aparte de `indice.ts` a proposito: GSAP es codigo de NAVEGADOR y no
// puede entrar al bundle de servidor. Igual que `servidor.ts` guarda lo que
// solo corre en Node, esto guarda lo que solo corre en el cliente. Se importa
// desde "@tukit/contrato/motion" y solo desde componentes marcados "use client".
//
// La regla de oro: TODO respeta `prefers-reduced-motion`. Si el sistema pide
// menos movimiento, los helpers no animan —dejan el elemento en su estado
// final— porque una animacion que el usuario pidio no ver es un defecto de
// accesibilidad, no un adorno. Los tiempos y la curva de rebote son los mismos
// tokens que declara `tokens.css` (`--ease-clay`, `--dur-*`).

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

/** La curva de rebote de plastilina, en la forma que entiende GSAP. */
export const EASE_CLAY = "back.out(1.4)";
export const EASE_SUAVE = "power3.out";

/** ¿El usuario pidió menos movimiento? Se consulta en cada animacion, no una
 *  vez al cargar: alguien puede cambiar el ajuste con la pestaña abierta. */
export function prefiereMenosMovimiento(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Reexporta lo que las pantallas necesitan sin que cada una registre plugins
 *  ni recuerde el nombre exacto del paquete. */
export { gsap, ScrollTrigger, useGSAP };

/**
 * Entrada con rebote para una lista de elementos (tarjetas, pasos, kits).
 * Es el preset por defecto del rediseño: aparecen inflándose y subiendo un
 * poco, en cascada. Con movimiento reducido no anima y los deja visibles.
 */
export function entradaEnCascada(
  objetivos: gsap.TweenTarget,
  opciones: { retraso?: number; cadaUno?: number; desde?: gsap.StaggerVars["from"] } = {},
): gsap.core.Tween | undefined {
  if (prefiereMenosMovimiento()) {
    gsap.set(objetivos, { opacity: 1, y: 0, scale: 1 });
    return undefined;
  }
  return gsap.from(objetivos, {
    opacity: 0,
    y: 18,
    scale: 0.94,
    duration: 0.45,
    delay: opciones.retraso ?? 0,
    ease: EASE_CLAY,
    stagger: { each: opciones.cadaUno ?? 0.07, from: opciones.desde ?? "start" },
  });
}

/**
 * Entrada simple de un elemento (héroe, tarjeta suelta). Sin cascada.
 */
export function entrada(
  objetivo: gsap.TweenTarget,
  opciones: { retraso?: number; y?: number } = {},
): gsap.core.Tween | undefined {
  if (prefiereMenosMovimiento()) {
    gsap.set(objetivo, { opacity: 1, y: 0, scale: 1 });
    return undefined;
  }
  return gsap.from(objetivo, {
    opacity: 0,
    y: opciones.y ?? 22,
    scale: 0.96,
    duration: 0.5,
    delay: opciones.retraso ?? 0,
    ease: EASE_CLAY,
  });
}

/**
 * Revelado al entrar en pantalla, a prueba de primer cargue.
 *
 * Antes cada elemento tenia su propio ScrollTrigger sobre un `gsap.from`: las
 * posiciones se calculaban antes de que cargaran fuentes e imagenes, asi que
 * los de arriba quedaban mal medidos y solo disparaban los ultimos. Ahora un
 * unico IntersectionObserver (que mide en vivo, sin posiciones cacheadas):
 *  - lo que ya esta en pantalla al montar anima de inmediato, en cascada;
 *  - lo demas anima al entrar, en tandas escalonadas;
 *  - un seguro revela todo si el observador nunca dispara, para que nada
 *    quede invisible.
 * Con movimiento reducido (o sin IntersectionObserver) todo queda visible.
 * Devuelve la funcion de limpieza (la que useGSAP llama al desmontar).
 */
export function revelarAlEntrar(
  objetivos: gsap.TweenTarget,
  opciones: { cadaUno?: number; retraso?: number; y?: number } = {},
): () => void {
  const elementos = gsap.utils.toArray<HTMLElement>(objetivos);
  if (
    prefiereMenosMovimiento() ||
    typeof IntersectionObserver === "undefined" ||
    elementos.length === 0
  ) {
    gsap.set(elementos, { opacity: 1, y: 0, scale: 1 });
    return () => {};
  }
  const cadaUno = opciones.cadaUno ?? 0.08;
  const y = opciones.y ?? 24;
  const pendientes = new Set(elementos);
  const timers: number[] = [];
  gsap.set(elementos, { opacity: 0, y, scale: 0.96 });

  const mostrar = (lote: HTMLElement[], retraso = 0) => {
    lote.forEach((el) => pendientes.delete(el));
    gsap.to(lote, {
      opacity: 1,
      y: 0,
      scale: 1,
      duration: 0.55,
      delay: retraso,
      ease: EASE_CLAY,
      stagger: cadaUno,
      overwrite: "auto",
      // Suelta los estilos en linea: el hover/translate de CSS vuelve a mandar.
      onComplete: () => {
        gsap.set(lote, { clearProps: "opacity,transform" });
      },
    });
  };

  const alto = window.innerHeight;
  const visibles = elementos.filter((el) => {
    const r = el.getBoundingClientRect();
    return r.top < alto * 0.92 && r.bottom > 0;
  });
  if (visibles.length) mostrar(visibles, opciones.retraso ?? 0);

  const resto = elementos.filter((el) => pendientes.has(el));
  const obs = new IntersectionObserver(
    (entradas) => {
      const lote = entradas
        .filter((e) => e.isIntersecting && pendientes.has(e.target as HTMLElement))
        .map((e) => e.target as HTMLElement);
      lote.forEach((el) => obs.unobserve(el));
      if (lote.length) mostrar(lote);
    },
    { threshold: 0.08, rootMargin: "0px 0px -8% 0px" },
  );
  resto.forEach((el) => obs.observe(el));

  // Seguro: si pasados 8 s algo sigue oculto estando en pantalla, se revela.
  timers.push(
    window.setTimeout(() => {
      const atascados = Array.from(pendientes).filter((el) => {
        const r = el.getBoundingClientRect();
        return r.top < window.innerHeight && r.bottom > 0;
      });
      if (atascados.length) mostrar(atascados);
    }, 8000),
  );

  return () => {
    obs.disconnect();
    timers.forEach((t) => window.clearTimeout(t));
    gsap.set(elementos, { clearProps: "opacity,transform" });
  };
}

/** Compatibilidad: mismo nombre de antes, ahora con el observador robusto. */
export function revelarEnScroll(
  objetivos: gsap.TweenTarget,
  opciones: { cadaUno?: number } = {},
): () => void {
  return revelarAlEntrar(objetivos, opciones);
}

/**
 * "Squish" de plastilina al presionar: el elemento se hunde a 0.94 y vuelve.
 * Se engancha a mano en onPointerDown/Up cuando un botón lo quiere; el press
 * también está en CSS (:active) para que funcione sin JS. Con movimiento
 * reducido, no hace nada.
 */
export function squish(el: Element | null, presionado: boolean): void {
  if (!el || prefiereMenosMovimiento()) return;
  gsap.to(el, {
    scale: presionado ? 0.94 : 1,
    duration: presionado ? 0.12 : 0.32,
    // El regreso NO rebota: `back.out` sobrepasa el 1 y, si el usuario vuelve a
    // tocar antes de que el tween termine, deja la escala colgada por encima de
    // 1 (el sintoma de "crece y no vuelve"). `overwrite` mata cualquier tween
    // de escala en curso sobre el mismo nodo para que siempre resuelva a 1.
    ease: "power2.out",
    overwrite: "auto",
  });
}

/**
 * Late (pulso) suave para llamar la atención sobre algo vivo: la marca de la
 * etapa en curso, un contador que sube. Loop infinito hasta que se mate.
 */
export function latido(objetivo: gsap.TweenTarget): gsap.core.Tween | undefined {
  if (prefiereMenosMovimiento()) return undefined;
  return gsap.to(objetivo, {
    scale: 1.06,
    duration: 0.7,
    ease: "sine.inOut",
    repeat: -1,
    yoyo: true,
  });
}
