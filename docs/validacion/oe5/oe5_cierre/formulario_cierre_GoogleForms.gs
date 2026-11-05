/**
 * TUKIT · cuestionario de cierre OE5 (SUS + RTLX + NPS), ~3 minutos.
 * Uso: script.google.com > Nuevo proyecto > pegar > Ejecutar crearCuestionarioCierre.
 * En el registro (Ver > Registros) salen el enlace de edición y un enlace
 * prellenado por participante (ACU-01..ACU-06): envíe a cada acudiente el suyo.
 */
function crearCuestionarioCierre() {
  var f = FormApp.create("TUKIT: su opinión después de la prueba (3 minutos)");
  f.setCollectEmail(false).setProgressBar(true).setLimitOneResponsePerUser(false);
  f.setDescription(
    "¡Gracias otra vez por probar TUKIT! Son 3 minutos. Piense en la prueba que hizo con nosotras " +
    "y en su última compra de útiles. Evaluamos la aplicación, no a usted: no hay respuestas " +
    "correctas ni incorrectas. Sus respuestas se guardan con un código, sin nombre, y se usan solo " +
    "para el trabajo de grado (Ley 1581 de 2012). Puede pedir que se borren escribiendo a tukit.ayuda@gmail.com.");

  var codigo = f.addTextItem().setTitle("Código (ya viene lleno, no lo cambie)").setRequired(true);
  f.addMultipleChoiceItem()
    .setTitle("Autorizo usar estas respuestas, sin mi nombre, para el trabajo de grado.")
    .setChoiceValues(["Sí, autorizo"]).setRequired(true);

  // Parte 1. SUS (Brooke, 1996), versión en español, 10 ítems, 1-5.
  f.addPageBreakItem().setTitle("1. Su opinión sobre TUKIT")
    .setHelpText("1 = totalmente en desacuerdo · 5 = totalmente de acuerdo. Lea cada frase completa: unas están en positivo y otras en negativo.");
  [
    "Creo que me gustaría usar TUKIT con frecuencia.",
    "Encontré TUKIT innecesariamente complejo.",
    "Pensé que TUKIT era fácil de usar.",
    "Creo que necesitaría el apoyo de una persona técnica para poder usar TUKIT.",
    "Encontré que las diversas funciones de TUKIT estaban bien integradas.",
    "Pensé que había demasiada inconsistencia en TUKIT.",
    "Imagino que la mayoría de las personas aprendería a usar TUKIT muy rápido.",
    "Encontré TUKIT muy incómodo de usar.",
    "Me sentí muy seguro o segura usando TUKIT.",
    "Necesité aprender muchas cosas antes de poder empezar a usar TUKIT."
  ].forEach(function (t) {
    f.addScaleItem().setTitle(t).setBounds(1, 5).setLabels("Totalmente en desacuerdo", "Totalmente de acuerdo").setRequired(true);
  });

  // Parte 2 y 3. RTLX (NASA-TLX sin pesos), 6 escalas 0-10, tradicional y con TUKIT.
  var escalas = [
    ["Exigencia mental", "¿Cuánto tuvo que pensar, comparar, decidir y recordar?"],
    ["Exigencia física", "¿Cuánto tuvo que desplazarse, cargar o moverse?"],
    ["Presión de tiempo", "¿Cuánta prisa o presión sintió?"],
    ["Resultado", "¿Qué tan mal le fue en conseguir todo lo de la lista? (0 = perfecto, 10 = muy mal)"],
    ["Esfuerzo", "¿Cuánto se tuvo que esforzar para lograrlo?"],
    ["Frustración", "¿Qué tan estresado o molesto se sintió?"]
  ];
  f.addPageBreakItem().setTitle("2. Su última compra de útiles (sin TUKIT)")
    .setHelpText("Piense en la última vez que compró la lista de útiles a su manera de siempre. 0 = muy bajo · 10 = muy alto.");
  escalas.forEach(function (e) {
    f.addScaleItem().setTitle(e[0] + " (compra habitual)").setHelpText(e[1]).setBounds(0, 10).setRequired(true);
  });
  f.addPageBreakItem().setTitle("3. La prueba con TUKIT")
    .setHelpText("Ahora piense en la prueba que hizo con TUKIT. 0 = muy bajo · 10 = muy alto.");
  escalas.forEach(function (e) {
    f.addScaleItem().setTitle(e[0] + " (con TUKIT)").setHelpText(e[1]).setBounds(0, 10).setRequired(true);
  });

  // Parte 4. NPS.
  f.addPageBreakItem().setTitle("4. Para terminar");
  f.addScaleItem().setTitle("¿Qué tan probable es que recomiende TUKIT a otro papá o mamá del colegio?")
    .setBounds(0, 10).setLabels("Nada probable", "Muy probable").setRequired(true);
  f.addParagraphTextItem().setTitle("¿Por qué? (opcional)").setRequired(false);

  Logger.log("Editar: " + f.getEditUrl());
  for (var i = 1; i <= 6; i++) {
    var c = "ACU-0" + i;
    var r = f.createResponse().withItemResponse(codigo.createResponse(c));
    Logger.log(c + ": " + r.toPrefilledUrl());
  }
}
