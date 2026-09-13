# Polaridad y estrategia física de marcado — v0.8.0

## Propósito

Marking Studio separa dos cosas que no deben confundirse:

1. **el símbolo óptico esperado** — Code 128, Code 39, QR o Data Matrix en polaridad normal;
2. **la geometría de ablación** — qué superficie debe retirar el láser para intentar producir ese símbolo después del acabado físico.

El generador matemático de las simbologías **no cambia**. La polaridad se aplica después de obtener su geometría positiva canónica.

Esto existe porque una superficie puede responder al láser de manera distinta: algunas se oscurecen, otras se aclaran y otras producen poco contraste. El software no inventa qué estrategia será mejor: genera el artefacto, advierte el riesgo y deja la aceptación a una prueba física controlada.

## Tres rutas físicas habilitadas

| Ruta | Qué se graba | Acabado posterior | Objetivo óptico |
|---|---|---|---|
| Directo / intaglio | módulos/barras | opcional, rellenar huecos | símbolo oscuro sobre fondo claro |
| Relieve | fondo alrededor del símbolo | marcador/pintura sobre lo alto | símbolo oscuro sobre fondo claro |
| Negativo seco | fondo alrededor del símbolo | ninguno | útil sólo si el material produce por sí mismo la polaridad correcta |

La palabra **negativo** en Marking Studio describe la geometría de ablación. No significa que el lector deba aceptar un código ópticamente invertido.

## Modelo `MarkingMode`

La plantilla guarda un modo por defecto y cada trabajo puede aplicar un override temporal:

- `polarity`: `positive | negative`;
- `polarity_scope`: `codes | all`;
- `negative_field`: `islands | template`;
- `field_margin_mm`: margen adicional alrededor del campo negativo;
- `kerf_compensation_mm`: recuperación TOTAL medida del ancho del módulo; `0` significa sin compensación;
- `validated_on`: nota humana sobre máquina/superficie/preset/fecha.

Todos los valores nuevos tienen defaults compatibles con 0.7.1: una plantilla antigua sigue produciendo marcado positivo.

## Combinaciones

### `negative + codes + islands`

Cada código genera su propio campo negativo. Texto y geometría auxiliar permanecen positivos. Es el modo con menor ablación y el primer candidato para pruebas de relieve.

### `negative + all + islands`

Cada elemento obtiene su isla negativa. El texto se convierte a contorno y las líneas/rectángulos se convierten a áreas vectoriales antes de restarse del campo.

### `negative + all + template`

Toda la plantilla se convierte en un único campo. El contenido se recorta como huecos mediante `fill-rule="evenodd"`. El artefacto pierde deliberadamente la estructura interna por elemento porque físicamente es un único trazado fusionado. El sistema lo declara en warnings.

Por el momento, esta modalidad rechaza elementos rotados: fundir geometría rotada de texto/códigos sin una operación booleana/transformación de paths robusta introduciría un artefacto engañoso. `islands` sí conserva rotación.

### `negative + codes + template` — DOS ETAPAS

**Bloqueado.** Un campo completo rebajado y texto/objetos positivos requerirían una segunda operación física/capa con parámetros propios. Marking Studio no controla capas de potencia ni la máquina, así que exportarlo como una sola operación sería ambiguo. La UI evita seleccionarlo y el backend lo rechaza igualmente.

## Kerf

No existe un valor por defecto distinto de cero. El usuario debe medirlo sobre material real.

`kerf_compensation_mm = 0.10` significa una recuperación TOTAL de `0.10 mm`. En geometría 1D se protege `0.05 mm` adicional por cada lado horizontal de la barra. En 2D se compensa en X/Y.

La compensación puede hacer que módulos vecinos se solapen. Bajo `fill-rule="evenodd"`, dos huecos solapados cancelarían paridad y volverían a llenar una zona protegida. Para evitarlo, `code_geometry.expand_and_union_rects()` calcula la unión de los rectángulos compensados antes de serializarlos. Es una unión específica de rectángulos alineados a ejes; no se añadió una dependencia de booleanos geométricos.

Aunque el software pueda generar esa geometría, **kerf distinto de cero sigue pendiente de validación física**.

## Preflight — invariante

El preflight **siempre** evalúa el símbolo positivo canónico.

Nunca se evalúa el SVG negativo como si fuera el código que debe leer el scanner. El negativo es una instrucción de ablación; el resultado esperado después de material/acabado es polaridad normal.

`assess_template_codes()` incluye una guardia que falla si recibe un fragmento `even-odd` negativo en la ruta de calidad.

## Trazabilidad y seguridad

Un artefacto negativo debe ser difícil de confundir:

