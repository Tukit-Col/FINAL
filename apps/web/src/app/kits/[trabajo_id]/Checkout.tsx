import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { prefiereMenosMovimiento } from "@tukit/contrato/motion";
import { formatearPesos, hayQueCobrar, LOCALIDADES_BOGOTA, type PerfilKit } from "@tukit/contrato";
import { FalloApi, iniciarCheckout } from "@/lib/api-navegador";
import {
  aplicarLugarElegido,
  entregaDeCheckout,
  escribirDireccionAMano,
} from "@/lib/direccion-checkout";
import type { EntregaPrevia } from "@/lib/pagar-pedido";
import { abrirWidgetWompi } from "@/lib/wompi";
import CampoDireccionOsm, { type LugarElegido } from "./CampoDireccionOsm";
import styles from "./Kits.module.css";

const CIUDAD_ENTREGA = "Bogotá";

export default function Checkout({
  trabajoId,
  perfil,
  total,
  correo,
  entregaPrevia,
  abrirPago,
}: {
  trabajoId: string;
  perfil: PerfilKit;
  total: number;
  correo: string;
  entregaPrevia: EntregaPrevia | null;
  abrirPago: boolean;
}) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(abrirPago);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datos, setDatos] = useState({
    destinatario: "",
    direccion: "",
    indicaciones: "",
    localidad: "",
    departamento: "",
    latitud: null as number | null,
    longitud: null as number | null,
    ...entregaPrevia,
    ciudad: CIUDAD_ENTREGA,
    correo,
  });
  const formRef = useRef<HTMLFormElement>(null);
  const primerCampoRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!abierto) return;
    formRef.current?.scrollIntoView({
      behavior: prefiereMenosMovimiento() ? "auto" : "smooth",
      block: "start",
    });
    primerCampoRef.current?.focus({ preventScroll: true });
  }, [abierto]);

  const cambiar =
    (campo: Exclude<keyof typeof datos, "ciudad" | "latitud" | "longitud">) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setDatos((d) => ({ ...d, [campo]: e.target.value }));

  const escribirDireccion = (direccion: string) =>
    setDatos((d) => escribirDireccionAMano(d, direccion));

  const elegirLugar = (lugar: LugarElegido) => setDatos((d) => aplicarLugarElegido(d, lugar));

  const moverPin = (latitud: number, longitud: number) =>
    setDatos((d) => ({ ...d, latitud, longitud }));

  async function pagar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const { correo } = datos;
      const checkout = await iniciarCheckout(trabajoId, {
        perfil,
        correo,
        entrega: entregaDeCheckout(datos),
        url_redireccion: `${window.location.origin}/pago/resultado`,
      });
      if (checkout.widget) {
        await abrirWidgetWompi(checkout.widget, (transaccionId) => {
          router.push(`/pago/resultado?id=${encodeURIComponent(transaccionId)}`);
        });
        setEnviando(false);
      } else if (checkout.url_redireccion) {
        window.location.href = checkout.url_redireccion;
      } else {
        setError("No pudimos abrir la pasarela de pago.");
        setEnviando(false);
      }
    } catch (causa) {
      const mensaje =
        causa instanceof FalloApi
          ? causa.message
          : "No pudimos iniciar el pago. Intenta de nuevo.";
      setError(mensaje);
      setEnviando(false);
    }
  }

  return (
    <>
      <p className={styles.notaTotalKit}>
        El total incluye solo lo que está en tu carrito. Lo de la sección «Fuera
        del carrito» no entra en esta cifra.
      </p>
      <footer className={styles.pie}>
        <div>
          <span className={styles.etiquetaTotal}>Total del kit {perfil}</span>
          <span className={`${styles.totalPie} cifra`}>
            {hayQueCobrar(total) ? formatearPesos(total) : "Sin productos con precio"}
          </span>
        </div>
        {!abierto && (
          <button
            type="button"
            className={styles.pagar}
            disabled={!hayQueCobrar(total)}
            onClick={() => setAbierto(true)}
          >
            Ir a pagar
          </button>
        )}
      </footer>

      {abierto && (
        <form ref={formRef} className={styles.formPago} onSubmit={pagar}>
          <p className={styles.tituloPago}>¿A dónde te lo llevamos?</p>
          <p className={styles.totalAntesDePagar}>
            Vas a pagar <strong className="cifra">{formatearPesos(total)}</strong> por el kit {perfil}.
          </p>
          <label>
            Nombre de quien recibe
            <input
              ref={primerCampoRef}
              value={datos.destinatario}
              onChange={cambiar("destinatario")}
              required
            />
          </label>
          <CampoDireccionOsm
            valor={datos.direccion}
            latitud={datos.latitud}
            longitud={datos.longitud}
            onEscribir={escribirDireccion}
            onElegir={elegirLugar}
            onMoverPin={moverPin}
          />
          <label>
            Apto, torre, conjunto, referencias (opcional)
            <input
              value={datos.indicaciones}
              onChange={cambiar("indicaciones")}
              maxLength={120}
              autoComplete="address-line2"
            />
          </label>
          <div className={styles.filaPago}>
            <label>
              Ciudad
              <input value={datos.ciudad} readOnly aria-describedby="ciudad-fija" autoComplete="address-level2" />
            </label>
            <label>
              Localidad
              <select value={datos.localidad} onChange={cambiar("localidad")} required>
                <option value="">Elige la localidad</option>
                {LOCALIDADES_BOGOTA.map((localidad) => (
                  <option key={localidad} value={localidad}>
                    {localidad}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p id="ciudad-fija" className={styles.ciudadFija}>
            Por ahora entregamos solo en Bogotá.
          </p>
          <label>
            Departamento (opcional)
            <input
              value={datos.departamento}
              onChange={cambiar("departamento")}
              maxLength={128}
              autoComplete="address-level1"
            />
          </label>
          {correo ? (
            <p className={styles.notaTotal}>
              El comprobante va a <strong>{correo}</strong>.
            </p>
          ) : (
            <label>
              Correo para el comprobante
              <input type="email" value={datos.correo} onChange={cambiar("correo")} required />
            </label>
          )}
          {error && <p className={styles.errorPago}>{error}</p>}
          <p className={styles.avisoLegal}>
            Al pagar aceptas los <Link href="/legal/terminos">términos y condiciones</Link>, la{" "}
            <Link href="/legal/privacidad">política de datos personales</Link> y conoces tu{" "}
            <Link href="/legal/retracto">derecho de retracto y garantía</Link>.
          </p>
          <button type="submit" className={styles.pagar} disabled={enviando || !hayQueCobrar(total)}>
            {enviando ? "Llevándote a la pasarela…" : `Pagar ${formatearPesos(total)}`}
          </button>
        </form>
      )}

      <p className={styles.notaPago}>
        Al confirmar, el precio se congela y no se mueve. Pagas en la pasarela segura;
        Tukit nunca ve los datos de tu tarjeta.
      </p>
    </>
  );
}
