import Link from "next/link";
import {
  Sparkles,
  Route,
  PackageSearch,
  BookMarked,
  ShoppingBasket,
  Cpu,
  ShieldCheck,
  Eye,
} from "lucide-react";
import Revelar from "@/components/Revelar";
import UtilesFlotantes from "./UtilesFlotantes";
import LineaDelTiempo from "./LineaDelTiempo";
import styles from "./Inicio.module.css";

export const dynamic = "force-dynamic";

// Marco de copy (Julian Shapiro): la portada abre con el DOLOR del acudiente,
// no con el catálogo ni con el precio. Los útiles distintos, las tiendas y los
// productos curados son cifras del backend que a un papá no le dicen nada: no
// van en el héroe. Lo que sí va es la promesa —te lo resolvemos de verdad— y la
// razón por la que es creíble —una persona revisa, y lo que no hay te lo
// decimos—. El ahorro aparece tarde y en voz baja: en la encuesta fue el dolor
// que MENOS gente nombró, y liderar con descuentos sería contestar la pregunta
// que casi nadie hizo.

// Los dolores de la encuesta, ya sin el porcentaje: el número era ruido para
// quien llega a comprar. Cada tarjeta es un dolor real y, debajo, lo que
// hacemos con él —la promesa se gana objeción por objeción, no de una—.
const DOLORES = [
  {
    Icono: PackageSearch,
    titulo: "Recorrer papelerías y que esté agotado",
    respuesta:
      "Si no lo tenemos, te lo decimos con esas palabras. Nunca te ofrecemos algo parecido haciéndolo pasar por lo que pediste.",
  },
  {
    Icono: BookMarked,
    titulo: "Los libros y el plan lector nunca cuadran",
    respuesta:
      "Los textos se resuelven por edición, no por parecido. Y cuando el colegio los cierra a una editorial, te decimos cómo conseguirlos en vez de callarlo.",
  },
  {
    Icono: ShoppingBasket,
    titulo: "No encontrar todo en un solo lugar",
    respuesta:
      "Un solo pedido para todos tus hijos, con lo repetido junto: dos borradores sueltos cuestan más que una caja de diez.",
  },
];

// Por qué es creíble: las tres cosas que hacemos distinto, cada una responde una
// objeción que el acudiente ya trae puesta ("¿otra tienda que promete?"). La
// primera es la propuesta de valor: la IA hace en minutos lo que a ti te toma
// una tarde. La segunda dice que igual una persona lo revisa (la IA no manda
// sola). La tercera es la promesa de decir la verdad sobre lo que no hay.
const RAZONES = [
  {
    Icono: Cpu,
    titulo: "Una IA arma el kit en minutos",
    texto:
      "Lee tu lista renglón por renglón y busca cada útil en las tiendas que sí lo tienen. Lo que a ti te cuesta una tarde de papelería, aquí toma minutos.",
  },
  {
    Icono: ShieldCheck,
    titulo: "Y una persona lo revisa",
    texto:
      "La IA propone, pero no manda sola. Antes de que veas tu kit, alguien del equipo revisa lo que quedó dudoso. Rápido no significa a la carrera.",
  },
  {
    Icono: Eye,
    titulo: "Te decimos lo que no tenemos",
    texto:
      "Un catálogo que solo cuenta lo que sí tiene es el que te hace perder la tarde. Nosotros publicamos también lo que todavía nos falta.",
  },
];

