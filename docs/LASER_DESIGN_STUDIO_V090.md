# Laser Design Studio v0.9 — evolución experimental

## Propósito

Esta rama convierte Marking Studio de un generador especializado de identificación en una base extensible de **diseño y preflight para fabricación láser**, sin asumir control de máquina.

La frontera de seguridad de v0.8 permanece: el sistema genera documentos SVG y diagnóstico geométrico; LightBurn, Sculpfun Space, LaserGRBL u otro software de máquina conserva movimiento, potencia, foco y disparo.

## Qué se conserva de v0.8

No se reemplazan QR, Code128, Code39, Data Matrix, CSV/XLSX, jigs, trazabilidad, presets, polaridad, kerf ni el diseñador visual existente. Esta evolución añade otra superficie sobre el mismo producto.

## Motor nuevo

`app/laser_design_studio.py` usa milímetros como unidad canónica y separa cuatro responsabilidades:

1. generación de geometría;
2. preflight de manufacturabilidad;
3. serialización SVG;
4. proveedores opcionales futuros.

### Papel picado paramétrico

Genera patrones de diamante, círculo, hexágono, estrella o corazón. La semilla y parámetros forman un **Design Genome** que permite regenerar exactamente el mismo diseño.

### Foto → halftone de corte

Convierte luminosidad de una imagen en perforaciones. El diámetro máximo se limita automáticamente cuando la combinación solicitada violaría el puente mínimo entre celdas.

### Foto → stencil

Convierte una imagen raster en regiones de corte, detecta componentes de material que quedarían aislados e inserta corredores de material para conectarlos con el marco. Las guías de puente aparecen únicamente en el SVG de preview; el SVG productivo conserva sólo operaciones de corte.

### Preflight físico geométrico

El análisis actual comprueba:

- cantidad de componentes resultantes del material restante;
- área retirada;
- distancia mínima estimada entre cortes y contra el borde;
- comparación con `min_bridge_mm`;
- hotspots de menor separación;
- escala mínima recomendada cuando el diseño es demasiado fino.

Un PASS significa que la geometría satisface estas reglas digitales; **no significa que el material real haya sido validado**.

## OpenAI Experimental Lab

Esta zona está separada de funciones estables para experimentar sin convertir el producto en un conjunto de parches.

### Bridge Ladder Coupon

Genera un cupón sacrificial con ligamentos de anchos conocidos. El operador lo corta usando parámetros que ya utiliza y registra cuál es el puente más estrecho que sobrevive limpiamente.

La meta es cerrar el ciclo:

`material real → medición física → min_bridge_mm → preflight de diseños futuros`

No se infieren velocidad, potencia ni parámetros de láser.

### Cut Survival Map

El preflight localiza cuellos geométricos y separaciones críticas. La siguiente iteración podrá convertir esos hotspots en una superposición visual sobre el diseño.

### Safe Scale Guard

Si un archivo importado tiene detalles menores al mínimo configurado, el sistema calcula cuánto debe ampliarse para respetar esa restricción. Futuro: también podrá proponer simplificación local conservando tamaño final.

### Design Genome

Los generadores procedurales guardan receta + semilla. Dos ejecuciones con la misma receta deben producir el mismo arte; esto permite versionar diseños sin almacenar miles de variantes casi idénticas.

### Adaptive Bridge Planner

La primera implementación conecta islas del stencil al marco. El siguiente nivel será puntuar rutas candidatas por longitud, impacto visual, simetría y resistencia, en lugar de elegir sólo la ruta cardinal más corta.

### Material DNA Passport

Genera una hoja sacrificial reproducible que combina tres familias de probetas: puentes de material, agujeros mínimos repetidos y separaciones entre cortes. Cada receta recibe un `passport_id` estable. Después del corte, el operador registra el menor valor que sale íntegro y repetible para cada familia.

El pasaporte **no certifica** un material ni calcula potencia/velocidad. Convierte observaciones físicas de un proceso ya establecido en restricciones geométricas que los generadores pueden usar después. Esto permite que papel picado, halftone y stencil compartan un mismo conjunto de límites reales en lugar de valores arbitrarios.

### Self-Guarding Geometry

El objetivo no es generar primero y reparar siempre después. Cuando una restricción ya es conocida, el generador debe respetarla durante la construcción: halftone limita automáticamente el diámetro de perforación, papel picado limita el tamaño de motivos y stencil conserva/construye material de unión. El preflight permanece como segunda barrera independiente.

## Investigación consolidada y decisión de integración

### BridgeIt

Aporta el patrón conceptual imagen → contornos → islas → bridges → SVG. La rama implementa su propio motor raster/bridge, no copia su aplicación.

### VTracer

Se reserva como proveedor opcional para vectorización de mayor detalle. El contrato de capacidades detecta si está instalado, pero v0.9 no lo exige y funciona completamente sin él.

### svg-halftone

Valida la utilidad de una ruta especializada imagen → perforaciones. v0.9 implementa un generador propio integrado al preflight físico.

### Deepnest / SVGnest

Se conserva una frontera de `nesting` para una fase posterior. No se mezcla nesting con generación: primero debe existir geometría válida y después optimizarse la lámina.

### Maker.js

Su separación entre modelo geométrico, operaciones y exportación refuerza la decisión de mantener una representación geométrica propia en lugar de acoplar toda la lógica a SVG.

### CUTLINE / Boxes.py y otros proyectos GPL

Se estudian como bibliografía ejecutable para preflight, bridges, kerf, generadores paramétricos y CAM. No se copia ni integra código GPL en este núcleo propietario experimental.

## Dependencias

La única dependencia nueva obligatoria en esta etapa es **Shapely 2.1.2**, utilizada para booleans, conectividad, distancia y geometría robusta.

VTracer permanece opcional. No se incorpora Deepnest ni otro runtime adicional.

## Interfaz

`/laser-design` ofrece un flujo lineal:

1. elegir herramienta;
2. ajustar parámetros;
3. generar;
4. leer preflight;
5. exportar SVG.

La UI oculta parámetros que no pertenecen al modo actual. Imagen se carga por drag-and-drop o selector. El panel derecho mantiene visible el diagnóstico físico mientras se ajusta el diseño.

## Contratos de seguridad

- no G-code;
- no movimiento;
- no comandos de potencia;
- no streaming al láser;
- SVG de guías separado del SVG de corte;
- imágenes procesadas localmente;
- límites de tamaño y complejidad;
- validación física real pendiente antes de tratar presets o mínimos como productivos.

## Fases siguientes propuestas

1. **Overlay de hotspots**: visualizar sobre el diseño los cuellos de material.
2. **Vectorizer Provider**: VTracer opcional con fallback nativo.
3. **Papel picado Composer**: texto convertido a stencil, motivos, bordes, simetría y plantillas.
4. **Nesting Adapter**: múltiples diseños sobre hoja/material con separación configurable.
5. **Material Fingerprint**: guardar resultado del Bridge Ladder por material, espesor, máquina y preset ya validado.
6. **Constraint-aware generator**: generar variantes decorativas que nunca creen una característica menor al límite físico elegido.
7. **Production proof sheet ampliada**: Material DNA ya integra bridge/hole/gap; una fase posterior puede sumar kerf y muestras de grabado manteniendo operaciones semánticas separadas.

## Estado de aceptación

Esta rama es experimental. Se puede evaluar software, UI y SVG inmediatamente. La aceptación física exige pruebas sacrificiales antes de trabajar sobre activos o material final.
