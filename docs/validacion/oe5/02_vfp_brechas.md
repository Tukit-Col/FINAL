# VFP vs lo que existe: brechas de TUKIT (2026-10-17)

Fuentes: `Arquitectura/VFP_ISIS2610G19_v3.docx` (citado como VFP, con la línea de `pandoc -t plain --wrap=none`),
`Arquitectura/ENMIENDA_VFP.md`, `Marco_Metodologico_Tukit_v3.md`, `Arquitectura/MATRIZ_OE_EVIDENCIA.md` (21-sep),
`Memoria/HECHOS_CANONICOS.md`, `Memoria/PLAN_MEMORIA.md` (23-sep), WBS v3 (csv) y código en `tukit/` (solo rg).
Aviso: la MATRIZ es del 21-sep y el código avanzó después; donde difieren, mando lo que vi en el código.
El VFP docx NO tiene aplicada la enmienda (el docx de `Arquitectura/` y el de `ENTREGA_FINAL/VFP/` aún dicen "móvil nativa").

## Actualizacion tras fetch (origin/main dfc4fd3)
`origin/main` pasó de 58b9e47 a dfc4fd3 (+154 commits, merge de `feature/integracion-total`). Releído con `git show/grep origin/main`, sin checkout.
Detalle técnico y tabla de ramas en `01_estado_implementacion.md` (sección "Actualizacion tras fetch"). Las tablas de abajo se corrigieron en línea
con la marca [ACTUALIZADO]; lo que no tiene marca no cambió o no se volvió a revisar.

**Brechas del VFP que cambian de estado:**
| Promesa del VFP | Antes | Ahora (origin/main) |
|---|---|---|
| Personalizar ítems individualmente (swap del padre, UI-03) | falta | PARCIAL-HECHO: botón "Cambiar por otra opción" por línea en `LineaDeKit.tsx`, `PUT /v1/trabajos/{id}/kits/{perfil}/lineas/{item}/producto`, solo entre las opciones de la línea. Falta el carrusel (el VFP no lo exige) |
| Ajustar presupuesto con recomputación en tiempo real | falta | PARCIAL: tope en pesos al empezar (`presupuesto_por_hijo`) + kit "A tu Medida" + aviso "se pasa del tope"; NO hay slider/recomputación en `/kits` |
| Tres kits Ahorrador/Fan/Premium | hecho (3) | hecho con desvío: son 4 (se agregó "A tu Medida", ADR/migración 20261004). Declarar el desvío junto con los 4 objetivos |
| Checkout con pasarela | parcial | MÁS COMPLETO: widget Wompi + `/pago/simulado` + `/pago/resultado` + pagar/cancelar desde el dashboard. Default `WOMPI_MODO=falso`; sandbox sin probar |
| Seguimiento / última milla | parcial | PARCIAL: admin con acciones de avance (reparto propio, repartidor, fecha estimada). Para el padre solo estado en "Mis pedidos"; `/pedidos/[id]` con línea de tiempo está en `feature/maps-and-feats` |
| Panel de colegio | falta | SIGUE FALTANDO: `/portal` es el aviso "apps/colegio pendiente de portar" |
| Panel de privacidad (consulta, exportación, supresión) | parcial/falta | SIGUE FALTANDO en la web y en identidad (sin rutas de exportar/suprimir). La rama `mejoras/seguridad-ortografia-carrusel` solo trae páginas estáticas `/privacidad`, `/terminos`, `/cookies` + banner |
| Cambiar personaje del Fan | parcial (solo revisor) | Igual; el padre ve el personaje aplicado en las anclas y puede cambiar cada ítem a mano |
| Front generativo / NL2C / gamificación | falta | Sin cambio (`rg` en origin/main: sin chat ni LLM en `apps/web`) |
| App nativa | descopeada | Igual (PWA). Sin `capacitor` en el repo |

