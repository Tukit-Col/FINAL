// El "cómo funciona" como línea de tiempo que se dibuja al hacer scroll.
//
// Decisiones:
// - Es la única pieza de la portada con animación ligada al scroll y por eso es componente de cliente;
//   el resto de la página sigue siendo Server Component.
// - Pasa por el helper de motion del contrato: con `prefers-reduced-motion` no anima nada y el bloque
//   se lee como una lista ordenada normal. La animación es el adorno, no el contenido.

"use client";

import { useRef, type ElementType } from "react";
import {
  School,
  ScanText,
  Store,
  Boxes,
  UserCheck,
  BellRing,
  Truck,
} from "lucide-react";
import { useGSAP, gsap, ScrollTrigger, prefiereMenosMovimiento } from "@tukit/contrato/motion";
import styles from "./LineaDelTiempo.module.css";

interface Etapa {
  Icono: ElementType;
  titulo: string;
  texto: string;
  actor: string;
  proximamente?: boolean;
}

const ETAPAS: Etapa[] = [
  {
    Icono: School,
    titulo: "Nos dices de quién es la lista",
    texto:
      "Eliges colegio y grado, o subes la foto de la lista. Es un pedido por hogar, no por hijo, para poder juntar lo que se repite entre hermanos.",
    actor: "Tú, en un minuto",
  },
  {
    Icono: ScanText,
    titulo: "Leemos la lista tal como está escrita",
    texto:
      "“Cuaderno cosido de 100 hojas” es una cosa y “cuaderno argollado” es otra. Interpretamos cada renglón sin adivinar ni redondear a lo parecido.",
    actor: "Lo hace la IA",
  },
  {
    Icono: Store,
    titulo: "Comparamos precios en varias tiendas",
    texto:
      "El mismo útil, buscado en las tiendas que de verdad lo tienen. No una sola papelería: las que hay, con su precio de hoy.",
    actor: "Lo hace la IA",
  },
  {
    Icono: Boxes,
    titulo: "Armamos tres kits con todo",
    texto:
      "Ahorrador, Fan y Premium, con el mismo alcance y todos tus hijos en un solo pedido. Los textos, por edición; nunca por parecido.",
    actor: "Lo hace la IA",
  },
  {
    Icono: UserCheck,
    titulo: "Una persona lo revisa antes de que lo veas",
    texto:
      "Nadie recibe un kit que una máquina soltó sola. Lo que quedó dudoso lo resuelve alguien del equipo, y solo entonces te llega.",
    actor: "Lo revisa una persona",
  },
  {
    Icono: BellRing,
    titulo: "Te avisamos y eliges",
    texto:
      "Te escribimos al correo y al celular cuando esté. Te marcamos un kit y te explicamos por qué, pero los tres quedan a la vista y decides tú.",
    actor: "Decides tú",
  },
  {
    Icono: Truck,
    titulo: "Pagas y te llega a casa",
    texto:
      "Un pago, y el pedido llega armado a tu puerta. En esta versión de prueba el pago es simulado: no se cobra nada.",
    actor: "Pagas tú",
  },
];

export default function LineaDelTiempo() {
  const ref = useRef<HTMLOListElement>(null);

  useGSAP(
    () => {
      const lista = ref.current;
      if (!lista) return;
      const relleno = lista.querySelector<HTMLElement>(`.${styles.rielRelleno}`);
      const etapas = gsap.utils.toArray<HTMLElement>(`.${styles.etapa}`, lista);

      if (prefiereMenosMovimiento()) {
        if (relleno) gsap.set(relleno, { scaleY: 1 });
        etapas.forEach((el) => {
          gsap.set(el, { opacity: 1, x: 0 });
          el.classList.add(styles.activa);
        });
        return;
      }

      if (relleno) {
        gsap.set(relleno, { transformOrigin: "top center" });
        gsap.fromTo(
          relleno,
          { scaleY: 0 },
          {
            scaleY: 1,
            ease: "none",
            scrollTrigger: {
              trigger: lista,
              start: "top 60%",
              end: "bottom 75%",
              scrub: true,
            },
          },
        );
      }

      etapas.forEach((el) => {
        gsap.from(el, {
          opacity: 0,
          x: -16,
          duration: 0.5,
          ease: "power3.out",
          scrollTrigger: { trigger: el, start: "top 82%", once: true },
        });
        ScrollTrigger.create({
          trigger: el,
          start: "top 62%",
          onEnter: () => el.classList.add(styles.activa),
          onLeaveBack: () => el.classList.remove(styles.activa),
        });
      });
    },
    { scope: ref },
  );

  return (
    <ol ref={ref} className={styles.linea}>
      <span className={styles.riel} aria-hidden="true">
        <span className={styles.rielRelleno} />
      </span>

      {ETAPAS.map(({ Icono, titulo, texto, actor, proximamente }, i) => (
        <li
          key={titulo}
          className={styles.etapa}
          data-estado={proximamente ? "proximamente" : undefined}
        >
          <span className={styles.punto} aria-hidden="true">
            <Icono size={22} strokeWidth={2.2} />
          </span>
          <div className={styles.contenido}>
            <div className={styles.encabezado}>
              <span className={styles.paso}>Paso {i + 1}</span>
              <span className={styles.actor}>{actor}</span>
            </div>
            <h3>{titulo}</h3>
            <p>{texto}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
