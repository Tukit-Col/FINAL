import estilos from "./Kits.module.css";

// Estado de carga mientras el servidor trae el trabajo: esqueleto con la forma
// de la pagina (titulo, selector, tarjeta del kit y primeros renglones) para
// que no salte el layout al llegar. Sin datos ni logica: solo presentacion.
export default function CargandoKits() {
  return (
    <div className={estilos.pagina} role="status" aria-busy="true">
      <span className={estilos.visualmenteOculto}>Cargando tus kits…</span>
      <div aria-hidden="true">
        <span className={estilos.esqueletoLinea} style={{ width: "min(420px, 70%)", height: 34 }} />
        <span className={estilos.esqueletoLinea} style={{ width: "min(520px, 90%)", marginTop: 12 }} />
        <span className={estilos.esqueletoLinea} style={{ width: "100%", height: 150, marginTop: 28, borderRadius: 28 }} />
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={estilos.esqueletoLinea}
            style={{ width: "100%", height: 88, marginTop: 16, borderRadius: 22 }}
          />
        ))}
      </div>
    </div>
  );
}
