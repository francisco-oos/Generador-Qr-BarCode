"""Rasterize and analyse SVG output without alpha-transparency false positives.

WHY (v0.7.0):
Durante la linea base PRE de este proyecto se concluyo erroneamente que un
renderizador independiente producia una imagen completamente negra y que eso
demostraba fragilidad del SVG generado.  La causa real fue de medicion: el PNG
venia en RGBA y se convirtio con ``Image.convert("L")``, que descarta el canal
alfa y deja los pixeles transparentes en 0, es decir, negro.  Al componer sobre
fondo blanco la densidad de tinta resulto de 0.0085 y el archivo se renderizaba
correctamente.

Este modulo existe para que ese falso positivo no pueda repetirse.  Cualquier
analisis de tinta, contraste o decodificacion debe pasar por aqui:

    RGBA -> composicion sobre fondo blanco -> escala de grises -> analisis

Nunca se debe medir densidad directamente sobre una imagen con transparencia.
"""

from __future__ import annotations

import io

from PIL import Image

# WHY: El blanco es el fondo de referencia porque es lo que asume cualquier decoder
# de codigo de barras y lo que aproxima papel o una superficie clara marcada.
WHITE = (255, 255, 255, 255)

# WHY: Umbral de binarizacion. 128 es el punto medio; se declara como constante para
# que todas las pruebas midan lo mismo y un cambio de criterio sea explicito.
INK_THRESHOLD = 128


# WHY: Punto unico donde una imagen con alfa se convierte en una imagen analizable.
# Es la funcion que impide reproducir el falso positivo documentado arriba.
def flatten_on_white(image: Image.Image) -> Image.Image:
    """Composite any image over an opaque white background and return greyscale."""
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, WHITE)
    return Image.alpha_composite(background, rgba).convert("L")


# WHY: Acepta bytes PNG de cualquier renderizador; los de CairoSVG traen alfa y los de
# svglib no, y el resto del analisis no debe tener que saber cual fue el origen.
def load_flattened(png_bytes: bytes) -> Image.Image:
    return flatten_on_white(Image.open(io.BytesIO(png_bytes)))


# WHY: Densidad de tinta = fraccion de pixeles oscuros. Un 1.0 significa imagen
# totalmente negra y es la senal que delataba el error de medicion original.
def ink_density(image: Image.Image) -> float:
    grey = flatten_on_white(image)
    histogram = grey.histogram()
    dark = sum(histogram[:INK_THRESHOLD])
    total = grey.size[0] * grey.size[1]
    return dark / total if total else 0.0


# WHY: Rasteriza con el renderizador de produccion (svglib), que es el mismo que usa
# la exportacion PNG; asi las pruebas miden el artefacto real y no una aproximacion.
def rasterize_production(svg: str, width_mm: float, height_mm: float, dpi: int = 600) -> Image.Image:
    from .exporters import svg_to_png

    return load_flattened(svg_to_png(svg, width_mm, height_mm, dpi=dpi))


# WHY: Rasteriza con un motor independiente para comprobar que el archivo no depende
# de las tolerancias de una sola libreria.  Devuelve ``None`` si no esta instalado,
# porque la ausencia de una herramienta opcional no es un fallo del proyecto: se
# reporta como NO PROBADO, nunca como PASS.
def rasterize_independent(svg: str, dpi: int = 600) -> Image.Image | None:
    """Rasterize with a second, independent engine; ``None`` when unavailable."""
    try:
        import cairosvg
    except Exception:
        return None
    return load_flattened(cairosvg.svg2png(bytestring=svg.encode("utf-8"), dpi=dpi))


# WHY: Decodifica con pyzbar sobre la imagen ya normalizada.  Devuelve ``None`` cuando
# libzbar no esta disponible para distinguir "no legible" de "no se pudo comprobar".
def decode_symbols(image: Image.Image) -> list[tuple[str, str]] | None:
    try:
        from pyzbar import pyzbar
    except Exception:
        return None
    try:
        found = pyzbar.decode(flatten_on_white(image))
    except Exception:
        return None
    return sorted((d.type, d.data.decode("utf-8", errors="replace")) for d in found)
