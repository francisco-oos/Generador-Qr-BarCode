# Revisión independiente posterior a Claude — v0.7.1

Fecha: 2026-09-13
Base recibida: `server-oficina-marking-studio-v0.7.0.zip`

## Resultado

La 0.7.0 recibida es coherente con su reporte POST: SHA-256 correcto, estructura limpia, arranque real y pruebas funcionales. La auditoría independiente confirmó además que el motor no contiene ramas de fabricante en la lógica productiva; INOVA/Sercel/teléfonos siguen siendo datos/plantillas.

Se encontraron dos mejoras documentales y una mejora funcional pertinente a la finalidad del producto:

1. `README.md` decía 149 pruebas para 0.7.0 aunque el POST y la colección real son 151.
2. `app/code_geometry.py` conservaba en su docstring la antigua afirmación falsa de que CairoSVG producía una imagen negra; PRE/POST ya habían demostrado que fue un error de medición del canal alfa.
3. Se añadió una estrategia genérica `negative_background` para códigos, surgida del caso real de superficies con poco contraste.

## Grabado negativo / relieve

No se reimplementó ninguna simbología. El código canónico se genera igual y, sólo después, se transforma la geometría de remoción:

- `positive`: se graban barras/módulos;
- `negative_background`: se graba el complemento dentro de la caja física del símbolo, incluida la quiet zone, dejando barras/módulos como islas sin grabar.

Esto habilita pruebas de relieve donde un marcador/pintura se frota sobre la parte elevada para obtener barras/módulos oscuros sobre fondo rebajado. No se afirma que el SVG de polaridad inversa crudo sea legible por el Steren COM-597: su manual confirma las simbologías, pero no documenta explícitamente lectura inversa.

## Evidencia software específica

- Code 128 negativo `Q00525499`: render con svglib, CairoSVG e Inkscape correcto; la polaridad cruda no decodifica con pyzbar (esperado), y al simular la recuperación de polaridad óptica se obtiene exactamente `Q00525499`.
- QR negativo `TEL-0037`: mismo resultado, recupera exactamente `TEL-0037` tras la simulación de contraste final.
- El modo es opt-in y las cinco plantillas existentes permanecen en `positive`.
- El modelo rechaza `negative_background` en texto/línea/rectángulo para evitar una semántica ambigua.
- El preflight expone `physical_validation_required=true` y conserva las pruebas de módulo, quiet zone y geometría.

## Hardcode

Búsqueda sobre `app/*.py`, `app/static/*.js` y HTML:

- no hay lógica ejecutable por INOVA/Sercel/CUBOT/UMIDIGI/Xiaomi;
- las menciones restantes son ejemplos, placeholders, documentación o nombre del lector real;
- `engraving_mode` es una propiedad de `ElementSpec`, no una condición por tipo de activo.

## Pendiente físico

El nuevo modo NO queda aprobado para producción física hasta realizar material de descarte → grabado → marcador/relleno → limpieza → lectura repetida con el lector objetivo. También debe medirse el incremento de tiempo/calor frente al grabado positivo, porque el negativo remueve mucha más superficie.
