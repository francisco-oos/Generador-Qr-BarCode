# Investigación, razonamiento, decisiones y descartes

Fecha de revisión: 2026-09-12

## 1. Alcance investigado

Se investigó la cadena completa que afecta al problema:

- SCULPFUN S9 Pro 10W y naturaleza de un diodo azul;
- software de máquina: LightBurn y LaserGRBL;
- capacidades de barcode/QR y producción por lotes;
- lector observado Zebra/Symbol LS2208;
- identidad física INOVA/Sercel mostrada en fotografías;
- superficies de teléfonos CUBOT, UMIDIGI y Xiaomi/Redmi;
- captura de settings ya probados por el taller;
- materiales y riesgos;
- portabilidad Windows/Linux/macOS;
- escalabilidad a miles de IDs;
- futura integración con Server Oficina.

## 2. Problema real, no sólo “generar un QR”

El problema operativo no es dibujar un barcode. Es conservar simultáneamente:

1. **identificación humana rápida** — texto grande cuando hay pocas piezas;
2. **identificación legible por máquina** — Code 128/QR/Data Matrix;
3. **correspondencia con la pieza física** — evitar grabar el serial correcto en la pieza equivocada;
4. **repetibilidad** — dimensiones y posición iguales entre operadores;
5. **auditoría** — saber qué se generó, con qué plantilla/preset y si se verificó;
6. **compatibilidad con el taller** — reutilizar SCULPFUN, LightBurn y lectores existentes.

Por eso la arquitectura incluye plantilla + jig + conciliación + exportación + verificación, no sólo un generador gráfico.

## 3. SCULPFUN S9 Pro 10W

Fuente oficial: https://www.sculpfun.com/products/sculpfun-s9-pro-10w-laser-engraving-machine

La ficha publicada actualmente indica:

- hasta 10 W ópticos;
- área de grabado 400 × 410 mm;
- foco nominal 0.06 mm;
- sistema de enfoque fijo/deslizante.

El manual oficial **S9 Pro** enlazado en el centro de descargas de SCULPFUN aclara un dato operativo decisivo: el foco está a **50 mm** bajo el borde inferior de la carcasa de aluminio del módulo y se suministra una columna de medición de 50 mm. Se corrigió en v0.5 una referencia anterior de 20 mm que no correspondía a este manual S9 Pro.

Fuente adicional de parámetros: https://www.sculpfun.com/blogs/blog/settings-guide

La guía oficial enfatiza que no existen settings universales y que deben hacerse Material Tests. También describe potencia dinámica como opción normalmente adecuada para grabado con GRBL compatible.

### Decisión

No codificar velocidades/potencias “universales” dentro de las plantillas de identidad. Esos parámetros pertenecen a un **preset de material/máquina** separado.

Esto permite que el mismo `INOVA_QUANTUM_V1` use un preset del taller hoy y otro futuro si cambia carcasa, láser o acabado, sin alterar la identidad ni geometría.

## 4. LightBurn

Fuentes oficiales:

- Bar Code: https://docs.lightburnsoftware.com/2.1/Reference/BarCode/
- Variable Text: https://docs.lightburnsoftware.com/2.0/Reference/VariableText/
- Material Test: https://docs.lightburnsoftware.com/latest/Reference/MaterialTest/
- Material Library: https://docs.lightburnsoftware.com/latest/Reference/MaterialLibrary/
- Preferences: https://docs.lightburnsoftware.com/latest/Reference/ManagingPreferences/
- instalación/OS: https://docs.lightburnsoftware.com/2.1/GetStarted/InstallLightBurn/

LightBurn ya sabe crear barcodes, manejar Variable Text, CSV, Material Test, Cut Settings, framing y control GRBL.

### Alternativa descartada: reemplazar LightBurn

Se descartó construir un controlador completo porque duplicaría funciones críticas y aumentaría riesgo. Marking Studio debe aportar lo que LightBurn no conoce: identidad del activo, reglas corporativas, histórico, plantilla por familia, conciliación física y conexión futura a Tracking Core.

### Integración elegida

- SVG milimétrico como formato autoritativo;
- PNG como fallback raster;
- importadores read-only para `.clb`, `.lbmt`, `.lbset`, `.lbprefs`, `.lbrn2`, `.lbzip`;
- GRBL read-only `$I/$$` para inventariar controller settings;
- no streaming de producción.

