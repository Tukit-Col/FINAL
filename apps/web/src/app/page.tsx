import Link from "next/link";
import { origenDeDatos } from "@tukit/contrato/servidor";
import styles from "./Inicio.module.css";

export const dynamic = "force-dynamic";

// El titular lo elige el DOLOR declarado en la encuesta, no el precio.
// 37 % disponibilidad y agotados, 28 % libros y plan lector, 22 % no
// encontrar todo en un solo lugar, 17 % precio. Por eso la pagina abre
// diciendo que se va a decir la verdad sobre lo que hay y sobre que edicion
// es cual, y el ahorro aparece al final y en voz baja: es el cuarto dolor de
// cuatro, y liderar con descuentos seria contestar la pregunta que menos
// gente hizo.
const DOLORES = [
  {
    porcentaje: "37 %",
    titulo: "Recorrer papelerias y que este agotado",
    respuesta:
      "Si no lo tenemos, te lo decimos con esas palabras. Nunca te ofrecemos algo parecido haciendolo pasar por lo que pediste.",
  },
  {
    porcentaje: "28 %",
    titulo: "Los libros y el plan lector",
    respuesta:
      "Los textos se resuelven por edicion, no por parecido. Y cuando el colegio los cierra a una editorial, te decimos como conseguirlos en vez de callarlo.",
  },
  {
    porcentaje: "22 %",
    titulo: "No encontrar todo en un solo lugar",
    respuesta:
      "Un solo pedido para todos tus hijos, con lo repetido junto: dos borradores sueltos cuestan mas que una caja de diez.",
  },
  {
    porcentaje: "17 %",
    titulo: "El precio",
    respuesta:
      "Tres kits con el mismo alcance y precios distintos. Te marcamos uno y te decimos por que, pero los otros dos quedan a la vista.",
  },
];

export default async function Inicio() {
  // Las cifras del heroe salen del catalogo de verdad, no de un texto fijo.
  // Si el catalogo baja, la portada baja con el, que es lo que queremos: una
  // portada que promete lo que el sistema no tiene es la forma mas cara de
  // mentir.
  const { resumen } = await origenDeDatos().catalogo();

  return (
    <div className={styles.pagina}>
      <section className={styles.heroe}>
        <div className={styles.heroeTexto}>
          <p className={styles.antetitulo}>Listas escolares, resueltas</p>
          <h1 className={styles.titular}>
            Te decimos que hay <em>de verdad</em> disponible, y que libro es
            exactamente cual.
          </h1>
          <p className={styles.bajada}>
            Elige tu colegio y tu grado, o sube el archivo de la lista. Te armamos tres
            kits con todo lo de tus hijos en un solo pedido. Lo que no tenemos te lo
            decimos, no te lo cambiamos por otra cosa.
          </p>

          <div className={styles.acciones}>
            <Link href="/empezar" className={styles.botonPrimario}>
              Armar mi kit
            </Link>
            <Link href="/catalogo" className={styles.botonSecundario}>
              Ver que hay en catalogo
            </Link>
          </div>

          <dl className={styles.cifras}>
            <div>
              <dt>Productos curados</dt>
              <dd className="cifra">{resumen.productos}</dd>
            </div>
            <div>
              <dt>Utiles distintos</dt>
              <dd className="cifra">{resumen.conceptos}</dd>
            </div>
            <div>
              <dt>Tiendas comparadas</dt>
              <dd className="cifra">{resumen.tiendas}</dd>
            </div>
            <div className={styles.cifraHonesta}>
              <dt>Todavia no tenemos</dt>
              <dd className="cifra">{resumen.conceptos_sin_producto}</dd>
            </div>
          </dl>
          <p className={styles.notaCifras}>
            Esa ultima cifra tambien la publicamos. Un catalogo que solo cuenta lo que
            si tiene es el que te hace perder la tarde en la papeleria.
          </p>
        </div>
      </section>

      <section className={styles.dolores} aria-labelledby="titulo-dolores">
        <h2 id="titulo-dolores" className={styles.tituloSeccion}>
          Lo que nos dijeron 60 acudientes que mas les duele
        </h2>
        <ul className={styles.rejillaDolores}>
          {DOLORES.map((dolor) => (
            <li key={dolor.titulo} className={styles.dolor}>
              <span className={`${styles.porcentaje} cifra`}>{dolor.porcentaje}</span>
              <h3>{dolor.titulo}</h3>
              <p>{dolor.respuesta}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.comoFunciona} aria-labelledby="titulo-como">
        <h2 id="titulo-como" className={styles.tituloSeccion}>
          Como funciona
        </h2>
        <ol className={styles.pasos}>
          <li>
            <span className={styles.numero}>1</span>
            <div>
              <h3>Nos dices de quien es la lista</h3>
              <p>
                Eliges colegio y grado, o subes el archivo. Es un pedido por hogar, no
                por hijo: asi podemos juntar lo que se repite entre hermanos.
              </p>
            </div>
          </li>
          <li>
            <span className={styles.numero}>2</span>
            <div>
              <h3>Te vas a hacer otra cosa</h3>
              <p>
                Armar el kit toma minutos, no segundos, porque preferimos acertar a ir
                rapido. Te avisamos al correo y al celular cuando este.
              </p>
            </div>
          </li>
          <li>
            <span className={styles.numero}>3</span>
            <div>
              <h3>Una persona lo revisa antes de que lo veas</h3>
              <p>
                Nadie de Tukit te manda un kit sin mirarlo. Lo que quedo dudoso lo
                resuelve alguien, y solo entonces te llega.
              </p>
            </div>
          </li>
          <li>
            <span className={styles.numero}>4</span>
            <div>
              <h3>Eliges entre tres</h3>
              <p>
                Ahorrador, Fan y Premium, con el mismo alcance. Te marcamos uno y te
                explicamos por que, pero decides tu.
              </p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  );
}
