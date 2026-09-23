// `/colegios/{colegio}/{grado}` — P4, la lista verificada de un grado.
//
// Muestra la lista oficial ya publicada (la que ve el acudiente), renglón por
// renglón. El botón "Editar" clona la vigente en una versión nueva sin revisar
// (`nuevaVersion`, vía el componente cliente `EditarLista`) y cae en el revisor
// de cuatro paneles con esa versión.
//
// Server Component: `listaOficial()` sale del origen directamente. Un 404 se
// traduce a `notFound()`.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { ListaOficial } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import EditarLista from "@/components/EditarLista";
import styles from "../../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string; grado: string }>;
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

      <section className={styles.tarjeta}>
        <table className={styles.tabla}>
          <thead>
            <tr>
              <th>#</th>
              <th>Renglón</th>
              <th>Cant.</th>
              <th>Categoría</th>
              <th>Adquisición</th>
            </tr>
          </thead>
          <tbody>
            {lista.items.map((item) => (
              <tr key={item.orden}>
                <td className="cifra">{item.orden}</td>
                <td>
                  {item.texto_generico ?? item.texto_original}
                  {item.libro ? (
                    <span className={styles.libro}>
                      {item.libro.titulo}
                      {item.libro.editorial ? ` · ${item.libro.editorial}` : ""}
                    </span>
                  ) : null}
                </td>
                <td className="cifra">{item.cantidad}</td>
                <td>{item.categoria ?? "—"}</td>
                <td>{item.modo_adquisicion}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
