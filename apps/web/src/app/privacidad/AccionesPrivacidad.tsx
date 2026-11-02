"use client";

// Las tres acciones del titular: descargar su copia, retirar su autorizacion y
// borrar sus datos. Borrar pide escribir la frase: el boton no se habilita hasta
// que la frase coincide (la misma regla que aplica Identidad, que es quien
// decide). Al terminar, la cookie ya se borro en el Route Handler y se muestra
// que se borro y que se guardo, con su fundamento.

import { useState } from "react";
import { Download, ShieldOff, Trash2 } from "lucide-react";
import {
  confirmacionDeSupresionValida,
  type DatoConservado,
  type DatoSuprimido,
  type ResultadoSupresion,
} from "@tukit/contrato";
import { FalloApi, revocarConsentimientos, suprimirMisDatos } from "@/lib/api-navegador";
import dashboard from "../dashboard/Dashboard.module.css";
import styles from "./Privacidad.module.css";

interface Props {
  frase: string;
  suprimido: DatoSuprimido[];
  conservado: DatoConservado[];
  autorizacionesVigentes: number;
}

export default function AccionesPrivacidad({ frase, suprimido, conservado, autorizacionesVigentes }: Props) {
  const [vigentes, setVigentes] = useState(autorizacionesVigentes);
  const [revocando, setRevocando] = useState(false);
  const [confirmandoRevocar, setConfirmandoRevocar] = useState(false);
  const [errorRevocar, setErrorRevocar] = useState<string | null>(null);

  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoSupresion | null>(null);

  async function revocar() {
    setRevocando(true);
    setErrorRevocar(null);
    try {
      await revocarConsentimientos();
      setVigentes(0);
      setConfirmandoRevocar(false);
    } catch (causa) {
      setErrorRevocar(causa instanceof FalloApi ? causa.message : "No pudimos revocar tu autorización.");
    } finally {
      setRevocando(false);
    }
  }

  async function borrar() {
    setBorrando(true);
    setError(null);
    try {
      setResultado(await suprimirMisDatos(texto));
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos borrar tus datos. Intenta de nuevo.");
      setBorrando(false);
    }
  }

  if (resultado) {
    return (
      <section className={dashboard.card} role="status">
        <div className={dashboard.sectionHeader}>
          <h2>Tus datos fueron borrados</h2>
        </div>
        <div className={styles.cuerpo}>
          <p>{resultado.mensaje}</p>
          <p>
            Tu sesión se cerró. Si vuelves a usar Tukit con el mismo correo, empezarás con una cuenta nueva y
            vacía.
          </p>
          {resultado.pedidos_conservados !== null && resultado.pedidos_conservados > 0 && (
            <p>
              Guardamos {resultado.pedidos_conservados}{" "}
              {resultado.pedidos_conservados === 1 ? "pedido" : "pedidos"} sin tu nombre ni tu correo, por lo
              que explicamos abajo.
            </p>
          )}
          <ListaConservado conservado={resultado.conservado} />
          <a href="/" className={dashboard.btnContactar}>
            Volver al inicio
          </a>
        </div>
      </section>
    );
  }

  const fraseLista = confirmacionDeSupresionValida(texto);

  return (
    <>
      <section id="descargar" className={dashboard.card}>
        <div className={dashboard.sectionHeader}>
          <h2>Descargar mis datos</h2>
        </div>
        <div className={styles.cuerpo}>
          <p>
            Te damos un archivo con todo lo que guardamos de ti: cuenta, hijos, direcciones completas,
            autorizaciones y la lista de tus pedidos, casos y solicitudes.
          </p>
          <a href="/api/cuenta/mis-datos/exportar" download className={dashboard.btnContactar}>
            <Download size={15} aria-hidden /> Descargar mis datos
          </a>
        </div>
      </section>

      <section id="revocar" className={dashboard.card}>
        <div className={dashboard.sectionHeader}>
          <h2>Retirar mi autorización</h2>
        </div>
        <div className={styles.cuerpo}>
          {vigentes === 0 ? (
            <p>No tienes autorizaciones vigentes.</p>
          ) : (
            <>
              <p>
                Puedes retirar la autorización que nos diste para tratar tus datos sin borrar tu cuenta. Tus
                pedidos en curso se siguen atendiendo.
              </p>
              {!confirmandoRevocar ? (
                <button
                  type="button"
                  className={`${dashboard.accionDiscreta} ${dashboard.accionDiscretaPeligro}`}
                  onClick={() => setConfirmandoRevocar(true)}
                >
                  <ShieldOff size={13} aria-hidden /> Retirar mi autorización
                </button>
              ) : (
                <div className={dashboard.confirmacion} role="alertdialog" aria-label="Retirar autorización">
                  <p>¿Retirar tu autorización? Quedará registrada la fecha de hoy.</p>
                  <div className={dashboard.hijoAcciones}>
                    <button
                      type="button"
                      className={dashboard.btnPeligro}
                      disabled={revocando}
                      onClick={() => void revocar()}
                    >
                      {revocando ? "Retirando…" : "Sí, retirar"}
                    </button>
                    <button
                      type="button"
                      className={dashboard.btnCancelar}
                      disabled={revocando}
                      onClick={() => setConfirmandoRevocar(false)}
                    >
                      No
                    </button>
                  </div>
                  {errorRevocar && (
                    <span className={dashboard.errorPedido} role="alert">
                      {errorRevocar}
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </section>

      <section id="borrar" className={`${dashboard.card} ${styles.peligro}`}>
        <div className={dashboard.sectionHeader}>
          <h2>Borrar mis datos</h2>
        </div>
        <div className={styles.cuerpo}>
          <p>
            Esto no se puede deshacer. Cerramos tu cuenta y borramos tus datos personales. Lo que la ley nos
            obliga a guardar queda sin tu nombre, tu correo ni tu celular.
          </p>
          {!abierto ? (
            <button type="button" className={dashboard.btnPeligro} onClick={() => setAbierto(true)}>
              <Trash2 size={14} aria-hidden /> Quiero borrar mis datos
            </button>
          ) : (
            <div className={styles.flujo}>
              <h3>Lo que borramos</h3>
              <ul className={styles.items}>
                {suprimido.map((s) => (
                  <li key={s.dato}>{s.detalle}</li>
                ))}
              </ul>
              <h3>Lo que guardamos y por qué</h3>
              <ListaConservado conservado={conservado} />
              <label className={styles.campo}>
                <span>
                  Para confirmar, escribe <strong>{frase}</strong>
                </span>
                <input
                  type="text"
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  aria-describedby="aviso-borrar"
                />
              </label>
              <p id="aviso-borrar" className={styles.nota}>
                Al confirmar, se cierra tu sesión en todos tus dispositivos.
              </p>
              <div className={dashboard.hijoAcciones}>
                <button
                  type="button"
                  className={dashboard.btnPeligro}
                  disabled={!fraseLista || borrando}
                  onClick={() => void borrar()}
                >
                  {borrando ? "Borrando…" : "Borrar mis datos"}
                </button>
                <button
                  type="button"
                  className={dashboard.btnCancelar}
                  disabled={borrando}
                  onClick={() => {
                    setAbierto(false);
                    setTexto("");
                    setError(null);
                  }}
                >
                  Cancelar
                </button>
              </div>
              {error && (
                <span className={dashboard.errorPedido} role="alert">
                  {error}
                </span>
              )}
            </div>
          )}
        </div>
      </section>
    </>
  );
}

function ListaConservado({ conservado }: { conservado: DatoConservado[] }) {
  return (
    <ul className={styles.items}>
      {conservado.map((c) => (
        <li key={c.dato}>
          {c.detalle}
          <span className={styles.fundamento}>{c.fundamento}</span>
        </li>
      ))}
    </ul>
  );
}
