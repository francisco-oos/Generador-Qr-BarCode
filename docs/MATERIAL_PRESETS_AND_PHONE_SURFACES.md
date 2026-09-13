# Presets de materiales y superficies de teléfonos

Fecha de investigación: 2026-09-12

## 1. Propósito

Este documento define cómo Marking Studio maneja **ajustes de grabado** sin convertir referencias de Internet en parámetros de producción. El principio central es:

> **El ajuste que ya fue validado por el área en la misma grabadora, misma superficie y misma operación tiene prioridad.**

Marking Studio puede descubrir/importar esos ajustes desde LightBurn y conservarlos como evidencia. Los rangos de este documento sólo sirven para preparar un Material Test o una primera prueba sobre material de descarte.

## 2. Jerarquía de autoridad

1. `shop_validated_same_machine_same_material`: ajuste ya usado con éxito por el área, para la SCULPFUN y superficie exactas.
2. Recomendación específica del fabricante del láser/material, si realmente corresponde a esa combinación.
3. Rango investigado de referencia.
4. Material Test conservador y aprobación local.

Nunca se degrada automáticamente del nivel 1 al nivel 3: una actualización web no reemplaza un ajuste local comprobado.

## 3. Lo que SCULPFUN publica para la familia S9

SCULPFUN advierte expresamente que **no hay ajustes universales**: incluso piezas del mismo lote pueden reaccionar diferente. Para grabado con diodo, su guía usa como marco general potencias por debajo de las de corte y recomienda realizar pruebas de material. Si no existe muestra previa, propone iniciar de forma conservadora alrededor de `1000 mm/min` y `10 %` de potencia y avanzar mediante prueba.

La misma guía ofrece ejemplos, principalmente para S9, que sirven como **zona inicial**, no como preset final:

| Material / método | Referencia SCULPFUN | Tratamiento en Marking Studio |
|---|---|---|
| Plywood, grabado | 1000–2000 mm/min, 20–60 %, 1 pasada | rango de investigación |
| Cuero genuino, grabado | 1000–2000 mm/min, 20–60 % | rango de investigación + extracción |
| Vidrio con recubrimiento | 1000–2000 mm/min, 60–80 % | método indirecto; no extrapolar a teléfono ensamblado |
| Espejo por reverso | 1000–2000 mm/min, 30–80 % | método específico por reverso |
| Acero inoxidable con tratamiento | 800–1500 mm/min, 20–70 % | marcado superficial, no corte |
| Cerámica/azulejo con método de recubrimiento | 1000–2000 mm/min, rango muy amplio de potencia | Material Test obligatorio |
| Acrílico opaco oscuro, corte de referencia | 100–300 mm/min, 85 %, 4–8 pasadas | sólo referencia de corte; no teléfono |

Fuentes:

- SCULPFUN Settings guide: https://www.sculpfun.com/blogs/blog/settings-guide
- SCULPFUN S9 Pro 10W: https://www.sculpfun.com/products/sculpfun-s9-pro-10w-laser-engraving-machine

La S9 Pro publicada actualmente es un diodo de hasta 10 W y área 400 × 410 mm. Para **esta revisión S9 Pro**, el manual oficial enlazado por SCULPFUN indica foco fijo a **50 mm por debajo del borde inferior de la carcasa de aluminio del módulo**, usando la columna de medición de 50 mm suministrada. Esta referencia de 50 mm sustituye una interpretación anterior de 20 mm que no correspondía al manual S9 Pro revisado. El foco real del taller debe verificarse contra el hardware/manual que acompaña a su unidad.

## 4. LightBurn como herramienta de calibración

LightBurn incorpora `Laser Tools → Material Test` para generar una matriz que varía velocidad, potencia, intervalo, pasadas u otros parámetros. Los presets de Material Test pueden exportarse/importarse como `.lbmt`; LightBurn también mantiene Material Libraries `.clb` para ajustes reutilizables.

Marking Studio v0.6 puede:

