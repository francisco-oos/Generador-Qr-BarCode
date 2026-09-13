# Reporte de pruebas — Server Oficina Marking Studio v0.8.0 final

**Fecha:** 2026-09-13  
**Host:** Linux x86_64 · Python 3.13.5

## Suite automatizada

`pytest --collect-only`: **196 pruebas**.

La suite fue ejecutada por grupos por el límite del runner. Todos los grupos terminaron PASS. Después de los últimos cambios se repitieron específicamente las pruebas de `image`, polaridad, frontend y contrato documental.

Cobertura funcional relevante:

- API, licencia y configuración;
- CSV/XLSX, hojas, mapping y transformaciones;
- Code128/Code39/QR/Data Matrix;
- SVG editable/productivo, capas e IDs únicos;
- diseñador, undo/redo, snap, alineación y selección múltiple;
- jigs, calibración y conciliación física;
- polaridad positiva/negativa y cuatro combinaciones scope/field;
- preflight positivo canónico;
- kerf=0 y compensación medida;
- manifiestos/histórico/sufijos negativos;
- biblioteca de presets/evidencia;
- **elemento imagen PNG/JPG/SVG**, sanitización, dithering/threshold, solapamiento con quiet zone y preview API;
- escalabilidad.

## Verificaciones auxiliares

| Verificación | Resultado |
|---|---|
| `compileall` | PASS |
| `node --check app.js` | PASS |
| `compatibility_check.py` | PASS |
| `qa_quality_preflight.py` | PASS |
| `qa_scan_simulation.py` | 28/28 PASS |
| `qa_batch_decode.py` | PASS, 12/12 con svglib y CairoSVG |
| `qa_svg_interop.py` | PASS, Inkscape + svglib/CairoSVG |
| `qa_configuration_imports.py` | 4/4 PASS |
| `qa_grbl_serial_simulator.py` | PASS, sólo `$I`/`$$` |
| `qa_browser_smoke.py` | API/HTML PASS; navegador SKIP_POLICY |

## Benchmark

- 1,200 registros → 100 cargas de jig de 12.
- 2,500 renders → 2.108 s (~1,185.9/s).
- delta RSS observado: ~0.12 MiB en el benchmark.
- 1,200 marcas vectoriales: 0.979 s.
- PNG cama 300 dpi: 5.68 s.

## Invariantes de seguridad comprobados

- `direct_laser_job_streaming=false`.
- GRBL de diagnóstico limitado a `$I` y `$$`.
- preflight no evalúa geometría negativa.
- IDs únicos en lotes.
- `_NEGATIVE` / `_NEGATIVE_2PASS` evita confundir artefactos de ablación.
- `negative/all + editable` se rechaza.
- imagen no acepta URLs/scripts ni participa en la clasificación de código.

## Lo que estas pruebas NO demuestran

No certifican comportamiento físico del láser, material, kerf, contraste, abrasión, lectura del COM-597 sobre grabado real ni calidad fotográfica de una imagen tramada. Estos puntos permanecen en el plan de aceptación física.
