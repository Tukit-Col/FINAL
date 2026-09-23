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
 * Revelado por scroll: el elemento aparece cuando entra en pantalla. Para
 * secciones largas (portada, catálogo). Devuelve el ScrollTrigger para poder
 * limpiarlo. Con movimiento reducido deja todo visible y no crea trigger.
 */
export function revelarEnScroll(
  objetivos: gsap.TweenTarget,
  opciones: { cadaUno?: number } = {},
): void {
  if (prefiereMenosMovimiento()) {
    gsap.set(objetivos, { opacity: 1, y: 0, scale: 1 });
    return;
  }
  const elementos = gsap.utils.toArray<HTMLElement>(objetivos);
  elementos.forEach((el) => {
    gsap.from(el, {
      opacity: 0,
      y: 28,
      scale: 0.95,
      duration: 0.5,
      ease: EASE_CLAY,
      scrollTrigger: { trigger: el, start: "top 88%", once: true },
    });
  });
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
    ease: presionado ? "power2.out" : EASE_CLAY,
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