- importar `.lbmt`;
- importar `.clb`;
- importar `.lbrn/.lbrn2`, `.lbset`, `.lbprefs` y `.lbzip`;
- detectar `material_test_presets.lbmt` y otros artefactos locales cuando el backend corre en la misma PC que LightBurn;
- preservar SHA-256, origen, fecha de captura y ajustes encontrados;
- asociar el preset capturado a un trabajo/lote.

Fuentes:

- LightBurn Material Test: https://docs.lightburnsoftware.com/latest/Reference/MaterialTest/
- LightBurn Material Library: https://docs.lightburnsoftware.com/latest/Reference/MaterialLibrary/
- LightBurn Preferences: https://docs.lightburnsoftware.com/latest/Reference/ManagingPreferences/

## 5. Materiales de alto riesgo o composición desconocida

No se publica un preset productivo genérico para los siguientes casos:

### PVC / vinilo / materiales clorados

**No usar.** SCULPFUN, xTool y Epilog advierten que los materiales con PVC/vinilo/cloro generan gases peligrosos y corrosivos.

### ABS

Marking Studio no asigna velocidad/potencia de producción. xTool advierte que puede fundirse, incendiarse y producir humos peligrosos.

### Policarbonato (PC)

No se trata como “plástico grabable genérico”. xTool incluye policarbonato entre los materiales que pueden liberar humos dañinos y presentar problemas térmicos.

### Goma/caucho desconocido

No basta con que visualmente sea “goma”. La formulación y aditivos deben conocerse o el área debe tener una prueba documentada exactamente sobre esa superficie.

### Fibra de vidrio / composite

“Fiberglass” no identifica por sí solo la resina, pintura o recubrimiento. No se crea un preset directo hasta conocer el composite o disponer de un ajuste local validado.

Fuentes de seguridad:

- xTool Safety Guide: https://support.xtool.com/article/354
- Epilog materiales inseguros: https://www.epiloglaser.com/es-mx/como-funciona/preguntas-frecuentes/materiales-peligrosos-para-maquinas-laser/
- SCULPFUN Settings guide: https://www.sculpfun.com/blogs/blog/settings-guide

## 6. Teléfonos: por qué no existe un preset “Xiaomi” o “rugged phone”

La carcasa cambia incluso dentro de una misma marca. El sistema exige **modelo + superficie exacta**.

### CUBOT KingKong 9

La ficha oficial confirma un equipo rugged de 390 g y batería no removible de 10600 mAh, pero no publica una composición química precisa de la superficie trasera. Por eso Marking Studio lo marca como `shop_validated_exact_surface_only`.

Fuente oficial: https://cubot.net/phones/rugged-phone/kingkong9-specs/94?l=en

Uso recomendado:

- si el área ya graba KingKong 9 con buen resultado, importar/capturar ese preset y nombrarlo por **modelo + zona física**;
- no extrapolar desde una funda aftermarket o desde otro CUBOT;
- verificar contraste/lectura del QR o Code 128 en una unidad de descarte / tapa equivalente antes de estandarizar.

### UMIDIGI BISON X10

UMIDIGI describe el BISON X10 con **AG matte fiberglass** y **rubber cushion**. Eso confirma que no es una única placa de plástico homogénea.

Fuente oficial: https://www.umidigi.com/page-umidigi_bisonx10_overview.html

Uso recomendado: mantener un preset local únicamente para la zona exacta ya validada; si se cambia de zona (fiberglass → goma), crear otro perfil/preset.

### Xiaomi / Redmi

Xiaomi demuestra por qué no debe existir un preset por marca:

- REDMI Note 14: Xiaomi indica tapa posterior **PC + PMMA**.
- REDMI Note 13 Pro+ 5G: Xiaomi indica tapa posterior **de vidrio**.

Fuentes oficiales:

- https://www.mi.com/ph/support/faq/details/KA-530059/
- https://www.mi.com/global/support/faq/details/KA-242965/

