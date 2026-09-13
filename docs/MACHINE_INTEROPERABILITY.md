# Interoperabilidad con SCULPFUN, LightBurn, Sculpfun Space, LaserGRBL y futuras máquinas

Fecha de revisión: 2026-09-12  
Versión del proyecto: 0.6.2

## 1. Principio de arquitectura

Marking Studio es la capa de **datos, plantillas, conciliación, auditoría y generación**. No reemplaza al software que controla físicamente el láser.

```text
Marking Studio
  ├─ identidad / CSV / futura BD
  ├─ QR / Code 128 / Data Matrix / texto
  ├─ tamaño y posiciones del jig
  ├─ preset/material referenciado
  ├─ conciliación física
  ├─ histórico
  └─ SVG/PNG + manifest
            ↓
Sculpfun Space / LightBurn / LaserGRBL / software de máquina
            ↓
controlador GRBL / otra controladora
            ↓
grabado físico
```

La separación evita duplicar funciones críticas como origen, framing, foco, velocidad, potencia, movimiento, pausa, paro y seguridad. Marking Studio puede diagnosticar o leer configuraciones, pero **no enciende el láser ni mueve ejes**.

## 2. SCULPFUN S9 Pro 10W instalada

Fuentes oficiales revisadas:

- Centro de descargas: https://www.sculpfun.com/pages/download-center
- Manual S9 Pro enlazado por SCULPFUN: `S9_PRO_-2024.10.30.pdf`
- Guía de ajustes: https://www.sculpfun.com/blogs/blog/settings-guide

El perfil del proyecto usa área nominal de **400 × 410 mm** hasta contrastarla con la máquina real y con `$130/$131`.

### Corrección importante sobre enfoque

El manual oficial **S9 Pro** consultado especifica que:

- la distancia focal es fija;
- el foco se encuentra **50 mm directamente debajo del borde inferior de la carcasa de aluminio del módulo láser**;
- SCULPFUN suministra una **columna de aluminio de 50 mm** para ajustar el foco.

Por lo tanto, una referencia anterior de 20 mm se eliminó del proyecto. Para esta máquina instalada se debe seguir el manual S9 Pro de 50 mm o, si el taller posee una revisión física diferente, registrar su procedimiento comprobado como evidencia local. Nunca se mezclan cifras de otra revisión S9 sin comprobar el hardware real.

## 3. Comunicación con la máquina

### Producción

**No hay streaming directo de trabajos en esta candidata.** Marking Studio exporta:

- SVG en milímetros: salida vectorial recomendada;
- PNG 300/600 DPI: alternativa raster;
- manifiesto, plantilla, jig y preset referenciado.

El operador abre la salida en el software autorizado, aplica o verifica el preset del material, usa `Frame`/previsualización, confirma foco y origen y ejecuta desde ese software.

### Diagnóstico GRBL

El acceso serial directo está limitado por código a consultas read-only:

```text
$I
$$
```

No se envían comandos de movimiento, homing, potencia, láser, spindle ni escritura de parámetros. Las pruebas verifican que no aparezcan `G0`, `G1`, `M3`, `M4`, `M5`, `$H`, `$32=...` ni comandos `S...`.

### Propiedad del puerto

LightBurn, Sculpfun Space, LaserGRBL y Marking Studio no deben abrir el mismo puerto serial simultáneamente. Para un diagnóstico:

1. detener cualquier trabajo;
2. desconectar/cerrar el puerto en el software de máquina;
3. leer `$I/$$` desde Marking Studio;
4. guardar la captura;
5. cerrar el probe;
6. reconectar el software de producción.

## 4. Sculpfun Space

Fuente oficial: https://www.sculpfun.com/pages/software

SCULPFUN publica Sculpfun Space como software gratuito para sus máquinas no-galvo y documenta:

- Windows 10+ y macOS 13+;
- importación de JPG, PNG, SVG, DXF y PLT;
- creación de texto, códigos de barras y QR;
- array layout y batch processing;
- presets de materiales;
- prueba de parámetros/material;
- control de potencia, velocidad, line spacing y pasadas.

Esto lo hace un **handoff válido** para Marking Studio, especialmente para un operador principiante: Marking Studio entrega el SVG/PNG ya normalizado y conserva identidad, conciliación e histórico; Sculpfun Space conserva el control de máquina.