## 5. Captura de ajustes ya existentes

El usuario confirmó que el taller ya produce números visibles. Por eso la primera fuente de verdad debe ser su configuración real.

LightBurn reparte información entre:

- controlador/Machine Settings;
- Cut Settings de capas;
- Material Libraries;
- Material Test presets;
- proyectos;
- preferencias y bundles.

Marking Studio v0.6 conserva esos artefactos con hash y extrae los campos legibles. La aplicación no intenta escribirlos de vuelta.

### Descubrimiento automático

Si backend y LightBurn están en la misma PC, se escanean rutas convencionales de preferencias con profundidad/cantidad limitadas. Si están en máquinas distintas, el usuario sube el export manualmente. Esto evita una falsa promesa de “leer el PC remoto” desde un navegador.

## 6. Zebra / Symbol LS2208

Fuente oficial: https://www.zebra.com/us/en/products/spec-sheets/scanners/general-purpose-scanners/ls2208.html

Zebra documenta:

- lector láser 1D, single line;
- 100 scans/s;
- mínimo 20 % de diferencia de contraste;
- soporte de Code 128 entre otras simbologías 1D.

### Decisión

Para nodos que deben pasar por el flujo existente, **Code 128 + texto visible** es el primer estándar. QR/Data Matrix no sustituyen ese flujo mientras el lector sea 1D.

Los QR sí encajan bien en teléfonos/activos consultados mediante cámara o lector 2D.

## 7. Identidad INOVA

Las fotografías operativas muestran:

- etiqueta de fábrica con texto + 1D + 2D;
- unidades reparadas/restauradas donde se escribía un número reducido con marcador;
- proceso actual con grabado visible de forma `Q00xxxxxx`.

El usuario indicó que el sufijo `-xx` de ciertas etiquetas no se ha requerido en la operación.

### Decisión

- ID operativo inicial: `Q00xxxxxx`;
- texto visible: mismo ID;
- Code 128: mismo ID;
- `-xx`: dato secundario opcional si está documentado; nunca se inventa.

### Captura manual vs CSV

La regla de prefijo es contextual:

- captura manual `525499` → plantilla puede asegurar `Q00` → `Q00525499`;
- CSV con `Q00525499` → se usa tal cual por defecto.

Esto evita dobles prefijos y permite conservar listas autorizadas.

## 8. Sercel

La plantilla inicial conserva `Code 128 + ID visible` para interoperar con el lector actual. Existe una plantilla Data Matrix experimental, pero no se declara estándar productivo hasta contar con lector 2D y comprobar el contenido real del símbolo de fábrica.

## 9. Teléfonos y materiales

### CUBOT KingKong 9

Fuente oficial: https://cubot.net/phones/rugged-phone/kingkong9-specs/94?l=en

La ficha confirma batería de 10600 mAh no removible, pero no define con precisión química toda la superficie trasera. Por tanto, no se asigna un preset web de plástico.

### UMIDIGI BISON X10

Fuente oficial: https://www.umidigi.com/page-umidigi_bisonx10_overview.html

UMIDIGI indica **AG matte fiberglass + rubber cushion**. Eso refuerza que un teléfono rugged puede presentar varias superficies/composites.

### Xiaomi / Redmi

Fuentes oficiales:

- REDMI Note 14: https://www.mi.com/ph/support/faq/details/KA-530059/
- REDMI Note 13 Pro+ 5G: https://www.mi.com/global/support/faq/details/KA-242965/

El primero usa PC + PMMA en la tapa trasera; el segundo declara vidrio. **Marca o familia comercial no basta para elegir un ajuste.**

### Decisión

Los teléfonos requieren `marca + modelo exacto + zona/superficie + preset local`. Si el área ya graba ese modelo, se captura su ajuste y se usa como baseline. Si no se conoce la composición, se prefiere una placa de activo apta para láser.

## 10. Seguridad de materiales

Fuentes:

- SCULPFUN: https://www.sculpfun.com/blogs/blog/settings-guide
- xTool: https://support.xtool.com/article/354
- Epilog: https://www.epiloglaser.com/es-mx/como-funciona/preguntas-frecuentes/materiales-peligrosos-para-maquinas-laser/

PVC/vinilo/clorados quedan bloqueados. ABS, policarbonato, composites y plásticos desconocidos no reciben pares velocidad/potencia de producción en el catálogo. La aplicación distingue entre información investigada y preset aprobado.