Dos equipos de la misma familia comercial pueden exigir decisiones de material completamente diferentes.

## 7. Estrategia recomendada para el primer piloto de teléfonos

Como el área **ya dispone de un ajuste visible que funciona**, la primera estrategia no es buscar potencia desde cero:

1. Identificar modelo exacto y zona donde ya graban.
2. Capturar el ajuste existente desde `.clb`, `.lbrn2`, `.lbmt` o registrar los valores actuales.
3. Guardarlo como `shop_validated_candidate` ligado a `SCULPFUN S9 Pro 10W + modelo + superficie`.
4. Mantener la misma configuración y cambiar primero **geometría/tamaño** del QR/barcode/texto.
5. Grabar muestra controlada.
6. Verificar lectura, contraste y daño cosmético.
7. Si falla lectura, modificar geometría antes de aumentar agresivamente energía.
8. Sólo después ajustar potencia/velocidad mediante Material Test.
9. Aprobar el preset como estándar local y conservar el historial.

## 8. Qué debe guardar cada preset aprobado

Un preset de producción debe registrar, como mínimo:

- `machine_profile_id`;
- modelo de láser / potencia óptica;
- material o equipo exacto;
- zona/superficie física;
- color/recubrimiento cuando afecte absorción;
- tipo de operación (line/fill/scan);
- velocidad;
- min/max power si aplica;
- intervalo / line interval;
- pasadas;
- modo dinámico/constante cuando aplique;
- Air Assist on/off;
- foco / spacer / offset si se usa;
- plantilla y tamaño de código;
- lector utilizado;
- resultado de primer intento de lectura;
- evidencia de prueba;
- fecha y operador;
- origen del preset (`shop`, `lbmt`, `clb`, etc.);
- SHA-256 del artefacto importado.

## 9. Alternativa segura cuando no conviene grabar el teléfono directamente

Usar una placa/etiqueta de activo apta para láser (por ejemplo, aluminio anodizado/recubierto cuya composición sea conocida), pegarla/fijarla bajo procedimiento aprobado y grabar ahí el QR + económico. Así la identidad y el sistema de plantillas permanecen iguales sin aplicar calor directamente a una superficie de composición incierta.

## 10. Regla final

La biblioteca `config/materials/material_reference_v1.json` es **informativa y de seguridad**. Los presets de producción provienen de la operación real y quedan en SQLite/material presets importados. El sistema nunca debe convertir automáticamente un rango web en un ajuste listo para disparar el láser.


## Evidencia de modo físico validado — v0.8.0

La biblioteca local no debe responder «qué potencia usa el plástico», sino «qué se probó en esta combinación concreta». Un preset puede conservar: máquina, material/superficie/modelo, velocidad/potencia/pasadas/foco/intervalo, `MarkingMode`, perfil de lector, intentos, lecturas correctas, resultado y una nota `validated_on`.

Jerarquía de confianza:

1. ajuste validado por el área sobre la misma máquina y superficie;
2. referencia específica del fabricante;
3. investigación;
4. Material Test.

La polaridad que funciona pertenece físicamente a la combinación material+máquina+acabado. Marking Studio permite guardarla en una plantilla por conveniencia operativa, pero `validated_on` debe recordar el contexto y **no convierte esa plantilla en una receta universal**.

Para un modo negativo, registrar también si hubo acabado (marcador/pintura), lector, intentos y éxitos. Un resultado parcial/fallido nunca debe mostrarse como preset validado.

## Evidencia de polaridad y arte de imagen — v0.8.0

Los presets del área pueden conservar el `MarkingMode` realmente probado y evidencia de lectura. Esto no convierte el material en una receta universal: máquina, superficie/modelo, preset, fecha y lector siguen siendo contexto necesario.

Los elementos `image` no heredan un preset especial ni una “receta para fotos”. El threshold/Floyd–Steinberg define geometría 1-bit, no energía del láser. Antes de adoptar un logo/imagen como estándar debe probarse sobre descarte con el preset del material correspondiente.
