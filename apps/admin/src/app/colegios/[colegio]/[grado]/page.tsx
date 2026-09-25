// `/colegios/{colegio}/{grado}` — P4, la lista verificada de un grado.
//
// Dos paneles lado a lado, como el revisor de onboarding: a la izquierda el PDF
// oficial que dio lugar a la lista (embebido desde `/api/listas/{version_id}/
// documento`, la URL del backend no llega al navegador); a la derecha los
// renglones ya resueltos, uno por tarjeta, con su medallón de orden, su libro y
// una píldora de adquisición coloreada por si Tukit lo puede surtir o no. El
// botón "Editar" clona la vigente en una versión nueva sin revisar
// (`nuevaVersion`, vía el componente cliente `EditarLista`) y cae en el revisor.
//
// Server Component: `listaOficial()` sale del origen directamente. Un 404 se
// traduce a `notFound()`.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { ItemListaOficial, ListaOficial } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import EditarLista from "@/components/EditarLista";
import styles from "../../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string; grado: string }>;
}

// Etiqueta y color de la píldora de adquisición. El eje que importa: los modos
// SURTIBLES (Tukit los pone en el carrito) van en verde; la venta directa del
// colegio/editorial en ámbar; el resto en neutro. Un modo desconocido cae en
// neutro con su texto crudo, nunca se rompe la fila.
const ADQUISICION: Record<string, { etiqueta: string; clase: string }> = {
  mercado_abierto: { etiqueta: "Mercado abierto", clase: styles.adqSurte },
  libro_libre: { etiqueta: "Libro libre", clase: styles.adqSurte },
  venta_directa_editorial: { etiqueta: "Venta directa", clase: styles.adqDirecta },
  edicion_exclusiva: { etiqueta: "Edición exclusiva", clase: styles.adqDirecta },
  plataforma: { etiqueta: "Plataforma", clase: styles.adqNeutra },
  diferido: { etiqueta: "Diferido", clase: styles.adqNeutra },
};

function adquisicion(modo: string): { etiqueta: string; clase: string } {
  return ADQUISICION[modo] ?? { etiqueta: modo, clase: styles.adqNeutra };
}

function Renglon({ item }: { item: ItemListaOficial }) {
  const adq = adquisicion(item.modo_adquisicion);
  return (
    <li className={styles.renglon}>
      <span className={styles.renglonNumero}>{item.orden}</span>
      <div className={styles.renglonCuerpo}>
        <p className={styles.renglonTexto}>{item.texto_generico ?? item.texto_original}</p>
        {item.libro ? (
          <span className={styles.libroBadge}>
            📕 {item.libro.titulo}
            {item.libro.editorial ? ` · ${item.libro.editorial}` : ""}
          </span>
        ) : null}
        <div className={styles.renglonMeta}>
          <span className={styles.metaCantidad}>
            <span className="cifra">{item.cantidad}</span> u.
          </span>
          {item.categoria ? <span className={styles.categoriaPill}>{item.categoria}</span> : null}
          <span className={`${styles.adquisicionPill} ${adq.clase}`}>{adq.etiqueta}</span>
        </div>
      </div>
    </li>
  );
}

export default async function PaginaListaGrado({ params }: Props) {
  const { colegio: colegioId, grado } = await params;

  let lista: ListaOficial;
  try {
    lista = await origenDeDatos().listaOficial(colegioId, grado);
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) notFound();
    throw causa;
  }

  // El PDF cuelga de la versión; una lista sembrada/CLI no lo trae y el panel
  // muestra un vacío en vez de un iframe roto.
  const urlDocumento = lista.version_id
    ? `/api/listas/${encodeURIComponent(lista.version_id)}/documento`
    : null;

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href={`/colegios/${encodeURIComponent(colegioId)}`}>← Perfil del colegio</Link>
      </nav>

      <header className={styles.encabezado}>
        <div>
          <h1>
            {lista.grado} · <code>{lista.colegio_id}</code>
          </h1>
          <p className={styles.bajada}>
            Lista verificada, versión <span className="cifra">{lista.version}</span> · año{" "}
            <span className="cifra">{lista.anio_lectivo}</span>. Es la que ve el acudiente.
          </p>
        </div>
        <EditarLista
          colegioId={lista.colegio_id}
          grado={lista.grado}
          anioLectivo={lista.anio_lectivo}
        />
      </header>

      <div className={styles.paneles}>
        {/* -------------------------------------------- El PDF oficial */}
        <section className={styles.panel}>
          <div className={styles.panelCabecera}>
            <h2>PDF oficial</h2>
          </div>
          {urlDocumento ? (
            <iframe className={styles.marcoPdf} src={urlDocumento} title="PDF de la lista" />
          ) : (
            <p className={styles.pendienteContrato}>
              Esta versión no tiene un PDF adjunto (se cargó sin evidencia).
            </p>
          )}
        </section>

        {/* ------------------------------------------- Los renglones */}
        <section className={styles.panel}>
          <div className={styles.panelCabecera}>
            <h2>Renglones</h2>
            <span className={styles.panelConteo}>
              <span className="cifra">{lista.items.length}</span>
            </span>
          </div>
          {lista.items.length === 0 ? (
            <p className={styles.vacio}>La lista no tiene renglones.</p>
          ) : (
            <ol className={styles.renglones}>
              {lista.items.map((item) => (
                <Renglon key={item.orden} item={item} />
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
