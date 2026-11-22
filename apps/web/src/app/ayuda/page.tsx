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

const PREGUNTAS = [
  {
    Icono: ListChecks,
    pregunta: "¿Cómo armo mi kit?",
    respuesta:
      "Eliges colegio y grado, o subes la lista. Armamos un solo pedido con lo de todos tus hijos y te lo mostramos en tres kits.",
  },
  {
    Icono: PackageSearch,
    pregunta: '¿Por qué a veces dicen "no lo tenemos"?',
    respuesta:
      "Porque preferimos decírtelo a cambiarlo por otra cosa. Nunca te damos algo parecido haciéndolo pasar por lo que pediste.",
  },
  {
    Icono: UserCheck,
    pregunta: "¿Qué es la revisión humana?",
    respuesta:
      "Antes de que veas tu kit, una persona de Tukit resuelve lo dudoso, como una edición de libro o un útil ambiguo.",
  },
  {
    Icono: LayoutGrid,
    pregunta: "¿Por qué tres kits?",
    respuesta:
      "Ahorrador, Fan y Premium cubren la misma lista; cambian las marcas y el precio. Te sugerimos uno, pero decides tú.",
  },
  {
    Icono: Users,
    pregunta: "¿Cómo funcionan los personajes por hijo?",
    respuesta:
      "Cada hijo tiene su personaje para distinguir de un vistazo qué es de quién, sin pedidos aparte.",
  },
  {
    Icono: Lock,
    pregunta: "¿Ya puedo pagar?",
    respuesta:
      "Sí. Eliges el kit, pones la dirección y pagas. En esta versión de prueba el pago es simulado y no se cobra nada.",
  },
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
              <div className={styles.cuerpo}>
                <p className={styles.respuesta}>{respuesta}</p>
              </div>
            </details>
          ))}
        </Revelar>
      </section>

      <section className={styles.soporte} aria-labelledby="titulo-soporte">
        <h2 id="titulo-soporte" className={styles.tituloSeccion}>
          ¿No encontraste tu respuesta?
        </h2>

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