## 11. Lotes y jigs

Un dataset de 1,200 IDs no implica un “lienzo de 1,200 piezas”. El motor separa dataset de capacidad física. Con 12 posiciones se crean 100 cargas.

Cada slot conserva:

- índice de posición;
- fila del dataset;
- ID esperado;
- ID físico confirmado;
- resultado de conciliación.

La exportación se bloquea ante mismatch cuando la política está activa.

## 12. Verificación posterior

Después de grabar:

`ID esperado == valor leído`.

El texto visible se mantiene porque en inspecciones pequeñas puede ser más rápido que un lector. El código existe para automatizar lotes y reducir transcripción.

## 13. Licenciamiento

La candidata standalone usa licencia local firmada. La frontera está preparada para que Server Oficina sea posteriormente autoridad de licencia y sincronización de eventos, sin convertir la base SQLite local en una BD compartida de red.

## 14. Portabilidad

Marking Studio es Python/FastAPI + HTML/JS y tiene launchers Windows/Linux/macOS. LightBurn tiene su propia compatibilidad: versiones actuales 2.x en Windows/macOS y 1.7.08 como última compatible con Linux. LaserGRBL es Windows.

Por diseño, Server Oficina puede vivir en Linux mientras el control físico permanece en la PC Windows del taller.



## Sculpfun Space como ruta de handoff

SCULPFUN publica actualmente **Sculpfun Space** como software gratuito para sus máquinas no-galvo. Admite SVG/PNG, creación de barcode/QR, arrays, batch processing, presets y prueba de materiales. Esta investigación cambió la arquitectura de entrega: Marking Studio no queda atado a LightBurn. Para un operador inexperto puede entregar SVG a Sculpfun Space; para un experto, LightBurn sigue siendo una ruta potente.

Fuente: https://www.sculpfun.com/pages/software

### Decisión

Mantener la frontera por archivos y presets. No integrar control directo de potencia/movimiento en Marking Studio sólo porque Sculpfun Space o LightBurn sepan hacerlo.

## LaserGRBL y ajustes existentes

La base de materiales de LaserGRBL en Windows se almacena en archivos `.psh` XML bajo `%APPDATA%\LaserGRBL`. Marking Studio 0.6 incluye detección/importación read-only de `UserMaterials.psh`/`StandardMaterials.psh`, además de captura manual de ajustes del taller. Esto permite preservar conocimiento existente aunque el área no use LightBurn Material Library.

## 15. Decisiones descartadas

- **Grabar sólo QR en nodos:** descartado por lector 1D existente y necesidad de inspección visual.
- **Eliminar el texto visible:** descartado; el humano sigue siendo una ruta útil de contingencia.
- **Guardar responsable/proyecto dentro del QR:** descartado porque cambian; el código representa identidad estable.
- **Inventar `-xx` de INOVA:** descartado por falta de evidencia y porque no es requisito operativo actual.
- **Usar un preset por marca de teléfono:** descartado por variación de materiales.
- **Controlar el láser directamente desde Marking Studio:** descartado en esta etapa por seguridad, duplicidad y mantenimiento.
- **Confiar sólo en el orden del CSV:** descartado; se exige conciliación con pieza física.
- **Declarar el jig de la foto como dimensionalmente calibrado:** descartado; la foto inspira topología, pero el pitch/offset real debe medirse.

## 16. Criterio de terminación del software vs aprobación física

El software puede cerrarse técnicamente con tests de generación, parsing, seguridad, compatibilidad y decodificación. La aprobación física requiere la SCULPFUN real, el material real y el lector real. Esa frontera queda documentada y no se sustituye con simulación.


## Actualización 2026-09-12 — Steren COM-597 real del área

La etiqueta inferior visible en la fotografía identifica un **Steren COM-597** (5 V, 300 mA USB). Esto corrige la hipótesis conservadora de un Steren 1D genérico para ese puesto. El COM-597 es un imager 1D/2D y admite Code 128, QR y Data Matrix. Se conserva el perfil 1D genérico porque podrían existir otros lectores en operación.

Decisión: no cambiar las plantillas por esta capacidad extra. INOVA/Sercel continúan con Code 128 + texto por velocidad e inspección visual; teléfonos continúan con QR + económico. El COM-597 puede verificar ambos flujos con un solo dispositivo.
