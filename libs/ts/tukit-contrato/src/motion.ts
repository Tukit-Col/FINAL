// Motion compartido de las apps.
//
// Decisiones:
// - Vive aparte del índice porque GSAP es código de navegador y no puede entrar al bundle de servidor;
//   se importa desde "@tukit/contrato/motion" y solo desde componentes marcados "use client".
// - Todo respeta `prefers-reduced-motion`: si el sistema pide menos movimiento, los helpers dejan el
//   elemento en su estado final.
// - Los tiempos y la curva de rebote son los tokens de `tokens.css` (`--ease-clay`, `--dur-*`).

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export const EASE_CLAY = "back.out(1.4)";
export const EASE_SUAVE = "power3.out";

export function prefiereMenosMovimiento(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export { gsap, ScrollTrigger, useGSAP };

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

export function revelarEnScroll(
  objetivos: gsap.TweenTarget,
  opciones: { cadaUno?: number } = {},
): () => void {
  return revelarAlEntrar(objetivos, opciones);
}

export function squish(el: Element | null, presionado: boolean): void {
  if (!el || prefiereMenosMovimiento()) return;
  gsap.to(el, {
    scale: presionado ? 0.94 : 1,
    duration: presionado ? 0.12 : 0.32,
    ease: "power2.out",
    overwrite: "auto",
  });
}

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
