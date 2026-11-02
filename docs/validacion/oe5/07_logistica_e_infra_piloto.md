# 07 Logística e infraestructura del piloto (Bogotá, dic 2026 - ene 2027)
Consultado 2026-10-17. FX: 1 USD = 3.183 COP; 1 EUR = 3.578 COP (open.er-api.com, act. 2026-10-18 00:02 UTC; no es TRM oficial).
Límite: WebSearch no estuvo disponible; se buscó con Brave/WebFetch y hubo bloqueos 429. Lo no verificado va como ESTIMADO.

## A) Entrega última milla en Bogotá
- Moto, misma localidad: 0-5 km 8-12k; 5-10 km 12-18k; 10-15 km 18-25k COP (tumensajeroexpress.com.co/cuanto-cuesta-un-envio-en-moto-en-bogota-guia-de-precios-2025/, 2026-02-02; blog de un courier, sesgo comercial).
- Recargo por peso en moto: 5-10 kg +5-8k; 10-20 kg +10-15k (requiere "moto especial"); >20 kg no viable. Mismo día +20-30% (misma fuente).
- Mensajeros Urbanos: tarifa base incluye 3 km; km adicional $900 en Bogotá (enviotodo.com.co, páginas de 2019-2021, DESACTUALIZADO). Rapigo: km adicional $1.000 (rapigo.co, sin fecha). Mensajeros Urbanos y Picap no publican tarifas; hay que cotizar en la app.
- Ruta de 15 km, paquete de 20 cm: Cabify 14.200; Pibox (Picap) ~17.400; Uber 20.330; Didi 21.200 (larepublica.co, 2023-12-13). En diciembre la demanda de viajes sube más de 60% (misma nota).
- Rappi Favor y Didi Envíos: sin tarifa pública verificada para paquete de 5-12 kg. ESTIMADO igual que moto: 18-30k.
- Transportadoras urbanas Bogotá: Coordinadora 15.330; Servientrega 20.600; Inter Rapidísimo desde 45.000 (tumensajeroexpress.com.co/cual-es-el-valor-de-un-envio-en-bogota/, 2025-07-22, sin peso ni fuente). Servientrega desde 9.200/kg (enviotodo.com.co, 2023-01). Son entregas en 1-3 días, no sirven para el día exacto.
- Camioneta/acarreo con conductor: desde 120.000 por servicio, mínimo 1 h, 6 am-6 pm, hasta ~6 m3 (trasteoselvelodromo.com/acarreos-en-bogota-baratos/, tarifas 2025). Camión 600 hasta 580.000+ (misma fuente).
- Alquiler camioneta sin conductor: 311.666-368.333/día (abcrentacar.com.co, sin fecha); 300-600k/día (carroya.com, sin fecha). El conductor se suma.
- Día de camioneta/van con conductor para entrega consolidada: ESTIMADO 300.000-500.000 COP (+ ayudante 80-120k ESTIMADO).

## B) Empaque
- Caja corrugada 40x30x30 nueva por mayor: no hay precio publicado. Referencias: 50x30x30 nueva 5.500; 60x40x40 nueva 8.500; 40x30x30 usada 3.500, entrega en Bogotá incluida (cajasycajas.com.co/cajas-carton-embalaje, sin fecha; "precios especiales por volumen"). Cartonecol: nuevas 2.300-11.000 según modelo (cartonecol.com, sin fecha).
- Caja 40x30x30 nueva (ESTIMADO): 3.500-5.000. Una usada baja el costo pero se ve peor para un regalo.
- Cinta de embalar y rótulo: ESTIMADO 400-900 por kit (rollo 48 mm x 100 m a 3-5k; etiqueta 100-300). Papel kraft/relleno ESTIMADO 500-1.000.
- Pliego de stickers (regalo): ESTIMADO 300-1.500 por kit (impresión digital 100-500 unidades). No se verificó precio.
- Empaque por kit: bajo 4k / base 6k / alto 9k (ESTIMADO, sumando lo anterior).

## C) Recogida en proveedores (papelería/mayorista/Panamericana al sitio de empaque)
- Una camioneta con conductor desde 120k por viaje (mismo dato de Velódromo, 2025). Muchos mayoristas entregan gratis sobre un mínimo de compra (ESTIMADO, preguntar).
- Para ~100 kits: 1-3 viajes = 120-400k, o sea 1.000-4.000 por kit. ESTIMADO: bajo 1k / base 2,5k / alto 4,5k.

