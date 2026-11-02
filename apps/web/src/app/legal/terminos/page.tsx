import Link from "next/link";
import DocumentoLegal, { Dato } from "../DocumentoLegal";
import { RESPONSABLE } from "../datos-legales";

export const metadata = { title: "Términos y condiciones | Tukit" };

export default function PaginaTerminos() {
  return (
    <DocumentoLegal
      titulo="Términos y condiciones"
      resumen="Las reglas de uso de Tukit y de tus compras, para que sepas qué esperar antes de pagar."
    >
      <h2>1. Quiénes somos</h2>
      <p>
        Tukit es {RESPONSABLE.naturaleza}, con domicilio en <Dato valor={RESPONSABLE.domicilio} />. Es un
        servicio que arma el kit escolar de
        tus hijos a partir de la lista de útiles de su colegio y te lo vende en un solo pedido. Contacto:{" "}
        <Dato valor={RESPONSABLE.correo} />.
      </p>

      <h2>2. Tu cuenta</h2>
      <p>
        Para comprar creas una cuenta con tu correo y una contraseña. Eres responsable de lo que se haga con tu
        sesión; si crees que alguien más la usó, escríbenos. Debes ser mayor de edad.
      </p>

      <h2>3. El kit y los precios</h2>
      <ul>
        <li>El kit se arma con base en la lista oficial del colegio. Puedes cambiar un producto por otra opción de la misma categoría o descartar el que ya tienes.</li>
        <li>Los precios están en pesos colombianos (COP). El total que ves antes de pagar es el que se cobra.</li>
        <li>Algunos artículos no se cobran en Tukit: los que entrega el colegio, las licencias digitales y los que no tienen precio disponible se marcan con claridad y no suman al total.</li>
        <li>Los precios y la disponibilidad pueden cambiar. Si un producto deja de estar disponible antes de tu pago, te lo mostramos para que elijas otra opción.</li>
      </ul>

      <h2>4. Cómo se paga</h2>
      <p>
        Pagas en línea a través de una pasarela de pagos. Tukit no recibe ni guarda los datos de tu tarjeta. El pedido
        se confirma cuando el pago es aprobado. Si el pago es rechazado, no se te cobra y puedes intentarlo de nuevo.
      </p>

      <h2>5. Entrega</h2>
      <p>
        Entregamos en la dirección que indicas. El estado de tu pedido lo ves en Mis pedidos, con las fechas
        estimadas y las de entrega real. Si algo se retrasa, puedes abrir un caso desde Mis casos.
      </p>

      <h2>6. Retracto, cambios y garantía</h2>
      <p>
        Como compras a distancia, tienes derecho a retractarte en los 5 días hábiles siguientes a la entrega. La
        garantía legal cubre los defectos de los productos. Los detalles están en{" "}
        <Link href="/legal/retracto">Derecho de retracto y garantía</Link>.
      </p>

      <h2>7. Tus datos</h2>
      <p>
        Tratamos tus datos como explica la <Link href="/legal/privacidad">política de datos personales</Link>.
      </p>

      <h2>8. Uso adecuado</h2>
      <p>
        No uses Tukit para suplantar a otra persona, subir contenido que no te pertenezca o intentar acceder a
        pedidos que no son tuyos. Podemos suspender cuentas que lo hagan.
      </p>

      <h2>9. Cambios a estos términos</h2>
      <p>
        Si cambiamos estos términos, publicaremos la nueva versión aquí con su fecha. Los pedidos ya pagados se
        rigen por los términos vigentes cuando los hiciste.
      </p>

      <h2>10. Ley aplicable</h2>
      <p>
        Estos términos se rigen por las leyes de Colombia, en especial la Ley 1480 de 2011 (Estatuto del Consumidor)
        y la Ley 1581 de 2012. Si tienes una queja que no resolvamos, puedes acudir a la Superintendencia de
        Industria y Comercio.
      </p>
    </DocumentoLegal>
  );
}
