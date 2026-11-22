import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import type {
  AvisoLista,
  ColegioDetalle,
  DirectorioColegio,
  ItemListaOficial,
  Kit,
  ListaOficial,
  PedidosPorGrado,
  ResumenPedidosColegio,
} from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import AvisosLista from "@/components/AvisosLista";
import EditarKits from "@/components/EditarKits";
import EditarLista from "@/components/EditarLista";
import KitsCanonicos from "./KitsCanonicos";
import { formatearFecha } from "@/lib/formato";
import { COOKIE_SESION } from "@/lib/sesion";
import styles from "../../Colegios.module.css";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ colegio: string; grado: string }>;
}

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
    <li className={styles.renglon} id={`renglon-${item.orden}`}>
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

  let kitsCanonicos: Kit[] = [];
  const canonico = (await origenDeDatos().gradosCanonicos(lista.colegio_id).catch(() => [])).find(
    (g) => g.grado === lista.grado,
  );
  if (canonico) {
    try {
      const trabajo = await origenDeDatos().trabajoAdmin(canonico.trabajo_id);
      kitsCanonicos = trabajo.kits;
    } catch (causa) {
      console.error("no se pudo leer el trabajo canónico", causa);
    }
  }

  let tipoDocumento: string | null = null;
  if (lista.version_id) {
    try {
      const blob = await origenDeDatos().documento(lista.version_id);
      tipoDocumento = blob instanceof Blob && blob.type ? blob.type : "application/pdf";
    } catch (causa) {
      if (causa instanceof ErrorTukit && causa.estado === 404) tipoDocumento = null;
      else tipoDocumento = "application/pdf";
    }
  }

  let avisos: AvisoLista[] = [];
  if (lista.version_id) {
    avisos = await origenDeDatos()
      .avisosLista(lista.version_id)
      .catch((causa) => {
        console.error("no se pudieron leer los avisos de la lista", causa);
        return [];
      });
  }

  const urlDocumento = lista.version_id
    ? `/api/listas/${encodeURIComponent(lista.version_id)}/documento`
    : null;

  const origen = origenDeDatos();
  let colegio: ColegioDetalle | null = null;
  try {
    colegio = await origen.colegio(colegioId);
  } catch (causa) {
    if (!(causa instanceof ErrorTukit && causa.estado === 404)) throw causa;
  }
  const directorio: DirectorioColegio | null = colegio?.dane
    ? await origen.directorioCompleto(colegio.dane)
    : null;
  const nombreColegio = directorio?.nombre ?? colegio?.nombre ?? null;

  const token = (await cookies()).get(COOKIE_SESION)?.value;

  let resumenPedidos: ResumenPedidosColegio | null = null;
  let pedidosCargados = true;
  if (token) {
    try {
      resumenPedidos = await origen.resumenPedidosColegio(token, colegioId);
    } catch (causa) {
      if (causa instanceof ErrorTukit && (causa.estado === 401 || causa.estado === 403)) {
        pedidosCargados = false;
      } else {
        throw causa;
      }
    }
  } else {
    pedidosCargados = false;
  }

  const filaGrado: PedidosPorGrado | undefined = resumenPedidos?.por_grado.find(
    (g) => g.grado === grado,
  );
  const padresGrado = filaGrado?.por_padre ?? [];

  const correos = new Map<string, string>();
  let correosCargados = true;
  if (padresGrado.length > 0) {
    if (!token) {
      correosCargados = false;
    } else {
      try {
        const acudientes = await origen.acudientesAdmin(
          token,
          padresGrado.map((p) => p.usuario_id),
        );
        for (const a of acudientes) correos.set(a.usuario_id, a.correo);
      } catch (causa) {
        if (causa instanceof ErrorTukit && (causa.estado === 401 || causa.estado === 403)) {
          correosCargados = false;
        } else {
          throw causa;
        }
      }
    }
  }

  return (
    <div className={styles.pagina}>
      <nav className={styles.migas}>
        <Link href={`/colegios/${encodeURIComponent(colegioId)}`}>← Perfil del colegio</Link>
      </nav>

      <header className={styles.encabezado}>
        <div>
          <h1>
            {lista.grado} · {nombreColegio ?? <code>{lista.colegio_id}</code>}
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

      {lista.version_id ? <AvisosLista versionId={lista.version_id} avisos={avisos} /> : null}

      <div className={styles.paneles}>
        <section className={styles.panel}>
          <div className={styles.panelCabecera}>
            <h2>Documento original</h2>
          </div>
          {urlDocumento && tipoDocumento ? (
            tipoDocumento.startsWith("image/") ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className={styles.imagenDocumento}
                src={urlDocumento}
                alt="Documento original de la lista"
              />
            ) : (
              <iframe
                className={styles.marcoPdf}
                src={urlDocumento}
                title="Documento original de la lista"
              />
            )
          ) : (
            <p className={styles.pendienteContrato}>
              Esta lista no tiene documento original: se cargó desde los datos del sistema
            </p>
          )}
        </section>

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

      {canonico && kitsCanonicos.length > 0 && (
        <section className={styles.panel}>
          <div className={styles.panelCabecera}>
            <div>
              <h2>Kits NSGA aprobados</h2>
              <span className={styles.panelConteo}>
                caché del acudiente
                {canonico.publicado_en ? ` · versión publicada el ${formatearFecha(canonico.publicado_en)}` : ""}
              </span>
            </div>
            <EditarKits
              canonicoId={canonico.trabajo_id}
              borradorId={canonico.borrador_trabajo_id ?? null}
            />
          </div>
          <KitsCanonicos trabajoId={canonico.trabajo_id} kits={kitsCanonicos} />
        </section>
      )}

      <section className={styles.tarjeta}>
        <h2 className={styles.subtitulo}>Padres con pedido pagado</h2>
        {!pedidosCargados ? (
          <p className={styles.avisoCorreos}>
            No pudimos cargar los pedidos pagados (falta sesión o rol de operador/admin).
          </p>
        ) : padresGrado.length === 0 ? (
          <p className={styles.vacio}>
            Todavía no hay pedidos pagados de este colegio en este grado.
          </p>
        ) : (
          <>
            {!correosCargados ? (
              <p className={styles.avisoCorreos}>
                No pudimos cargar los correos (falta sesión o rol de operador/admin). Se muestran
                los identificadores.
              </p>
            ) : null}
            <div className={styles.tablaMarco}>
            <table className={styles.tabla}>
              <thead>
                <tr>
                  <th scope="col">Padre</th>
                  <th scope="col">Niños en {lista.grado}</th>
                </tr>
              </thead>
              <tbody>
                {padresGrado.map((p) => (
                  <tr key={p.usuario_id}>
                    <th scope="row" className={styles.celdaDato}>
                      {correos.get(p.usuario_id) ?? p.usuario_id}
                    </th>
                    <td className="cifra">{p.ninos}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
