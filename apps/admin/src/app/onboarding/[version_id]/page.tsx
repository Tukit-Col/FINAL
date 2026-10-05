// `/onboarding/{version_id}` — P4, el revisor de cuatro paneles de una lista
// importada.
//
// Las cuatro regiones, lado a lado:
//   (1) el PDF crudo, embebido desde `/api/listas/{id}/documento` (la URL del
//       backend no llega al navegador);
//   (2) lo que leyó el modelo, por página, desde `percepcion()`;
//   (3) los renglones itemizados de `revisionLista()`, con su concepto ya
//       emparejado, sus candidatos/confianza (las `propuestas`) y —por línea—
//       los controles ADD + EDIT y el de adquisición directa del colegio
//       (sin borrado duro), WIRED a `editarItemLista`/`agregarItemLista`;
//   (4) previsualizar los tres kits (`previewDeVersion` → un trabajo de preview
//       que se abre en la consola de revisión de siempre, `/trabajos/{id}`) Y
//       aprobar y publicar (`cerrarLista(version_id)`). Previsualizar NO aprueba:
//       son dos acciones distintas —y el preview NO se puede publicar (no tiene
//       acudiente): publicar es aprobar la LISTA, que crea el colegio y arma el
//       trabajo del padre.
//
// Server Component para leer: `revisionLista()` y `percepcion()` salen del origen
// directamente. Un 404 (`version_no_existe`/`sin_evidencia`) se traduce a
// `notFound()`.
//
// NOTA DE CONTRATO: `previewDeVersion(versionId, {colegioId, grado, anioLectivo})`
// arma, sobre una versión curada, un `TrabajoAdmin` de preview (`{trabajo_id}`) sin
// crear un trabajo de acudiente; la región 4 navega a él en la consola de revisión.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { DatosColegioNuevo, PercepcionCruda, RevisionLista } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { OpcionConcepto } from "@/components/PanelReclasificar";
import ItemsPercibidos from "@/components/ItemsPercibidos";
import { vocabularioDeConceptos, type VocabularioConceptos } from "@/lib/vocabulario-conceptos";
import AprobarLista from "@/components/AprobarLista";
import CompletarColegio from "@/components/CompletarColegio";
import PrevisualizarKits from "./PrevisualizarKits";
import styles from "../Onboarding.module.css";

export const dynamic = "force-dynamic";

// Quita las claves null/vacías de un bloque para que, al fusionar el DUEB por
// debajo (`{...dueb, ...limpiarVacios(guardado)}`), el pre-llenado solo cubra
// los huecos y jamás pise un dato que el revisor ya escribió.
function limpiarVacios(obj: DatosColegioNuevo): Partial<DatosColegioNuevo> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== ""),
  ) as Partial<DatosColegioNuevo>;
}

interface Props {
  params: Promise<{ version_id: string }>;
}