**Dato nuevo para la narrativa del VFP:** el catálogo de `feature/afinar-kits-agustiniano` (sin fusionar, hasta 15-oct) sube de 667 a 1.050 productos y su auditoría v4 dice
"758 de 885 renglones comprables (85,6 %) salen bien en los dos perfiles" (v3: 617 de 886 = 69,6 %). Es evidencia de OE3/OE4 para el Agustiniano, pero está solo en esa rama.
Esa rama fusiona limpio con main (avance rápido).

**Qué suman las otras ramas al VFP:**
- `feature/maps-and-feats`: seguimiento del pedido para el padre, dirección con Google Places, logos de colegios, alta de colegio no aliado desde la cola.
- `a/fases-2-6-integracion`: solo pruebas (caracterización, e2e Playwright web/admin, `datos/golden`, gate de cobertura). Ayuda a OE4/OE5 funcional; no suma producto. Choca solo en `ci.yml`.
- `mejoras/seguridad-ortografia-carrusel`: `SelectorCuadernos` elige el diseño de portada (8 diseños, 8 stickers) por hijo y viaja en el contrato; el backend no lo lee. No es el "carrusel para elegir otro cuaderno" del VFP y trae conflictos con main en 6+ archivos.

**P0/P1 corregidos:** "cerrar el flujo del padre" ya tiene intercambio de ítem y pago de prueba en main, así que la tarea observable lista -> kit -> cambio de un ítem -> pago existe en código
(UNVERIFIED en ejecución). Siguen abiertos: panel de colegio, panel de privacidad, ajuste de presupuesto en vivo, y todo OE5 (nada de OE5 cambió).
`docs/PENDIENTES.md` (rev. 2026-10-08) no trae pendientes de UI; sí benchmark Laya a re-medir, ADR y SRS del repo externo `Arquitectura/` por traer, y calibrar τ.

## 1. Objetivos y metodología declarados

**General** (VFP l.240): diseñar una arquitectura de recomendador multiobjetivo que asista la construcción de kits escolares,
"midiendo su efecto sobre la carga cognitiva percibida, la usabilidad y la satisfacción" con padres del sector Salitre, 2026.

**Específicos** (VFP l.244-254; son CINCO, no cuatro; la enmienda dice "los otros cuatro" al hablar de OE4):
- OE1 Caracterizar el dominio (negocio, requisitos con actores, bases conceptuales y de datos).
- OE2 Diseñar la arquitectura con ATAM y documentarla en el SDD.
- OE3 Percepción (PDF/imagen/texto) + normalización semántica (búsqueda vectorial densa) + NL2C.
- OE4 Recomendación multiobjetivo (costo, fidelidad de marca, disponibilidad) con configuraciones diferenciadas, en interfaz web
  progresiva. Enmienda (Cambio 1, ENMIENDA l.33-38): se quita la app nativa y se agrega "integrada con la pasarela de pagos".
- OE5 Evaluar con pruebas funcionales, no funcionales, de carga y de usabilidad con usuarios reales; satisfacción y reducción de
  carga cognitiva frente al proceso tradicional.

**Metodología (nombre exacto)**: "Metodología Híbrida Contenedora" que integra SCRUM + RUP + CRISP-DM, con estándares IEEE 830/1016/1058
y ATAM (VFP l.322; Marco_Metodologico l.5-10). No es Design Science ni doble diamante. Sprints de 2 semanas (Fase 4: 2 sprints).
RUP = riesgos y trazabilidad; SCRUM = construcción; CRISP-DM = solo Business Understanding en F1 (VFP l.328).

