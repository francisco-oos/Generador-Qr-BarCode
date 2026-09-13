# Reporte de pruebas — Server Oficina Marking Studio v0.5.0

Fecha de cierre: 2026-09-12

## Resultado general

**Estado de software: PASS / listo para piloto físico controlado.**

Esto significa que la generación, parsing, API, persistencia, licenciamiento, exportación, simulación de lectura, escalabilidad, interoperabilidad SVG y diagnóstico GRBL read-only pasaron en el host de validación. **No significa que un grabado físico específico esté aprobado**: potencia/velocidad/foco/contraste/material y repetibilidad del jig requieren la SCULPFUN real, las carcasas reales y el lector real.

## Matriz de pruebas ejecutadas

| Prueba | Resultado | Evidencia |
|---|---|---|
| Pytest completo | **41/41 PASS** | tests unitarios/integración |
| `compileall` app/scripts/tests | **PASS** | consola QA |
| JavaScript `node --check` | **PASS** | consola QA |
| Runtime/API `/api/health` | **PASS** | versión 0.5.0, licencia standalone válida |
| Compatibilidad/preflight | **PASS** | `qa/output/compatibility_report.json` |
| Simulación de lectura | **28/28 PASS** | Code128 + QR degradados |
| Decodificación lote INOVA 3×4 | **12/12 PASS** | 12 Code 128 distintos |
| Escalabilidad 1,200 registros | **PASS** | 100 cargas de 12 |
| 2,500 renders individuales | **PASS** | 499.4 marcas/s en este host |
| GRBL serial simulado | **PASS** | sólo `$I` y `$$`; 0 comandos prohibidos |
| SVG interop XML/svglib/Inkscape | **PASS** | 5 plantillas + lote 12 + SVG de calibración |
| Importación de archivos de configuración | **PASS** | `.clb`, `.lbmt`, `.psh`, dump GRBL |
| Guías de jig ausentes de SVG productivo | **PASS** | `guide_in_production=false` |
| UI/API fallback | **PASS** | health, index, modo guiado/experto, catálogo, calibración |
| Browser E2E Chromium | **SKIP_POLICY** | bloqueado por política del runtime, no por error de app |
| Bash syntax launchers Linux/macOS | **PASS** | `bash -n` |
| ZIP reextraído y verificado | **PASS** | hashes 159/159, compile, 41 tests, JS, compatibilidad, importadores, SVG y API health |

## Pruebas de captura y datos

La suite cubre:

- carga multipart HTTP de un CSV real de 1,200 registros mediante la API;

- captura manual con prefijo/sufijo;
- CSV sin duplicar prefijo por defecto;
- CSV UTF-8 BOM;
- separadores coma, punto y coma y tab;
- campos entrecomillados;
- archivos de 1,200 y 5,000 registros;
- generación de serie >1,000;
- conciliación física que bloquea discrepancias;
- exportación ZIP con SVG/PNG/manifiestos;
- verificación de escaneo y actualización de histórico.

## Generación/lectura de códigos

La simulación renderiza a raster y usa un decodificador independiente. Para INOVA, Sercel, teléfono y QR genérico se probaron variantes:

- pristine;
- reducción 50 %;
- blur 0.6;
- blur 1.0;
- rotación 2°;
- contraste reducido al 55 %;
- abrasión digital delgada.

Resultado: **28/28 lecturas correctas**. Esto valida la geometría digital, no la calidad óptica del láser sobre una carcasa real.

## Lote 3×4

La imagen completa de 12 posiciones contiene:

`Q00525499` a `Q00525510`.

El decodificador recuperó los **12/12 Code 128** sin faltantes ni códigos inesperados. La salida productiva no contiene rectángulos del jig; esos viven sólo en `preview_DO_NOT_ENGRAVE.svg`.

## Escalabilidad

Resultados de esta corrida:

- dataset: 1200 registros;
- capacidad jig: 12;
- cargas físicas: 100;
- 2,500 renders: 5.005 s;
- rendimiento observado: 499.5 marcas/s;
- incremento de RSS observado: ~5.62 MiB;
- batch vectorial de 1,200: 2.433 s;
- PNG de cama completa 300 DPI: 5.69 s.

Estos tiempos describen este host Linux de validación y no son una promesa de rendimiento idéntico en la PC del taller.

## Interoperabilidad SVG

Todas las plantillas fueron:

1. parseadas como XML;
2. rasterizadas con `svglib`;
3. abiertas/exportadas mediante Inkscape disponible en el host.