export default async function PaginaRevisionLista({ params }: Props) {
  const { version_id } = await params;

  const origen = origenDeDatos();

  let revision: RevisionLista;
  let percepcion: PercepcionCruda;
  let conceptos: OpcionConcepto[] = [];
  let vocabulario: VocabularioConceptos = { atributos: [], categorias: [] };
  try {
    // La revisión es la fuente de las regiones 3/4; la percepción cruda es la
    // evidencia por página de la región 2; el catálogo puebla el selector de
    // concepto de la región 3. Los tres cuelgan de la misma versión/origen.
    const [rev, perc, catalogo] = await Promise.all([
      origen.revisionLista(version_id),
      origen.percepcion(version_id),
      origen.catalogo(),
    ]);
    revision = rev;
    percepcion = perc;
    conceptos = catalogo.conceptos
      .map((c) => ({ codigo: c.codigo, nombre: c.nombre_canonico }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
    vocabulario = vocabularioDeConceptos(catalogo.conceptos);
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) notFound();
    throw causa;
  }

  // Pre-llenar el perfil del colegio nuevo con el bloque DUEB: la subida a veces
  // solo dejó el nombre. Se trae por DANE y se rellenan SOLO los campos vacíos
  // (lo que el revisor ya guardó manda). null = el DANE no está en el directorio.
  if (revision.colegio_datos?.dane) {
    const dueb = await origen.directorioColegio(revision.colegio_datos.dane);
    if (dueb) revision.colegio_datos = { ...dueb, ...limpiarVacios(revision.colegio_datos) };
  }

  const urlDocumento = `/api/listas/${encodeURIComponent(version_id)}/documento`;

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href="/cola">← Cola de verificación</Link>
      </nav>

      <header className={styles.encabezado}>
        <div>
          <h1>
            Revisión de {revision.colegio_datos?.nombre ?? "Colegio por identificar"} ·{" "}
            {revision.grado}
          </h1>
          <p className={styles.bajada}>
            Versión <span className="cifra">{revision.numero}</span> · año{" "}
            <span className="cifra">{revision.anio_lectivo}</span>. Coteja lo que leyó el modelo
            contra el PDF, corrige los ítems y aprueba. Aprobar deja el par (colegio, grado)
            disponible para los acudientes.
          </p>
        </div>
      </header>

      <div className={styles.regiones}>
        {/* ------------------------------------------------ Región 1: el PDF */}
        <section className={styles.region}>
          <div className={styles.regionCabecera}>
            <span className={styles.regionNumero}>1</span>
            <h2>El PDF original</h2>
          </div>
          <iframe className={styles.marco} src={urlDocumento} title="PDF de la lista" />
        </section>

        {/* --------------------------------- Región 2: percepción cruda */}
        <section className={styles.region}>
          <div className={styles.regionCabecera}>
            <span className={styles.regionNumero}>2</span>
            <h2>Lo que leyó el modelo</h2>
          </div>
          <div className={styles.crudo}>
            {percepcion.paginas.length === 0 ? (
              <p className={styles.pendienteContrato}>El modelo no dejó texto crudo por página.</p>
            ) : (
              percepcion.paginas.map((pagina) => (
                <div key={pagina.pagina} className={styles.crudoPagina}>
                  <h3>Página {pagina.pagina}</h3>
                  <p className={styles.crudoTexto}>{pagina.crudo}</p>
                </div>
              ))
            )}
          </div>
        </section>

        {/* --------------------------- Región 3: ítems + concepto + edición */}
        <section className={styles.region}>
          <div className={styles.regionCabecera}>
            <span className={styles.regionNumero}>3</span>
            <h2>Coincidencias y edición</h2>
          </div>
          <ItemsPercibidos
            versionId={version_id}
            revisada={revision.revisada}
            items={revision.items}
            propuestas={revision.propuestas}
            conceptos={conceptos}
            vocabulario={vocabulario}
          />
        </section>

        {/* ------------- Colegio nuevo por crear (solo si lo subió un padre).
            Sin `regionAncha`: cae en la celda libre al lado de la región 3 en vez
            de dejar un hueco. Va justo tras la región 3 para quedar a su derecha. */}
        {revision.colegio_datos ? (
          <section className={styles.region}>
            <div className={styles.regionCabecera}>
              <span className={styles.regionNumero}>·</span>
              <h2>Identidad del colegio nuevo</h2>
            </div>
            <CompletarColegio
              versionId={version_id}
              datos={revision.colegio_datos}
              revisada={revision.revisada}
            />
          </section>
        ) : null}

        {/* ------------------------------- Región 4: aprobar y publicar */}
        <section className={`${styles.region} ${styles.regionAncha}`}>
          <div className={styles.regionCabecera}>
            <span className={styles.regionNumero}>4</span>
            <h2>Aprobar y publicar</h2>
          </div>
          <p className={styles.bajada}>
            Aprobar deja la versión revisada y el par (colegio, grado) disponible para los
            acudientes, y arma solo sus kits canónicos (Ahorrador y Premium) en segundo plano.
            Si quieres revisarlos o ajustarlos antes, previsualízalos primero y apruébalos desde la
            consola: esos, con tus ajustes, quedan como los canónicos.
          </p>
          <PrevisualizarKits
            versionId={version_id}
            colegioId={revision.colegio_id}
            grado={revision.grado}
            anioLectivo={revision.anio_lectivo}
          />
          <AprobarLista
            versionId={version_id}
            colegioId={revision.colegio_id}
            grado={revision.grado}
            revisada={revision.revisada}
          />
        </section>
      </div>
    </div>
  );
}
