# Grabado negativo / relieve para códigos — v0.7.1
> **Estado histórico:** este documento describe la primera implementación v0.7.1 por elemento. En v0.8.0 fue generalizada por `MarkingMode` a nivel de plantilla/trabajo. Para el comportamiento vigente consulte `POLARITY_AND_PHYSICAL_MARKING.md`. El mecanismo legado se conserva sólo por compatibilidad.


## Propósito

Hay superficies donde el láser produce una marca visible para una persona pero con poco contraste óptico para un lector. Marking Studio 0.7.1 añade, **por elemento de código**, una segunda estrategia de geometría:

- `positive`: se graban las barras/módulos que normalmente aparecen oscuros;
- `negative_background`: se graba el fondo y los espacios del símbolo, dejando las barras/módulos sin grabar y en relieve respecto del área rebajada.

La segunda opción está pensada principalmente para un flujo físico como:

```text
SVG negativo
→ grabar fondo/espacios
→ quedan barras/módulos a la altura original
→ frotar marcador/pintura sobre la superficie elevada
→ limpiar excedente si corresponde
→ barras/módulos oscuros + fondo claro/rebajado
→ verificar con lector real
```

No debe confundirse con afirmar que un **barcode ópticamente invertido** (claro sobre oscuro) será leído por cualquier escáner.

## Por qué se modela como estrategia de grabado y no como “invertir colores”

LightBurn documenta que un grabado vectorial puede invertirse agregando un contorno exterior en la misma capa; así se intercambia qué regiones se rellenan. También dispone de `Negative Image` para imágenes, pero esa opción es distinta y no cambia nuestro SVG vectorial.

Referencias:

- LightBurn, *How to Invert a Vector Engraving*: https://docs.lightburnsoftware.com/2.1/Explainers/HowToInvertAVectorEngraving/
- LightBurn, *Engraved Areas Opposite of Expectation*: https://docs.lightburnsoftware.com/2.1/Troubleshooting/PreviewWindow/EngravedAreasOpposite/

Marking Studio genera directamente el complemento vectorial dentro de la caja física del símbolo. El archivo contiene un `path` compuesto con `fill-rule="evenodd"`: la caja exterior es área a grabar y los módulos/barras son huecos.

## Quiet zone en modo negativo

La caja exterior **incluye la quiet zone**. Esto es intencional.

Si se pretende frotar un marcador sobre el relieve, dejar la quiet zone a la misma altura que las barras haría que el marcador la ensuciara y destruiría el margen óptico. Al rebajar también la quiet zone, sólo las barras/módulos quedan elevados dentro del rectángulo del símbolo.

La quiet zone sigue gobernada por `quiet_modules` y por el perfil de calidad. El modo negativo no permite saltarse el preflight.

## Compatibilidad de lectores y polaridad

La capacidad de leer símbolos de polaridad invertida **depende del lector y su configuración**. Por ejemplo, Zebra documenta modos `Regular Only`, `Inverse Only` e `Inverse Autodetect` para 1D inverso en determinados escáneres. Cognex documenta polaridad `dark-on-light`, `light-on-dark` o `either` para Data Matrix en equipos compatibles.

Referencias:

- Zebra, *Inverse 1D*: https://docs.zebra.com/us/en/scanners/general/sm72-ig/symbologies/inverse-1d.html
- Cognex, *DATAMATRIX.CUSTOM-POLARITY*: https://docs.cognex.com/dmst_632/web/EN/DMCC/Content/Topics/idp10155206208.htm
- Cognex, DPM / ISO 29158: https://docs.cognex.com/dmst_631/web/EN/DM475V_Manual/Content/Topics/DM475V/TruCheck/AIM_DPM.htm

El manual disponible del **Steren COM-597** confirma Code 128, QR y Data Matrix, pero la documentación revisada no demuestra un modo de decodificación inversa. Por eso Marking Studio **no presume** que el COM-597 leerá directamente un símbolo claro-sobre-oscuro. La estrategia recomendada para el caso propuesto es recuperar polaridad normal mediante contraste físico/marker y validarlo con el lector real.

Manual Steren: https://descargas.steren.com.mx/COM-597-instr.pdf

## Qué valida el preflight

Para `negative_background`, el preflight:

1. sigue validando la geometría canónica del código (dato, módulo, quiet zone, tamaño, lector y degradaciones digitales);
2. marca `physical_validation_required=true`;
3. informa que la prueba digital no certifica el acabado negativo físico.

Esto evita dos errores opuestos:

- declarar inválida una geometría correcta sólo porque `pyzbar` no decodifica la polaridad inversa;
- declarar listo para producción un proceso de relleno/relieve que nunca se probó sobre la pieza real.

## Coste y seguridad

El grabado negativo puede retirar **más área** que el positivo. Eso normalmente implica más tiempo, más energía acumulada y más calor sobre el material. No debe activarse automáticamente ni reutilizarse un preset positivo sin una prueba de sacrificio.

Orden recomendado:

1. usar el preset local ya validado sólo como punto de partida;
2. probar en material de descarte;
3. verificar que no haya deformación, fusión o humo anormal;
4. aplicar el marcador/relleno si ese es el método elegido;
5. escanear repetidamente con el lector objetivo;
6. registrar `plantilla + modo + material + preset + lector` como estándar local sólo después de aprobarlo.

## Límite explícito

0.7.1 implementa la geometría y las pruebas de software. **No declara aprobado físicamente** el proceso de marcador sobre INOVA, Sercel, KingKong 9, BISON, Xiaomi/Redmi ni ningún otro equipo. Esa aprobación requiere material real, SCULPFUN real y lector real.