| Fase / OE | Método declarado | Artefactos | Criterio de evaluación |
|---|---|---|---|
| F1 / OE1 (S3-S4) | CRISP-DM Business Understanding + Design Thinking; BMC, FODA, entrevistas semiestructuradas; scraper ético | SRS (IEEE 830), SPMP, catálogo piloto (≥3 proveedores), extractor periódico, Kanban | Documento de dominio, scraper operativo, entorno configurado (VFP l.352-360) |
| F2 / OE2 (S5) | ATAM: árbol de utilidad, tradeoffs, riesgos/anti-patrones; IEEE 1016 | QA, informe ATAM, SDD, documento maestro aprobado por el director | Documento maestro aprobado (VFP l.380) |
| F3 / OE3 (S5-S8) | Diseño experimental, κ de Cohen (2 anotadores), ≥3 enfoques de extracción (OCR, layout, LMM), RAG+DPR/MTEB+HNSW, MAUT, NL2C | Corpus anotado, pipeline multimodal, índice vectorial, estados COINCIDENCIA/PARCIAL/SIN, objeto R | Precisión/recall/F1 del mapeo; protocolo de estados validado (l.406-440) |
| F4 / OE4 (S8-S12) | MOKP + NSGA-II, hipervolumen, choice architecture (Thaler), directrices Humano-IA (Amershi) | Motor NSGA-II, 3 kits, paneles admin/colegio, PWA, pago, última milla | 3 configuraciones con hipervolumen documentado; E2E funcional (l.482-492) |
| F5 / OE5 (S12-S13.5) | Protocolo IHC (Lazar), SUS, NPS, think-aloud, NASA-TLX (en Marco; el VFP no lo lista), estadística inferencial | Protocolo ético, consentimiento, Reporte de Evaluación, Anexos T/U | SUS (meta ≥68 en WBS/dossier), NPS, interacciones discretas vs flujo tradicional (l.500-530) |

Cómo se evidencia cada OE (MATRIZ_OE_EVIDENCIA + HECHOS): OE1 ACTA_APROBACION_OE1 (17 colegios, 3.608 ítems, 1.451 formas, encuesta
N=65/n=60); OE2 ACTA_APROBACION_OE2 con reservas (B′ 4,27/5, 14 escenarios, 18 ADR); OE3 acta con 7 compuertas (κ=0,705, F1 0,948,
60 sublistas/2.176 ítems, cobertura 83 %); OE4 código (NSGA-II pymoo, hipervolumen, checkout mock, cobertura 80-90 %); OE5 nada ejecutado.

## 2. Tabla de brechas (promesa -> estado -> evidencia)

Estado: hecho / parcial / falta. "Verif." = confirmado con rg en `tukit/` hoy.

### 2.1 Núcleo OE1-OE4

