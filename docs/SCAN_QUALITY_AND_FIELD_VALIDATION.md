# Calidad de escaneo y validación de campo

## Propósito

Un SVG válido no garantiza que el código sobreviva al mundo físico. La legibilidad final depende de módulo real, quiet zone, contraste, foco, material, escalado del software de salida, suciedad, desgaste, lector y ángulo. La v0.6.2 añade un **preflight preventivo** que reduce errores antes de usar la SCULPFUN, pero mantiene la aceptación física como autoridad final.

## Dos vistas distintas en el Estudio visual

- **Lienzo de edición — NO escaneable**: usa símbolos simplificados para arrastrar objetos rápidamente.
- **Vista real SVG de producción — ESCANEABLE**: la produce el mismo renderer que se exporta a LightBurn/Sculpfun Space/LaserGRBL.

Nunca valide con la representación del lienzo.

## Qué comprueba “Probar código”

Para cada Code 128, Code 39, QR o Data Matrix:

1. dato resuelto exacto;
2. módulo físico efectivo;
3. ancho/alto real del símbolo;
4. permanencia dentro del lienzo físico;
5. compatibilidad declarada por el lector seleccionado;
6. referencia de contraste del lector cuando existe;
7. rasterización digital y decodificación exacta bajo degradaciones simples, cuando `pyzbar/libzbar` está disponible.

La clasificación es preventiva:

- **ROBUSTO**: geometría conservadora y buena tolerancia digital;
- **ACEPTABLE**: válido, con menor margen;
- **FRÁGIL**: alguna decisión reduce margen; no producir sin ajustar/probar;
- **NO LEGIBLE**: dato vacío, fuera de área, lector incompatible o falla de lectura original.

## Por qué el reescalado importa

Los elementos se diseñan en milímetros. Si un PDF, procesador de texto, driver de impresora o importador aplica “Ajustar a página”, “Fit”, “Scale to fit” o una reducción automática, el módulo físico también se reduce. En Code 128 eso adelgaza barras y espacios; en QR reduce cada módulo.

Para pruebas en papel y para handoff al software de la máquina:

**mantener 100 % / tamaño real / 1:1.**

## Evidencia de campo inicial — 2026-09-12

Durante la prueba con una hoja impresa fotografiada se hizo una lectura independiente sobre la fotografía disponible:

- QR `TEL-0037`: **decodificado correctamente**;
- Code 128 `4281847`: **decodificado correctamente**;
- otros símbolos visibles en la hoja/fotografía no se declararon PASS porque el decodificador no los recuperó de la imagen completa.

Esto no demuestra que esos otros símbolos sean inválidos: la fotografía introduce perspectiva, desenfoque, exposición y pérdida de resolución. La siguiente autoridad es el **Steren COM-597 sobre la hoja física**, y después el mismo lector sobre el grabado real.

## Procedimiento de aceptación recomendado

1. Genere el símbolo y ejecute **Probar legibilidad**.
2. Exporte SVG sin reescalar.
3. Para una prueba en papel, imprima a 100 %.
4. Abra un bloc de notas y escanee el símbolo 5 veces.
5. Repita desde pequeñas variaciones de distancia/ángulo.
6. El dato escrito debe coincidir exactamente en todas las lecturas.
7. Después pruebe el mismo diseño sobre material de sacrificio con el preset real del área.
8. Si falla, aumente módulo/tamaño antes de aumentar agresivamente potencia/profundidad: el contraste y bordes limpios importan más que “quemar más”.
9. Sólo entonces guarde el conjunto `plantilla + material + preset + lector` como estándar local aprobado.

## Límite explícito

El preflight no es un verificador ISO/IEC y no mide contraste del futuro grabado. Su función es encontrar problemas evitables temprano y documentar por qué una geometría se considera segura o frágil.