## Costo logístico por kit (COP, sin precio de los útiles ni mano de obra del equipo)
Entrega a domicilio (moto o carro por familia, 5-15 km, kit de 5-12 kg, mismo día):
- Tramo: bajo 15k (moto, 5-10 km, sin recargo urgente) / base 24k (moto 8-12 km + 5-8k por peso + 25% mismo día) / alto 40k (kit >10 kg, carro o moto especial, 15 km, pico de diciembre, reintento).
- Total con empaque y recogida: bajo ~20k / BASE ~33k / alto ~54k.
Entrega consolidada en el colegio (una camioneta, un día, ~100 kits; requiere permiso del colegio y que el colegio reparta):
- Tramo: bajo 3k (camioneta 300k) / base 4,8k (480k: camioneta + ayudante) / alto 8k (800k: camión pequeño, 2 ayudantes, 2 viajes).
- Total: bajo ~8k / BASE ~13k / alto ~22k. Con 40 kits el costo fijo del día pesa más: ~12k/20k/32k (bajo/base/alto, ESTIMADO). Con 150 kits baja a ~11k base.
- Diferencia: la entrega consolidada cuesta ~20k menos por kit, pero pierde el "llega a casa". Cada kit de 5-12 kg en moto especial puede ser inviable si pesa >10 kg.

## D) Infraestructura del piloto (monorepo ~6 servicios FastAPI + workers + Postgres/pgvector + Next.js, Docker)
- Hetzner (excl. IVA, actualización 2026-06-15: CX/CAX +30-40%, CPX más del doble): CX23 2 vCPU/4 GB EUR 5,49; CX33 4 vCPU/8 GB EUR 8,49; CAX21 ARM 4 vCPU/8 GB EUR 10,49; CPX22 EUR 19,49; IPv4 +EUR 0,50 (costgoat.com/pricing/hetzner, 2026; hetzner.com/cloud/cost-optimized). CX solo en UE (FSN/NBG/HEL); en EE.UU. solo CPX, más caro. Latencia Colombia-UE ~120-150 ms (ESTIMADO), aceptable para el piloto.
- DigitalOcean: 4 GB/2 vCPU USD 24 (76k COP); 8 GB/4 vCPU USD 48 (153k) (digitalocean.com/pricing/droplets, 2026).
- Contabo: Cloud VPS 8 (8 vCPU/24 GB) EUR 11,20/mes con contrato de 24 meses, EUR 14 normal (contabo.com/en/vps, 2026). Barato por RAM, pero con contrato largo.
- Oracle Always Free: ARM A1 2 OCPU/12 GB, 200 GB disco, 10 TB salida, USD 0; reclama instancias con CPU <20% por 7 días y a veces no hay cupo (docs.oracle.com FreeTier, 2026). Sirve como respaldo, no como principal.
- Postgres administrado: Neon Free USD 0 (1 GB, 100 CU-h, pgvector sí, restauración 6 h); Launch USD 0,106/CU-h + 0,35/GB-mes (neon.com/pricing, 2026). Supabase Free USD 0 (500 MB, pausa tras 1 semana sin uso, sin backups); Pro desde USD 25 = 79,6k COP (supabase.com/pricing, 2026). Mejor Postgres en el mismo VPS.
- Vercel: Hobby USD 0 pero solo uso no comercial (vender kits lo incumple); Pro USD 20 = 63,7k COP (vercel.com/pricing, 2026). Mejor correr Next.js en el mismo docker compose.
- Dominio: .co USD 31,20/año = 99k COP (8,3k/mes); .com USD 11,08/año = 35k COP (2,9k/mes) (porkbun.com, 2026).
- Correo: Resend Free 3.000/mes y 100/día; Pro USD 20 por 50.000 (resend.com/pricing, 2026). Brevo: no se pudo verificar.
- Backups: copia de Hetzner ~20% del precio del servidor (ESTIMADO, ~6k COP) o pg_dump nocturno a otro almacenamiento. Gemini uso ligero: ESTIMADO USD 2-5/mes.

Costo mensual del piloto (COP, FX 3.183/3.578)
- BAJO ~42k (USD 13): CX33 + IPv4 EUR 8,99 = 32k; dominio .com 3k; Gemini 6k; Resend free; pg_dump manual. Opción mínima: Oracle gratis + dominio = ~10k, con riesgo de cupo o reclamo.
- BASE ~63k (USD 20): CX33 + IPv4 32k; backups Hetzner 6k; dominio .co 8k; Gemini 16k; Resend free; Next.js y Postgres dentro del VPS.
- Si se separa en Vercel Pro + Supabase Pro: +143k, ~205k/mes (no recomendado). No incluye comisión bancaria ni cobro de tarjeta en divisa (~3% ESTIMADO).