| Promesa del VFP | Estado | Evidencia / comentario |
|---|---|---|
| SRS IEEE 830, SPMP, QA, ATAM, SDD (tabla de entregables, VFP l.256-284) | hecho | `Arquitectura/SRS_*_v6.docx`, `ATAM_Tukit.tex`, `SDD_Tukit.tex`, `SPMP_*_v3.docx`; reservas OE2: 46 incoherencias, 25 altas (`COHERENCIA_OE2.md`) |
| Scraper periódico, catálogo piloto ≥3 proveedores | hecho | 503 productos (HECHOS §OE1); `Isis2610-G19-Tukit-Poc/services/scraper/` |
| Corpus de listas anotado, κ de Cohen | hecho | κ 0,705 (HECHOS §OE3); acta `MS-Busqueda/docs/f3-8.2/ACTA_APROBACION_OE3.md` |
| Comparar ≥3 enfoques de percepción | hecho | Gemini F1 0,948 vs Vision, GOT-OCR, reglas 0,298 (HECHOS §OE3). Falta cuadrar F1 del acta (0,925) y MRR "Aprox." |
| Índice vectorial + HNSW + MTEB; "DPR + FAISS" | parcial/desvío | Se implementó pgvector + RRF híbrido, e5-large (HECHOS); Marco_Metodologico dice "GraphRAG con DPR/FAISS" y HECHOS dice que el grafo se colapsó en pgvector (ADR 0006). Hay que alinear el Marco |
| Calibración de umbrales τ, δ con evidencia | parcial | τ=0,85/δ=0,05 con 7 ejemplos; 542 ítems anotados sin usar (HECHOS §OE3; PLAN_MEMORIA l.115) |
| NL2C (lenguaje natural a restricciones, inyección rechazada) | parcial | Solo en la PoC (`Isis2610-G19-Tukit-Poc/services/api-gateway/nl2c/parser.py`); verif.: cero menciones en `tukit/` |
| Estados de resolución COINCIDENCIA/PARCIAL/SIN + cola HITL | hecho | Máquina de estados y auditoría (`servicios/inteligencia/.../dominio/`, `trabajos.py`); G6 acta OE3 |
| NSGA-II + MOKP + hipervolumen, 3 objetivos | hecho (con desvío) | `optimizador.py`, `test_optimizador.py`. El código usa 4 objetivos (HECHOS) y el VFP dice 3; declarar el desvío. Presupuesto vive en `recomendar`, no en el frente (docstring `optimizador.py` l.22-26) |
| 3 kits Ahorrador / Fan / Premium en la web | hecho [ACTUALIZADO: son 4, con "A tu Medida"] | `apps/web/src/app/kits/[trabajo_id]/VistaKits.tsx` (copy por perfil l.31) |
| Anexo S: kits e hipervolumen | falta (documental) | PLAN_MEMORIA "Anexos": pendiente |
| Panel de administrador (carga, mapeo, aprobación, corrección) | hecho | `apps/admin/src/components/` (ConsolaRevision, AprobarLista, MatrizComparacion, PersonajeFan...) |
| Panel de colegio | falta [sin cambio en origin/main] | `apps/web/src/app/portal/page.tsx` es un aviso: "apps/colegio está pendiente de portar"; `apps/` solo tiene admin y web (la MATRIZ lo da por existente) |
| Autoservicio del padre (foto/PDF) | hecho | `apps/web/src/app/api/listas/subir/route.ts`, `/v1/listas/subir` |
| Resolución de conflictos (SIN_COINCIDENCIA, presupuesto insatisfacible) | parcial | Admin sí; en la web del padre no hallé pantalla de resolución (el "popup de variantes" del Marco no verificado) |
| Panel de privacidad con consulta, exportación y supresión | parcial/falta [re-verificado en origin/main: sigue sin UI] | Verif.: sin UI en `apps/web`; en identidad hay `GET /v1/cuenta` y flujo de supresión en tests (`test_privacidad.py`), no vi ruta de exportación |
| Checkout con pasarela | parcial [ACTUALIZADO: widget + /pago/simulado + /pago/resultado en origin/main] | Wompi (enmienda): `servicios/comercio/.../pasarela.py`, `POST /v1/webhooks/wompi`, `Checkout` en `VistaKits.tsx`. Pago real depende de NIT (D4, `FLUJO_EXTREMO_A_EXTREMO.md`); el hito WBS F4-11.2 solo pide mock |
| Seguimiento del pedido / última milla (rutas, operadores) | parcial [ACTUALIZADO: admin con acciones de avance y reparto propio; padre sin página de pedido en main] | `GET /v1/ordenes/{id}`, `/avanzar`, `LineaDelTiempo.tsx`; MATRIZ F4-11.2: solo etiqueta de estado. Ruteo optimizado por salón: no verificado (R-06) |
| Retracto / logística inversa (Ley 1480) | parcial | `POST /v1/ordenes/{id}/retracto`; reembolso manual (ENMIENDA l.178-181) |
| Despliegue productivo con endurecimiento | falta (declarado) | Minikube; va a Trabajo futuro (ENMIENDA l.183-186) |
| App móvil nativa iOS/Android | descopeada | ADR 0009; Capacitor como mitigación híbrida (ENMIENDA Cambio 7). Verif.: `capacitor` no aparece en `tukit/`; la ruta citada `Tukit-Frontend/frontend/pwa/` ya no existe en el árbol. Revisar que la afirmación siga siendo cierta |
| Pruebas automatizadas del motor e interfaces | parcial | Cobertura 80-90 % por servicio; CI del front sin umbral, Anexo V pendiente |

