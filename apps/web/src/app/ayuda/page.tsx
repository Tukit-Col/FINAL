import Image from "next/image";
import Link from "next/link";
import {
  LifeBuoy,
  Sparkles,
  ChevronDown,
  ListChecks,
  PackageSearch,
  UserCheck,
  LayoutGrid,
  Users,
  Lock,
  MessagesSquare,
} from "lucide-react";
import Revelar from "@/components/Revelar";
import { sesionActual } from "@/lib/sesion";
import SobreSoporte from "./SobreSoporte";
import FormularioCaso from "./FormularioCaso";
import styles from "./Ayuda.module.css";

// El centro de ayuda tiene dos mitades: las preguntas frecuentes (informativas)
// y un formulario REAL para abrir una PQRS. El formulario escribe en `operacion`
// (vía `/api/casos`), así que el caso queda de verdad en la cola del back-office
// —no fingimos un canal que no existe—. La primera tarjeta de la sección de
// soporte lleva la ilustración claymorphism del sobre a la derecha.

const PREGUNTAS = [
  {
    Icono: ListChecks,
    pregunta: "¿Cómo armo mi kit?",
    respuesta:
      "Eliges tu colegio y grado, o subes el archivo de la lista. Con eso armamos un solo pedido con lo de todos tus hijos y te lo mostramos como tres kits para que elijas. Es un pedido por hogar, no por hijo: así juntamos lo que se repite entre hermanos.",
  },
  {
    Icono: PackageSearch,
    pregunta: '¿Por qué a veces dicen "no lo tenemos"?',
    respuesta:
      "Porque preferimos decírtelo a cambiártelo por otra cosa. Si un útil está agotado o no lo conseguimos, aparece marcado con esas palabras. Nunca te ofrecemos algo parecido haciéndolo pasar por lo que pediste; esa es justo la vuelta a la papelería que queremos ahorrarte.",
  },
  {
    Icono: UserCheck,
    pregunta: "¿Qué es la revisión humana?",
    respuesta:
      "Antes de que veas tu kit, una persona de Tukit lo mira. Lo que quedó dudoso (una edición de libro, un útil ambiguo en la lista) lo resuelve alguien de carne y hueso, y solo entonces te llega. Nadie te manda un kit sin revisarlo primero.",
  },
  {
    Icono: LayoutGrid,
    pregunta: "¿Por qué tres kits?",
    respuesta:
      "Ahorrador, Fan y Premium tienen el mismo alcance: cubren la misma lista. Cambian las marcas y el precio. Te marcamos uno y te explicamos por qué lo sugerimos, pero los otros dos quedan a la vista para que decidas tú.",
  },
  {
    Icono: Users,
    pregunta: "¿Cómo funcionan los personajes por hijo?",
    respuesta:
      "Cada hijo tiene su personaje para que distingas de un vistazo qué es de quién dentro del mismo pedido. Sirve para separar lo de cada uno sin tener que hacer un pedido aparte por hijo.",
  },
  {
    Icono: Lock,
    pregunta: "¿Ya puedo pagar?",
    respuesta:
      "Sí. Eliges el kit, pones la dirección de entrega y pagas en la pasarela. En esta versión de prueba el pago es simulado y no se cobra nada. Al confirmar, el precio queda congelado.",
  },
];

// Foto de cada respuesta (columna derecha en escritorio). Se reparten en ciclo
// entre las tres fotos de la marca; la imagen es de apoyo, el texto manda.
const FOTOS = [
  { src: "/marca/caja-abierta-hero.webp", alt: "Caja Tukit abierta con cuadernos, lápices y colbón ordenados" },
  { src: "/marca/preparando-la-caja.webp", alt: "Una persona acomodando útiles dentro de la caja" },
  { src: "/marca/llega-a-tu-puerta.webp", alt: "Caja Tukit Premium entregada frente a una puerta" },
];

export const dynamic = "force-dynamic";

export default async function AyudaPage() {
  const sesion = await sesionActual();
  return (
    <div className={styles.pagina}>
      <Revelar as="section" className={styles.encabezado} modo="una">
        <p className={styles.antetitulo}>
          <LifeBuoy size={14} aria-hidden="true" strokeWidth={2.6} />
          Centro de ayuda
        </p>
        <h1 className={styles.titulo}>¿En qué te ayudamos?</h1>
        <p className={styles.bajada}>
          Lo que más nos preguntan los acudientes, respondido sin rodeos. Si algo no
          está acá, más abajo te decimos cómo escribirnos.
        </p>
      </Revelar>

      <section className={styles.faq} aria-labelledby="titulo-faq">
        <h2 id="titulo-faq" className={styles.tituloSeccion}>
          Preguntas frecuentes
        </h2>
        <Revelar as="div" className={styles.lista} modo="scroll" cadaUno={0.06}>
          {PREGUNTAS.map(({ Icono, pregunta, respuesta }, i) => (
            <details key={pregunta} className={styles.tarjeta}>
              <summary className={styles.resumen}>
                <span className={styles.resumenIcono} aria-hidden="true">
                  <Icono size={20} strokeWidth={2.2} />
                </span>
                <span className={styles.resumenTexto}>{pregunta}</span>
                <ChevronDown
                  size={20}
                  strokeWidth={2.4}
                  className={styles.flecha}
                  aria-hidden="true"
                />
              </summary>
              <div className={styles.cuerpo}>
                <p className={styles.respuesta}>{respuesta}</p>
                <div className={styles.foto}>
                  <Image
                    src={FOTOS[i % FOTOS.length].src}
                    alt={FOTOS[i % FOTOS.length].alt}
                    fill
                    sizes="(max-width: 860px) 0px, 280px"
                  />
                </div>
              </div>
            </details>
          ))}
        </Revelar>
      </section>

      <section className={styles.soporte} aria-labelledby="titulo-soporte">
        <h2 id="titulo-soporte" className={styles.tituloSeccion}>
          ¿No encontraste tu respuesta?
        </h2>

        {/* Primera tarjeta: la introducción, con el SVG claymorphism a la
            derecha. En móvil el SVG se apila arriba. */}
        <Revelar as="div" className={styles.introSoporte} modo="una">
          <div className={styles.introTexto}>
            <p className={styles.introAntetitulo}>
              <MessagesSquare size={14} aria-hidden="true" strokeWidth={2.6} />
              Escríbenos
            </p>
            <h3>Abre una solicitud y una persona la atiende</h3>
            <p>
              Cuéntanos qué necesitas: una duda, una queja, un reclamo sobre un pedido o
              una idea para mejorar. Tu mensaje entra a la cola de soporte con un número
              de radicado, y para las PQRS te decimos el plazo de ley en el que
              respondemos. Nada de buzones al vacío.
            </p>
          </div>
          <div className={styles.introArte} aria-hidden="true">
            <SobreSoporte />
          </div>
        </Revelar>

        {/* Segunda tarjeta: el formulario real. */}
        <Revelar as="div" className={styles.tarjetaForma} modo="una" retraso={0.08}>
          <FormularioCaso conSesion={Boolean(sesion)} />
        </Revelar>
      </section>

      <section className={styles.cierre}>
        <h2 className={styles.cierreTitulo}>¿Listo para armar tu lista?</h2>
        <p className={styles.cierreTexto}>
          Elige tu colegio y grado, o sube el archivo. El resto lo hacemos nosotros.
        </p>
        <Link href="/empezar" className={styles.botonPrimario}>
          <Sparkles size={18} aria-hidden="true" strokeWidth={2.6} />
          Armar mi kit
        </Link>
      </section>
    </div>
  );
}