export default async function Inicio() {
  return (
    <div className={styles.pagina}>
      {/* Útiles esparcidos por toda la página (fondo), para que el scroll entre
          secciones no se sienta vacío. Decorativos. */}
      <UtilesFlotantes variante="pagina" />

      <section className={styles.heroe}>
        {/* Útiles en clay flotando alrededor del titular. Decorativos. */}
        <UtilesFlotantes />

        <Revelar className={styles.heroeTexto} modo="una">
          <p className={styles.antetitulo}>
            <Sparkles size={14} aria-hidden="true" strokeWidth={2.6} />
            Listas escolares, resueltas
          </p>
          {/* Header con la propuesta de valor directa: el acento va bajo lo que
              de verdad compras, que no son útiles sino la tarde de vuelta. */}
          <h1 className={styles.titular}>
            Menos filas,
            <br />
            más <em>tiempo en familia</em>.
          </h1>
          {/* Subheader: qué es + por qué es posible (la IA), en dos frases. */}
          <p className={styles.bajada}>
            Nos dices de qué colegio y grado es la lista, o le tomas una foto, y una IA te
            arma tres kits con todo lo de tus hijos en un solo pedido. Antes de que lo veas,
            una persona lo revisa, para que llegue seguro a tu casa.
          </p>

          <div className={styles.acciones}>
            <Link href="/empezar" className={styles.botonPrimario}>
              <Sparkles size={18} aria-hidden="true" strokeWidth={2.6} />
              Armar mi kit
            </Link>
            <Link href="/#como-funciona" className={styles.botonSecundario}>
              <Route size={18} aria-hidden="true" strokeWidth={2.4} />
              Ver cómo funciona
            </Link>
          </div>

          {/* Micro-prueba bajo los CTA: baja el esfuerzo percibido antes del clic. */}
          <p className={styles.tranquilizador}>
            Armar el kit no cuesta nada · Tú eliges entre tres · Sin crear cuenta para empezar
          </p>
        </Revelar>
      </section>

      <section className={styles.dolores} aria-labelledby="titulo-dolores">
        <Revelar className={styles.encabezadoSeccion} modo="una">
          <p className={styles.kicker}>Lo que nos dijeron 60 acudientes</p>
          <h2 id="titulo-dolores" className={styles.tituloSeccion}>
            Sabemos por qué la lista del colegio se vuelve una tarde perdida
          </h2>
          <p className={styles.subtituloSeccion}>
            Preguntamos qué era lo que más pesaba. No inventamos el problema: lo oímos, y
            armamos el servicio alrededor de él.
          </p>
        </Revelar>
        <Revelar as="ul" className={styles.rejillaDolores} modo="scroll" cadaUno={0.08}>
          {DOLORES.map(({ Icono, titulo, respuesta }) => (
            <li key={titulo} className={styles.dolor}>
              <span className={styles.dolorIcono} aria-hidden="true">
                <Icono size={22} strokeWidth={2.2} />
              </span>
              <h3>{titulo}</h3>
              <p>{respuesta}</p>
            </li>
          ))}
        </Revelar>
      </section>

      <section className={styles.razones} aria-labelledby="titulo-razones">
        <Revelar className={styles.encabezadoSeccion} modo="una">
          <p className={styles.kicker}>Por qué puedes confiar</p>
          <h2 id="titulo-razones" className={styles.tituloSeccion}>
            No es otra tienda que promete y desaparece
          </h2>
        </Revelar>
        <Revelar as="ul" className={styles.rejillaRazones} modo="scroll" cadaUno={0.08}>
          {RAZONES.map(({ Icono, titulo, texto }) => (
            <li key={titulo} className={styles.razon}>
              <span className={styles.razonIcono} aria-hidden="true">
                <Icono size={22} strokeWidth={2.2} />
              </span>
              <h3>{titulo}</h3>
              <p>{texto}</p>
            </li>
          ))}
        </Revelar>
      </section>

      <section id="como-funciona" className={styles.comoFunciona} aria-labelledby="titulo-como">
        <Revelar className={styles.encabezadoSeccion} modo="una">
          <p className={styles.kicker}>De la lista a tu casa</p>
          <h2 id="titulo-como" className={styles.tituloSeccion}>
            Cómo funciona, paso a paso
          </h2>
          <p className={styles.subtituloSeccion}>
            Siete pasos, y en cada uno decimos quién lo hace: tú, la IA, o una persona del
            equipo que revisa. El último todavía lo estamos construyendo, y lo decimos aquí
            en vez de prometerlo antes de tiempo.
          </p>
        </Revelar>
        <LineaDelTiempo />
      </section>

      <section className={styles.cierre} aria-labelledby="titulo-cierre">
        <div className={styles.tarjetaCierre}>
          {/* Reparto liviano de útiles en las esquinas para que la tarjeta no se
              sienta vacía. Decorativo. */}
          <UtilesFlotantes variante="cierre" />
          <Revelar className={styles.cierreTexto} modo="una">
            <h2 id="titulo-cierre" className={styles.tituloCierre}>
              Esa tarde de papelería, esta vez pásala en casa.
            </h2>
            <p className={styles.bajadaCierre}>
              Toma un minuto. Armas el kit, ves los tres precios y decides sin compromiso.
            </p>
            <Link href="/empezar" className={styles.botonPrimario}>
              <Sparkles size={18} aria-hidden="true" strokeWidth={2.6} />
              Armar mi kit
            </Link>
          </Revelar>
        </div>
      </section>
    </div>
  );
}