Las 5 plantillas, el batch 3×4 y el SVG `CALIBRATION ONLY` pasaron. El SVG de calibración contiene marcas P0/PX/PY y una leyenda explícita para evitar confundirlo con una salida productiva. Esto reduce el riesgo de entregar un SVG sintácticamente válido pero incompatible con herramientas vectoriales comunes.

## Diagnóstico GRBL

El simulador serial recibió exactamente:

```text
$I
$$
```

No recibió movimiento, homing, laser/spindle, setting-write ni potencia. Se parsearon correctamente `$30`, `$32`, `$130`, `$131`.

## Configuraciones de software de máquina

Además de fixtures unitarios, se cargaron archivos de ejemplo reales del paquete mediante los importadores de producción; los 4/4 casos pasaron: LightBurn `.clb`, LightBurn `.lbmt`, LaserGRBL `.psh` y dump de `$I/$$`.

Se probaron parsers/rutas para:

- LightBurn `.clb`, `.lbmt`, `.lbset`, `.lbrn/.lbrn2`, `.lbprefs`, `prefs.ini`, `.lbzip`;
- LaserGRBL `.psh`;
- captura manual de preset local;
- rutas de descubrimiento Windows/Linux/macOS cuando aplica.

El programa archiva la copia importada con hash y no reescribe el archivo original.

## Calibración

Las 5 definiciones de jig generan `P0/PX/PY`. Las pruebas unitarias confirman:

- caso perfecto;
- detección de traslación;
- detección de escala;
- detección de desviación angular/escuadra.

El evaluador es diagnóstico y nunca modifica automáticamente la máquina.

## UX guiada y experta

La UI incluye:

- **Modo guiado**: flujo corto, menos controles técnicos;
- **Modo experto**: JSON de plantilla/jig, calibración avanzada, importadores y diagnóstico.

El navegador Chromium del entorno de ejecución bloqueó `localhost` con `ERR_BLOCKED_BY_ADMINISTRATOR`, por lo que el E2E visual se registra correctamente como **SKIP_POLICY**, no como PASS falso. El fallback FastAPI/HTML sí pasó y la sintaxis JS fue validada con Node.

## Compatibilidad por sistema operativo

El host realmente ejecutado fue Linux x86_64 / Python 3.13.5. Existen launchers y CI declarada para Windows, Linux y macOS con Python 3.12/3.13. No se afirma ejecución física Windows/macOS desde este host.

- Linux/macOS shell scripts: sintaxis comprobada.
- Windows batch: revisado y cubierto por la matriz CI declarada; requiere runner/PC Windows para certificación real.
- Marking Studio puede vivir en Linux aunque la estación use Sculpfun Space/LightBurn en Windows/macOS.

## Corrección de enfoque S9 Pro

Durante esta revisión se corrigió una referencia previa de 20 mm. El manual oficial **SCULPFUN S9 Pro** enlazado en el centro de descargas especifica foco fijo **50 mm debajo del borde de la carcasa de aluminio del módulo** y columna de medición de 50 mm. La documentación y el perfil de máquina de v0.5 ya reflejan 50 mm.

## Validación del paquete final

El ZIP final se extrajo en un directorio temporal independiente y se comprobó como si fuera una entrega recibida:

- `PROJECT_FILE_HASHES.sha256`: **159/159 PASS**;
- `compileall`: **PASS**;
- `pytest`: **41/41 PASS**;
- JavaScript: **PASS**;
- compatibilidad/preflight: **PASS**;
- importadores de configuración: **4/4 PASS**;
- interoperabilidad SVG: **PASS**;
- `/api/health`: **200 / v0.5.0 / licencia standalone válida**.

Esta prueba detecta, entre otras cosas, archivos omitidos del empaquetado, diferencias entre el árbol fuente y el ZIP y dependencias accidentales de archivos de runtime locales.

## Pendientes que sólo se pueden cerrar físicamente

1. Capturar el preset real que el área ya usa hoy.
2. Medir la base/jig real y sustituir offsets/pitch estimados.
3. Grabar material de descarte/carcasa fuera de servicio.
4. Probar Code 128 con el LS2208 real.
5. Probar QR de teléfono con el lector/cámara previsto.
6. Confirmar que la superficie no se deforma ni degrada.
7. Repetir al menos 20 lecturas consecutivas por estándar candidato.
8. Aprobar y versionar el preset/jig final.

## Conclusión

La **herramienta de software** cumple el alcance previsto para pasar a piloto de taller. La frontera física está explícitamente bloqueada hasta disponer de máquina/material/lector reales; esto evita declarar como “validado” algo que sólo se simuló digitalmente.
