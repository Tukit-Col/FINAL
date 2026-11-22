import {
  BookOpen,
  Shirt,
  CircleAlert,
  ExternalLink,
  House,
  School,
  ShoppingBag,
  type LucideIcon,
} from "lucide-react";
import {
  clasificar,
  dondeComprar,
  estadoDePrecio,
  razonDeNoCobrar,
  type LineaKit,
  type Kit,
} from "@tukit/contrato";
import {
  ABSTENCIONES,
  agruparPorCategoria,
  idAnclaCategoria,
  gruposFueraDelCarrito,
  type GrupoFueraDelCarrito,
} from "@/lib/kit-vista";
import LineaDeKit from "./LineaDeKit";
import CabeceraCategoria from "./CabeceraCategoria";
import styles from "./Kits.module.css";

function RenglonFuera({ linea, nombreHijo }: { linea: LineaKit; nombreHijo?: string }) {
  const producto = linea.producto_elegido;
  const donde = dondeComprar(linea);
  const razon = razonDeNoCobrar(linea);
  const precio = estadoDePrecio(linea);
  const detalle = [donde, linea.edicion?.titulo ? `edición ${linea.edicion.titulo}` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <li className={styles.renglonFuera}>
      {producto?.imagen_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img className={styles.fotoFuera} src={producto.imagen_url} alt="" loading="lazy" />
      )}
      <div className={styles.textoFuera}>
        <p className={styles.nombreFuera}>
          {linea.descripcion}
          {nombreHijo && <span className={styles.hijo}>{nombreHijo}</span>}
        </p>
        {(detalle || razon) && (
          <p className={styles.notaFuera}>
            {detalle || (precio.tipo === "sin_cobro" ? precio.titulo : razon)}
          </p>
        )}
      </div>
      {linea.url_externa && (
        <a className={styles.enlaceFuera} href={linea.url_externa} target="_blank" rel="noopener noreferrer">
          Cómo comprarlo <ExternalLink size={14} aria-hidden="true" />
        </a>
      )}
    </li>
  );
}

export default function SeccionesDeLineas({
  kit,
  trabajoId,
  nombresHijos,
}: {
  kit: Kit;
  trabajoId: string;
  nombresHijos: Map<string, string>;
}) {
  const abstenciones = kit.lineas.filter((l) => ABSTENCIONES.includes(clasificar(l)));
  const carrito = kit.lineas
    .filter((l) => clasificar(l) === "comprable")
    .sort((a, b) => Number(a.descartado === true) - Number(b.descartado === true));
  const enCarrito = carrito.filter((l) => !l.descartado).length;
  const fuera = gruposFueraDelCarrito(kit.lineas);
  const totalFuera = fuera.reduce((n, g) => n + g.lineas.length, 0);

  const renglon = (linea: LineaKit) => (
    <LineaDeKit
      key={linea.item_id}
      linea={linea}
      clase={clasificar(linea)}
      nombreHijo={linea.hijo ? nombresHijos.get(linea.hijo) : undefined}
      trabajoId={trabajoId}
      perfil={kit.perfil}
    />
  );

  return (
    <div className={styles.secciones}>
      {abstenciones.length > 0 && (
        <section className={`${styles.seccion} ${styles.seccion_hueco}`}>
          <header className={styles.cabeceraSeccion}>
            <h2>
              <CircleAlert size={20} aria-hidden="true" /> Revisa estos{" "}
              <span className={`${styles.conteo} cifra`}>{abstenciones.length}</span>
            </h2>
            <p>
              No los pudimos resolver y preferimos decírtelo a ofrecerte algo parecido como si fuera
              lo mismo.
            </p>
          </header>
          <ul className={styles.lineas}>{abstenciones.map(renglon)}</ul>
        </section>
      )}

      {carrito.length > 0 && (
        <section className={styles.seccion}>
          <header className={styles.cabeceraSeccion}>
            <h2>
              En tu carrito <span className={`${styles.conteo} cifra`}>{enCarrito}</span>
            </h2>
            <p>Puedes cambiar cualquier producto por otra opción o quitar lo que ya tienes.</p>
          </header>
          {agruparPorCategoria(carrito).map((grupo) => (
            <section
              key={grupo.categoria}
              id={idAnclaCategoria(grupo.categoria)}
              className={styles.grupoCategoria}
              data-categoria={grupo.categoria}
              aria-labelledby={`${idAnclaCategoria(grupo.categoria)}-titulo`}
            >
              <CabeceraCategoria
                titulo={grupo.titulo}
                categoria={grupo.categoria}
                lineas={grupo.lineas}
                trabajoId={trabajoId}
                perfil={kit.perfil}
              />
              <ul className={styles.lineas}>{grupo.lineas.map(renglon)}</ul>
            </section>
          ))}
        </section>
      )}

      {totalFuera > 0 && (
        <section className={`${styles.seccion} ${styles.fueraCarrito}`}>
          <header className={styles.cabeceraSeccion}>
            <h2>
              Fuera del carrito <span className={`${styles.conteo} cifra`}>{totalFuera}</span>
            </h2>
            <p>
              También están en la lista, pero no se compran en Tukit. Te decimos qué hacer con cada
              uno; no suman al total.
            </p>
          </header>
          {fuera.map(({ clave, titulo, lineas }) => {
            const Icono = ICONO_GRUPO_FUERA[clave];
            return (
              <div key={clave} className={styles.grupoFuera}>
                <h3>
                  <Icono size={16} aria-hidden="true" /> {titulo}
                </h3>
                <ul>
                  {lineas.map((l) => (
                    <RenglonFuera
                      key={l.item_id}
                      linea={l}
                      nombreHijo={l.hijo ? nombresHijos.get(l.hijo) : undefined}
                    />
                  ))}
                </ul>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}

const ICONO_GRUPO_FUERA: Record<GrupoFueraDelCarrito["clave"], LucideIcon> = {
  libros: BookOpen,
  colegio: School,
  uniformes: Shirt,
  cuenta: ShoppingBag,
  casa: House,
};
