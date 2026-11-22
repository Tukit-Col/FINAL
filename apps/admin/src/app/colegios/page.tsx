import { logoDeColegio } from "@tukit/contrato";
import { origenDeDatos } from "@tukit/contrato/servidor";
import TarjetaColegio from "@/components/TarjetaColegio";
import { imagenesDelDirectorio } from "@/lib/directorio";
import styles from "./Colegios.module.css";

export const dynamic = "force-dynamic";

export default async function PaginaColegios() {
  const colegios = await origenDeDatos().colegios();

  const aliados = colegios
    .filter((c) => c.es_partner ?? c.grados.length > 0)
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <div>
          <h1>Colegios y listas</h1>
          <p className={styles.bajada}>
            La base durable de colegios. Un colegio se vuelve aliado en cuanto tiene su primer
            grado revisado; hasta entonces no aparece en el selector del acudiente.
          </p>
        </div>
        <dl className={styles.resumen}>
          <div>
            <dt>Aliados</dt>
            <dd className="cifra">{aliados.length}</dd>
          </div>
        </dl>
      </header>

      {aliados.length === 0 ? (
        <p className={styles.vacio}>Todavía no hay colegios aliados.</p>
      ) : (
        <div className={styles.rejilla}>
          {aliados.map((colegio) => (
            <TarjetaColegio
              key={colegio.colegio_id}
              colegio={colegio}
              logo={logoDeColegio(colegio, imagenesDelDirectorio())}
            />
          ))}
        </div>
      )}
    </div>
  );
}