### 2.2 Paso final de PERSONALIZACIÓN (lo que pediste mirar)

Qué promete el VFP (cita textual):
- Descripción de la solución (l.222): la plataforma "permite visualizar la lista de productos con su precio total estimado,
  **personalizar ítems individualmente, ajustar el presupuesto con recomputación en tiempo real y generar componentes dinámicos
  según la interacción [26]**, culminando con la acción de agregar la configuración seleccionada al carrito".
- Entrada (l.214): preferencias "de marca y/o personalización deseada por el niño (por ejemplo, **Personaje animado favorito**)".
- Fase 4 actividades (l.470): "visualización de las tres alternativas de kit (Ahorrador, Fan, Premium), **personalización por ítem**,
  ajuste de presupuesto con recomputación en tiempo real, panel de privacidad...". La enmienda (Cambio 4) conserva esa frase.
- Fan (l.222): "perfil Fan, centrado en preferencias específicas de marca".
- Sprint 2 (l.460): "checkout mock, seguimiento, panel de colegio, **kit personalizado** e integración end to end".
- NL2C (l.614): "prefiero colores vivos en los cuadernos", "evitar marca genérica", "presupuesto máximo de $250.000".
- El VFP no dice "carrusel" ni "front generativo con chat". Lo más cercano: "generar componentes dinámicos según la interacción [26]" y la
  cita [52] Chen et al., "The GenUI Study" (l.622, referencia l.810), que presenta GenUI como paradigma "en contraste con" interfaces fijas.
  Es una promesa implícita y débil, apoyada en una cita, no un requisito.

| Ítem de personalización | Estado | Evidencia |
|---|---|---|
| Elegir personaje del hijo al registrarse | hecho | `apps/web/src/app/empezar/SelectorPersonaje.tsx`, `IconosPersonaje.tsx`, `personaje_por_hijo` |
| Fan = anclas con el personaje pedido (cuaderno, cartuchera, carpeta, maleta) | hecho (servidor) | `trabajos.py` (`_anclas_de_personaje`, `inyectar_personaje_fan`); commits `a4bbc8d`, `99cdc87`. Es búsqueda determinista, no re-ranking del NSGA |
| Cambiar de personaje en el kit Fan después de generado | parcial | Solo el revisor: `apps/admin/src/components/PersonajeFan.tsx` (swap por-nivel `fijarProductoLinea`). El padre no tiene control |
| **Carrusel para elegir otro cuaderno (u otro ítem) entre las alternativas** | [ACTUALIZADO] parcial: swap SÍ, carrusel NO | En origin/main `LineaDeKit.tsx` tiene "Cambiar por otra opción" con tarjetas y botón elegir y la ruta `PUT /v1/trabajos/.../lineas/{item}/producto`; sigue sin carrusel (`rg carrusel` solo da `directorio-colegios.json`). [Texto viejo, ya falso: sin botón de elegir y sin ruta del padre; la única era] `POST /v1/admin/trabajos/{id}/kits/{perfil}/lineas/{item}/producto` (admin). Es el requisito `UI-03` del SRS, ya diferido a v2 (`ADENDA_REQUISITOS_SRS.md` §7 pregunta 3) |
| Ajuste de presupuesto con recomputación en tiempo real | [ACTUALIZADO] parcial | En origin/main `FormularioEmpezar.tsx` pide un tope en pesos (`presupuesto_por_hijo`, con prioridad punto medio) y `VistaKits.tsx:179` avisa si el kit se pasa; no hay recomputación en vivo en `/kits` |
| Kit personalizado: tema/color y re-ponderar `fan_score` (WBS F4-11.3) | falta | MATRIZ: "único hueco de producto real"; `fan_score` es atributo del producto, no eje de preferencia del niño. WBS excluye marcas registradas (IP) como WON'T, lo cual choca con "Spiderman" como personaje: decidir y escribirlo |
| **Front generativo (UI generada, con chat)** | falta, y sin requisito | `FLUJO_EXTREMO_A_EXTREMO.md` T5/A9: "sin requisito" (8-15 jornadas); `ADENDA_REQUISITOS_SRS.md` §8 lo declara "alcance diferido". Verif.: sin chat ni LLM en `apps/web` (solo `ayuda/SobreSoporte.tsx`, que es soporte) |
| Gamificación con personaje | falta, sin requisito | FLUJO T6/A10; encuesta P21: personaje puntúa 1,87 vs 2,85 del precio (ADENDA §7). SRS pone al niño como actor sin acceso |
| NL2C en la interfaz | falta | Ver 2.1; la PoC lo tiene, el monorepo no |

