import Link from "next/link";
import DocumentoLegal, { Dato } from "../DocumentoLegal";
import { RESPONSABLE } from "../datos-legales";

export const metadata = { title: "Tratamiento de datos personales | Tukit" };

export default function PaginaPrivacidad() {
  return (
    <DocumentoLegal
      titulo="Política de tratamiento de datos personales"
      resumen="Qué datos guardamos, para qué los usamos y cómo puedes consultarlos, corregirlos o pedir que los borremos. Se rige por la Ley 1581 de 2012 y el Decreto 1377 de 2013."
    >
      <h2>1. Quién es el responsable</h2>
      <p>
        El responsable del tratamiento es {RESPONSABLE.nombre} (<Dato valor={RESPONSABLE.razonSocial} />, NIT{" "}
        <Dato valor={RESPONSABLE.nit} />
        ), con domicilio en <Dato valor={RESPONSABLE.domicilio} />. Puedes escribirnos a{" "}
        <Dato valor={RESPONSABLE.correo} /> o llamar al <Dato valor={RESPONSABLE.telefono} />.
      </p>

      <h2>2. Qué datos recogemos</h2>
      <ul>
        <li>Tuyos como acudiente: nombre, correo, teléfono, ciudad y dirección de entrega.</li>
        <li>De tus hijos: grado, colegio y las tallas que decidas darnos para armar el kit.</li>
        <li>De tus pedidos: qué compraste, el valor, el estado y las fechas de entrega.</li>
        <li>
          De tus casos de ayuda: el mensaje que escribes y las respuestas que recibes.
        </li>
      </ul>
      <p>
        No guardamos el número de tu tarjeta ni tus datos bancarios: el pago lo procesa la pasarela de pagos y a
        nosotros solo nos llega si fue aprobado o no.
      </p>

      <h2>3. Para qué los usamos</h2>
      <ul>
        <li>Crear tu cuenta y mantener tu sesión.</li>
        <li>Armar la lista de útiles y el kit de cada hijo según su colegio y grado.</li>
        <li>Procesar, entregar y hacer seguimiento a tus pedidos, incluidos retractos y garantías.</li>
        <li>Atender tus casos de ayuda y comunicarnos contigo sobre tu pedido.</li>
        <li>Cumplir obligaciones legales, contables y tributarias.</li>
        <li>Mejorar el servicio con datos agregados, sin identificarte.</li>
      </ul>
      <p>No vendemos tus datos. Solo los compartimos con quienes hacen posible el servicio (por ejemplo, la pasarela de pagos y el transportador) y únicamente para lo necesario.</p>

      <h2>4. Datos de niños, niñas y adolescentes</h2>
      <p>
        El artículo 7 de la Ley 1581 de 2012 prohíbe tratar datos de menores, salvo los de naturaleza pública. El
        Decreto 1377 de 2013 permite el tratamiento cuando responde al interés superior del menor y se respetan sus
        derechos, con autorización de su representante legal. En Tukit solo tratamos los datos mínimos del menor
        (grado, colegio y tallas) y únicamente porque tú, como madre, padre o representante legal, los entregas y lo
        autorizas. Puedes negarte a darlos: el kit se puede armar solo con colegio y grado.
      </p>

      <h2>5. Tus derechos como titular</h2>
      <p>Tienes derecho a:</p>
      <ul>
        <li>Conocer, actualizar y rectificar tus datos (acceso, rectificación y actualización).</li>
        <li>Pedir prueba de la autorización que nos diste.</li>
        <li>Saber cómo usamos tus datos.</li>
        <li>Presentar quejas ante la Superintendencia de Industria y Comercio por infracciones a la ley.</li>
        <li>Revocar la autorización y pedir que borremos tus datos (cancelación y supresión), cuando no haya un deber legal o contractual de conservarlos.</li>
        <li>Acceder a tus datos de forma gratuita.</li>
      </ul>
      <p>Esto es lo que se conoce como derechos ARCO (acceso, rectificación, cancelación y oposición) y habeas data.</p>

      <h2>6. Cómo ejercerlos</h2>
      <p>
        Con tu sesión iniciada, en <Link href="/privacidad">Privacidad y mis datos</Link> puedes ver lo que
        guardamos, descargar una copia, retirar tu autorización y pedir que borremos tus datos.
      </p>
      <p>
        También puedes escribir a <Dato valor={RESPONSABLE.correo} /> o abrir un caso desde la sección Ayuda con tu sesión iniciada,
        indicando qué quieres hacer. Una consulta se responde en máximo 10 días hábiles y un reclamo en máximo 15
        días hábiles; si necesitamos más tiempo, te avisamos antes de que venza el plazo y te decimos cuándo
        responderemos.
      </p>

      <h2>7. Seguridad y conservación</h2>
      <p>
        Protegemos tus datos con acceso por sesión personal y control de quién puede ver cada pedido. Los
        conservamos mientras tengas cuenta y el tiempo que la ley exija para soportes contables y de garantía.
      </p>

      <h2>8. Vigencia</h2>
      <p>
        Esta política rige desde la fecha indicada arriba. Si la cambiamos de forma importante, te lo avisaremos y
        volveremos a pedir tu autorización cuando la ley lo exija.
      </p>
    </DocumentoLegal>
  );
}