El manual de Sculpfun Space también expone consola/GRBL y biblioteca de materiales. Marking Studio no intenta reemplazar esas funciones ni escribir en su configuración interna hasta que exista un formato estable/documentado que podamos importar de forma segura.

## 5. LightBurn

Fuentes oficiales:

- Material Test: https://docs.lightburnsoftware.com/latest/Reference/MaterialTest/
- Primer Material Test: https://docs.lightburnsoftware.com/latest/GetStarted/FirstMaterialTest/
- Coordinates/Origin: https://docs.lightburnsoftware.com/2.0/Reference/CoordinatesOrigin/
- Material Library: https://docs.lightburnsoftware.com/latest/Reference/MaterialLibrary/
- instalación/compatibilidad: https://docs.lightburnsoftware.com/2.1/GetStarted/InstallLightBurn/

Marking Studio puede leer/importar, sin reescribir el original:

- `.clb` — Material Library;
- `.lbmt` — Material Test presets;
- `.lbset` — Machine Settings backup;
- `.lbprefs` / `prefs.ini` — preferencias/rutas legibles;
- `.lbrn/.lbrn2` — Cut Settings de proyectos;
- `.lbzip` — User Bundle.

La detección automática sólo aplica cuando el backend corre en la **misma computadora** que LightBurn. Si Server Oficina vive en otra máquina, se exporta/sube el artefacto desde la estación de grabado.

### Posicionamiento recomendado para jigs

LightBurn diferencia `Current Position`, `User Origin` y `Absolute Coordinates`. En una estación abierta donde homing/limit switches no estén confirmados, el procedimiento inicial es:

1. fijar mecánicamente el jig;
2. usar un punto P0 físico repetible;
3. trabajar con `Current Position` o `User Origin`;
4. ejecutar `Frame` antes de cada corrida;
5. usar `Absolute Coordinates` sólo después de validar homing/origen fijo de la instalación real.

La propia documentación de LightBurn advierte que Absolute Coordinates requiere un origen fijo/homing confiable.

## 6. LaserGRBL

Referencias:

- proyecto/software: https://github.com/arkypita/LaserGRBL
- base de materiales del usuario: `%APPDATA%\LaserGRBL\UserMaterials.psh`

Marking Studio 0.6 puede detectar/importar en Windows, en modo read-only:

- `UserMaterials.psh`;
- `UserMaterial.psh` (compatibilidad con variantes históricas de nombre);
- `StandardMaterials.psh`.

Los `.psh` son XML y se convierten a presets portables cuando contienen campos reconocibles de material, operación, velocidad, potencia y ciclos/pasadas. La copia importada se archiva con SHA-256.

LaserGRBL queda como software externo de producción; Marking Studio conserva PNG/SVG según el flujo disponible y no automatiza movimiento ni disparo.

## 7. Calibración, jigs y puntos de referencia

Marking Studio genera tres puntos diagnósticos por jig:

- `P0`: origen físico;
- `PX`: referencia lejana del eje X;
- `PY`: referencia lejana del eje Y.

Con mediciones reales puede calcular:

- traslación del origen;
- escala X/Y;
- ángulo del eje X;
- ortogonalidad/escuadra.

El análisis es **diagnóstico**. No corrige pasos/mm, no mueve la máquina y no altera el jig automáticamente. La corrección sólo se incorpora tras medir y aprobar el montaje físico.

## 8. Futuras grabadoras

Para otra máquina se mantienen tres capas independientes:

1. **Handoff por archivo**: SVG/PNG u otro formato aceptado.
2. **Importador de configuración**: biblioteca/proyecto/preset documentado del fabricante/software.
3. **Diagnóstico de controlador**: sólo si existe protocolo documentado y con lectura separable de las acciones de producción.

DSP/Ruida, galvo o controladores propietarios no se tratan como GRBL por inferencia.

## 9. Qué significa “compatible” en esta entrega

- Generación SVG/PNG: verificada digitalmente.
- SVG: parseado y rasterizado por librería independiente e Inkscape en el host de validación.
- Parsing LightBurn/LaserGRBL: verificado con fixtures y tests.
- GRBL read-only: verificado con puerto serial simulado/PTY.
- UI/API: prueba estática/API; navegador real se ejecuta cuando el entorno permite navegación localhost.
- Grabado físico sobre SCULPFUN real: **pendiente de aceptación en taller**; ninguna simulación reemplaza esa prueba.
