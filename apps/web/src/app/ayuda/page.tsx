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
  Mail,
} from "lucide-react";
import Revelar from "@/components/Revelar";
import styles from "./Ayuda.module.css";

// Página informativa, no un formulario. No hay backend de soporte todavía, así
// que no fingimos un canal que no existe: las respuestas explican el producto
// tal como es y el bloque de contacto dice en voz alta que está en construcción.

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
      "Todavía no. El pago vive en el servicio de comercio y aún no está arriba, así que el botón de pagar está apagado a propósito y te dice por qué. Cuando ese servicio se conecte, se habilita; al confirmar, el precio se congela.",
  },
];

export default function AyudaPage() {
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
          {PREGUNTAS.map(({ Icono, pregunta, respuesta }) => (
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
              <p className={styles.respuesta}>{respuesta}</p>
            </details>
          ))}
        </Revelar>
      </section>

      <section className={styles.contacto} aria-labelledby="titulo-contacto">
        <div className={styles.contactoIcono} aria-hidden="true">
          <Mail size={26} strokeWidth={2.2} />
        </div>
        <div className={styles.contactoTexto}>
          <h2 id="titulo-contacto">¿No encontraste tu respuesta?</h2>
          <p>
            Nuestro canal de soporte todavía está en construcción. Mientras lo
            montamos, escríbenos a{" "}
            <a href="mailto:hola@tukit.co" className={styles.correo}>
              hola@tukit.co
            </a>{" "}
            y te respondemos una persona de verdad. Aún no es un buzón automático,
            así que danos un momento.
          </p>
        </div>
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