Lectura: lo que SÍ está prometido en el VFP y falta es "personalización por ítem" (carrusel/swap del padre), "ajuste de presupuesto en
tiempo real" y el "kit personalizado". El front generativo es una aspiración respaldada por una cita, no una promesa contractual; si no se
construye, basta una línea en Trabajo futuro y no rompe ningún OE.

### 2.3 OE5: validación con padres

Qué dicen los documentos:
- Método (VFP l.498-502): protocolo de dos pasos; Paso 1 protocolo ético aprobado (Lazar + Ley 1581) "antes de involucrar participantes";
  Paso 2 "observación directa de sesiones en las que padres de familia realizan tareas representativas".
- Instrumentos (VFP l.502): SUS, think-aloud (verbalización concurrente), NPS. NASA-TLX aparece solo en Marco y WBS.
- Muestra (VFP l.502): "al menos 5 participantes, con un objetivo ideal de n >= 20 para detectar el 95 % de los problemas de usabilidad
  [44]; el análisis se ajustará al tamaño de muestra efectivamente alcanzado". WBS F5-11.1: lista estratificada con n>=20 confirmados antes
  de la primera sesión; F5-13.2: declarar "exploratorio" si n<20.
- Carga cognitiva (VFP l.502): interacciones discretas (clics, búsquedas, validaciones) con Tukit vs flujo tradicional [17]. Marco añade
  NASA-TLX y estadística inferencial (Shapiro-Wilk, t pareada o Wilcoxon, IC95 %).
- Tiempos: Marco S12-S13.5; WBS F5-11.1 sem 11 (ético), F5-12.1 sem 12 (instrumentos), F5-13.1 a 13.3 sem 13 (sesiones, análisis, hito OE5),
  14.1-14.4 sem 14 (entrega). El VFP no fija semanas. Presencialidad: el VFP dice "observación directa de sesiones"; no usa la palabra
  "presencial" ni fija lugar; el Plan de `Nestle/research/03_plan_validacion_presencial.md` propone el Agustiniano Salitre y es propuesta, no decisión.
