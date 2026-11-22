// `/onboarding/{version_id}`: el revisor de cuatro paneles de una lista importada.
//
// Decisiones:
// - Cuatro regiones lado a lado: el PDF crudo, lo que leyó el modelo por página, los renglones
//   itemizados con su concepto y sus candidatos, y la previsualización y aprobación de los tres kits.
// - Previsualizar no aprueba: son dos acciones distintas, y el preview no se puede publicar.

import Link from "next/link";
import { notFound } from "next/navigation";
import type { DatosColegioNuevo, PercepcionCruda, RevisionLista } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { OpcionConcepto } from "@/components/PanelReclasificar";
import ItemsPercibidos from "@/components/ItemsPercibidos";
import { vocabularioDeConceptos, type VocabularioConceptos } from "@/lib/vocabulario-conceptos";
import { valoresDeProductos } from "@/lib/atributos-renglon";
import AprobarLista from "@/components/AprobarLista";
import CompletarColegio from "@/components/CompletarColegio";
import PrevisualizarKits from "./PrevisualizarKits";
import styles from "../Onboarding.module.css";

export const dynamic = "force-dynamic";

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
  let valoresAtributos: Record<string, Record<string, string[]>> = {};
  try {
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
    const usados = new Set(rev.items.map((i) => i.concepto_codigo).filter(Boolean));
    valoresAtributos = valoresDeProductos(catalogo.conceptos.filter((c) => usados.has(c.codigo)));
  } catch (causa) {
    if (causa instanceof ErrorTukit && causa.estado === 404) notFound();
    throw causa;
  }

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
        <section className={styles.region}>
          <div className={styles.regionCabecera}>
            <span className={styles.regionNumero}>1</span>
            <h2>El PDF original</h2>
          </div>
          <iframe className={styles.marco} src={urlDocumento} title="PDF de la lista" />
        </section>

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
            valoresAtributos={valoresAtributos}
          />
        </section>

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