- sufijo `_NEGATIVE` en SVG/PNG productivo;
- metadatos SVG: `polarity`, `polarity_scope`, `negative_field`, `field_margin_mm`, `kerf_compensation_mm`;
- manifiesto e histórico con el mismo modo;
- aviso visible en UI;
- `README_FIRST.txt` del ZIP advierte explícitamente cuando el lote es negativo;
- la plantilla incrementa su versión si cambia el fingerprint físico del modo de marcado.

`validated_on` no incrementa versión porque es evidencia/nota, no geometría.

## Comparación antes de gastar material

`POST /api/marking/compare` devuelve positivo y negativo generados desde el mismo motor. Opcionalmente (`include_png=true`) también rasteriza ambos a PNG desde esos SVG exactos.

La UI del Generador y del Estudio Visual muestra lado a lado:

- **POSITIVO — referencia de lectura**;
- **NEGATIVO — instrucción de ablación**.

## Cupón de caracterización

`POST /api/marking/coupon` genera una sola pieza de descarte con cuatro paneles y la misma identidad:

A. Negativo + codes + islands
B. Negativo + codes + template (2PASS)
C. Negativo + all + islands
D. Negativo + all + template

La referencia positiva se obtiene por separado en `POST /api/marking/compare`.

El cupón no es un preset de producción. Sirve para descubrir qué estrategia física merece validarse en una superficie concreta.

## Biblioteca de ajustes validados

La pestaña Materiales reutiliza la misma base `machine_captures/material_presets`; no existe una biblioteca paralela.

Un registro local puede conservar:

- máquina;
- material/superficie/modelo;
- velocidad, potencia, pasadas, intervalo, foco y modo de láser;
- `MarkingMode` completo;
- lector usado;
- resultado de lectura (`pass/partial/fail/not_tested`);
- intentos y lecturas correctas;
- notas y contexto.

Jerarquía recomendada:

1. ajuste ya validado en la misma máquina/superficie;
2. referencia específica del fabricante;
3. investigación;
4. Material Test controlado.

Un preset de investigación nunca se convierte automáticamente en receta productiva.

## Área estimada de ablación

En negativo el renderer informa `estimated_ablation_mm2` y `estimated_ablation_ratio`. Si el campo aproxima o supera 45 % del lienzo se muestra advertencia de mayor carga térmica/tiempo.

Es una métrica geométrica, **no** una predicción de energía, temperatura ni tiempo de máquina.

Para `all + template` el área reportada es deliberadamente conservadora (campo completo) porque el área exacta de glifos/paths fusionados no se utiliza para tomar decisiones de potencia.

## Compatibilidad con software de máquina

Marking Studio sigue sin transmitir G-code, movimiento, potencia ni encendido.

- LightBurn / Sculpfun Space / LaserGRBL continúan siendo la capa de máquina.
- `fill-rule="evenodd"` se valida en este proyecto con XML, svglib, CairoSVG e Inkscape cuando está disponible.
- **Interpretación productiva de `fill-rule` por LightBurn/Sculpfun Space sobre la máquina real: NO PROBADA en este host.** Debe verificarse en el piloto.

## Steren COM-597

El proyecto conserva el perfil COM-597 como lector 1D/2D y no depende de que acepte polaridad óptica inversa. La estrategia negativa busca obtener finalmente polaridad normal mediante el material o el acabado.

Data Matrix permanece pendiente de confirmación física cuando el decodificador digital del host no soporta esa simbología.

## Limitaciones declaradas

- kerf real: pendiente de medición;
- LightBurn/Sculpfun Space real: no probado en este host;
- contraste, potencia, velocidad, abrasión y durabilidad: pendientes físicos;
- `codes + template`: disponible sólo como artefacto explícito de dos etapas; no se presenta como una pasada automática;
- `all + template` con rotación: bloqueado hasta contar con transformación/fusión de paths verificable;
- modo maestro editable + `negative/all`: bloqueado porque el texto debe convertirse a contorno.

## Elemento imagen

La final 0.8.0 incorpora `ElementSpec(kind="image")` como fase separada dentro del mismo proyecto. SVG se sanea a geometría vectorial segura; PNG/JPG se convierten a 1-bit con umbral o Floyd–Steinberg. La imagen no entra al preflight de códigos y el renderer advierte si invade la caja/quiet-zone de un símbolo.

En modo negativo, `scope=codes` mantiene la imagen positiva. `scope=all` con imagen se rechaza por ahora porque un SVG arbitrario saneado no puede convertirse honestamente en hueco de un campo sin una operación booleana general verificada. Consulte `IMAGE_ELEMENT.md`.
