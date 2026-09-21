# Handoff de software y conservación de ajustes de máquina

Fecha: 2026-09-12  
Versión: 0.7.0

## Responsabilidades

### Marking Studio

Es responsable de:

- identidad de activo;
- reglas de prefijo/sufijo;
- plantilla visual;
- QR / Code 128 / Data Matrix / texto;
- importación CSV y series autorizadas;
- jig/posición;
- conciliación física;
- preset referenciado;
- histórico y verificación posterior;
- exportación SVG/PNG/manifest.

### Software de máquina

Sculpfun Space, LightBurn o LaserGRBL mantienen:

- conexión real con el controlador;
- origen y movimiento;
- Frame/previsualización;
- velocidad/potencia/pasadas reales;
- pausa/stop;
- ejecución del láser;
- seguridad operacional.

Esta frontera reduce riesgo y evita implementar un segundo controlador láser dentro de Server Oficina.

## Ruta recomendada para usuario inexperto

**Marking Studio modo Guiado → SVG → Sculpfun Space o LightBurn → Frame → grabar → escanear.**

Sculpfun Space es una opción especialmente simple porque SCULPFUN lo publica como gratuito, compatible con sus máquinas no-galvo, con SVG, barcode/QR, array, batch y material presets. Marking Studio sigue siendo útil porque añade las reglas empresariales y la trazabilidad que el software del láser no conoce.

Fuente: https://www.sculpfun.com/pages/software

## Ruta recomendada para usuario experto

**Marking Studio modo Experto → importar presets / diagnóstico GRBL read-only / calibración P0-PX-PY → exportación → LightBurn/Sculpfun Space.**

El modo experto muestra información que puede confundir a un operador ocasional, pero no desbloquea comandos peligrosos: el probe GRBL sigue siendo `$I`/`$$` únicamente.

## Adoptar los ajustes que el área ya tiene

### LightBurn

El sistema puede descubrir/importar:

- `.clb` Material Library;
- `.lbmt` Material Test;
- `.lbrn/.lbrn2` proyectos/capas;
- `.lbset` Machine Settings backup;
- `.lbprefs` y `prefs.ini`;
- `.lbzip` bundles.

LightBurn documenta que los presets Material Test pueden exportarse/importarse como `.lbmt` y que `material_test_presets.lbmt` está en su carpeta de preferencias.

Fuente: https://docs.lightburnsoftware.com/latest/Reference/MaterialTest/

### LaserGRBL

En Windows, Marking Studio busca la base de materiales bajo `%APPDATA%\LaserGRBL`, incluyendo `UserMaterials.psh` y `StandardMaterials.psh`. Los campos XML reconocidos se convierten a presets internos y se conserva una copia con hash.

Fuente del proyecto: https://github.com/arkypita/LaserGRBL

### Captura manual

Si el operador ve los parámetros en pantalla pero no sabe exportarlos, puede registrar desde **Materiales → Capturar ajuste del área**:

- equipo/superficie;
- máquina;
- velocidad;
- potencia;
- pasadas;
- intervalo;
- referencia de foco;
- M3/M4/unknown;
- notas;
- `validado` o `borrador`.

Esto permite convertir conocimiento informal del taller en un preset versionable sin obligar a conocer XML o carpetas internas.

## Lectura del controlador

El probe de Marking Studio sólo lee:

- `$I`: información de build;
- `$$`: configuración del controlador.

Sirve para observar `$30`, `$32`, `$130`, `$131` y otros parámetros, pero **no revela por sí solo la potencia/velocidad de una capa**, porque esos ajustes pertenecen al software/proyecto/material preset.

## Exportación

### SVG

Es el formato autoritativo para geometría vectorial. Los archivos se generan con dimensiones físicas en `mm`. Se probaron con parser XML, svglib e Inkscape.

### PNG

Se genera como fallback raster y para inspección. No debe utilizarse para inferir medidas sin respetar su DPI.

### Preview del jig

`preview_DO_NOT_ENGRAVE.svg` puede mostrar la base/slots para que el operador entienda la colocación, pero las guías no aparecen en `engraving/batch.svg`.

## Comunicación futura con Server Oficina

Cuando Marking Studio se conecte a Tracking Core, la estación de grabado debería comportarse como cliente/nodo autorizado:

1. obtiene trabajo/IDs;
2. prepara y concilia posiciones;
3. graba mediante software local;
4. verifica escaneo;
5. devuelve resultado, plantilla, preset, operador, estación y hashes.

No es necesario exponer directamente el USB del láser al servidor central.


## Ruta experimental v0.10: control GRBL directo

La ruta histórica por archivo permanece soportada y es la referencia estable. La rama v0.10 agrega una alternativa **experimental** en Laser Design Studio para el perfil SCULPFUN S9 Pro:

1. producir o cargar geometría saneada;
2. seleccionar un preset local marcado como validado en la misma máquina/superficie;
3. compilar un job interno;
4. seleccionar el puerto serial;
5. ejecutar Frame con M5;
6. verificar físicamente límites/material/protección;
7. Start;
8. supervisar RUNNING/HOLD/DRAINING hasta GRBL Idle;
9. escanear/verificar cuando aplique.

El navegador no envía G-code libre. El backend genera las órdenes desde geometría validada y reconsulta $I/$$ antes de una ejecución energizada. No escribe automáticamente $30, $32, pasos/mm, homing ni límites.

LightBurn, Sculpfun Space y LaserGRBL continúan disponibles en paralelo y no dependen de esta función experimental.