- Criterios de éxito: SUS >= 68 (WBS gate QA #4, dossier `main.tex` l.338), NPS positivo, menos carga que lo tradicional.
- Consentimiento: VFP lo lista como entregable "requisito previo" (l.274); WBS pide adulto + asentimiento de menor si aplica.

| Promesa OE5 | Estado | Evidencia |
|---|---|---|
| Protocolo ético y consentimiento (Anexos N, O) | falta | PLAN_MEMORIA "Anexos" y `Memoria/sections/anexos.tex` l.23-27: pendiente; no hay archivo |
| Instrumentos SUS/NPS/NASA-TLX + guion think-aloud + batería de tareas (Anexo T) | falta | Pendiente; `rg` solo halla menciones en documentos, ningún instrumento |
| Notebook de análisis (Shapiro-Wilk, t/Wilcoxon) | falta | Verif.: sin `.ipynb` ni script fuera de las menciones. La memoria lo afirma "preparado" |
| k6, ZAP, SCA (pruebas no funcionales sin padres) | falta | Verif.: sin archivos k6/zap en el repo |
| Reclutamiento n>=20 estratificado | falta | Sin lista ni contacto con el colegio |
| Sesiones, SUS/NPS, comparación vs proceso tradicional | falta | Ejecutar tras lo anterior |
| Pruebas funcionales E2E (B2B y autoservicio) | parcial | Tests por servicio; reporte E2E consolidado no existe |

ALERTA de coherencia: `Memoria/sections/resultados.tex` l.316-318 dice que "se completó el instrumental completo" y que la ejecución
"quede reducida a la convocatoria". No encontré ese instrumental. Además, la misma sección declara que la validación no se ejecutó "dentro
del alcance temporal": para el VFP y el objetivo general, OE5 es el núcleo del aporte (medir carga cognitiva), no un apéndice. Hay que
corregir esa redacción o producir el instrumental antes de entregar.

## 3. Qué falta para cerrar, por prioridad

P0 (bloquea el objetivo general; son personas y plazos):
1. Protocolo ético y consentimiento (Anexos N, O), aprobados por el director, y contacto con el colegio para reclutar n>=20 (mínimo 5).
2. Instrumentos (Anexo T): SUS, NPS, NASA-TLX, guion think-aloud, batería de tareas y definición del baseline tradicional. Construirlos antes
   de las sesiones.
3. Cerrar el flujo del padre que se va a observar. Mínimo: lista -> kit -> intercambio de un ítem -> pago de prueba. [ACTUALIZADO: en origin/main ya existe el intercambio y el pago simulado; falta ensayarlo de punta a punta.]
4. Ejecutar sesiones, analizar (notebook con datos sintéticos primero), Reporte de Evaluación (F5-13.1 a 13.3). Si n<20, declarar "exploratorio".

P1 (promesas del VFP que faltan y se ven en la sustentación):
1. [HECHO en origin/main, salvo el carrusel] Swap del padre por ítem (`UI-03`): ya hay ruta no-admin y selector en `LineaDeKit.tsx`. Pendiente solo si se quiere la forma de carrusel.
2. Ajuste de presupuesto en vivo en `/kits` (hoy solo el tope inicial; el optimizador ya lo trata como cota en `recomendar`).
3. Kit personalizado WBS F4-11.3 (personaje/tema en el kit Fan para el padre). Decidir primero el tema IP (WBS lo excluye, el código ya usa franquicias).
4. Firmar OE1, OE2 (previo cierre RLS y 46 correcciones), OE3 (cuadrar 3 cifras, portar calibración), OE4 (Anexos S, V, Z, tag `v1.0-mvp-oe4`).
5. Panel de colegio (`apps/colegio` no existe) o declararlo Trabajo futuro/ADR; hoy el VFP lo promete en Sprint 2 y en F4.

P2 (higiene documental, rápida):
1. Aplicar ENMIENDA_VFP al docx (7 cambios) y verificar con `textutil ... | rg 'móvil nativa'`. Hoy los documentos hijos ya asumen el texto enmendado.
2. Mover NL2C al monorepo o documentar que vive en la PoC; alinear Marco_Metodologico (DPR/FAISS/GraphRAG) con pgvector + RRF (ADR 0006).
3. Declarar desvíos: 4 objetivos (VFP 3), pgvector en vez de FAISS, Wompi en vez de ePayco, app nativa a híbrido.
4. Corregir la afirmación de Capacitor (carpeta citada inexistente) y la de HECHOS "2/7 portados", que ya no coincide con `tukit/servicios/` (6 servicios presentes; en origin/main igual, 72 tablas esperadas; `README.md` raíz sigue diciendo "cuatro procesos").
5. Front generativo con chat y gamificación: una línea en Trabajo futuro con la cita [52]; no construir antes de cerrar P0.

P3 (memoria): capítulos ya tienen ~19.4k palabras (`Memoria/sections/`); faltan Resultados OE4/OE5 con datos reales, Anexos N, O, S, T, V, Z,
consolidar bibliografía (81 + 37 entradas), checklist VFP<->anexo (WBS 14.2), matriz final (14.3), repo con `docker compose up` y release (14.1), radicación (14.4).
