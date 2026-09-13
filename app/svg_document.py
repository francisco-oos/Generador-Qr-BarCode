"""Build the production/editable SVG document: semantic layers and unique IDs.

WHY:
Antes de v0.7.0 cada marca se serializaba como ``<g id="mark">`` con el contenido
que devolvian las librerias externas.  Eso producia identificadores repetidos
(``mark``, ``clip``, ``group``) en cuanto un documento contenia mas de un simbolo,
lo que viola la unicidad de ``id`` de XML/SVG y hace que dos simbolos distintos
puedan referenciar el mismo recurso.

Este modulo concentra TODA la construccion del documento en un solo lugar:
- asigna identificadores legibles, estables y unicos;
- agrupa los elementos en capas semanticas;
- emite metadatos de trazabilidad acotados;
- distingue la exportacion editable de la de produccion.

Ningun otro modulo debe escribir la cabecera ``<svg>`` por su cuenta.  Centralizar
la serializacion es lo que permite garantizar la unicidad de IDs mediante una
sola prueba en lugar de auditar cada generador.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# WHY: Namespace propio para metadatos; no colisiona con SVG ni con Inkscape y es
# ignorado por cualquier renderizador que no lo entienda.
MS_NAMESPACE = "https://server-oficina.local/ns/marking-studio"
INKSCAPE_NAMESPACE = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NAMESPACE = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd"

# WHY: Orden de apilado de capas: fondo abajo, referencias de registro arriba.
# El orden es explicito y estable para que un archivo reabierto en Inkscape
# conserve la misma jerarquia que vio el disenador.
LAYER_ORDER = (
    "layer_background",
    "layer_geometry",
    "layer_codes",
    "layer_text",
    "layer_registration",
    "layer_guides",
)

LAYER_LABELS = {
    "layer_background": "Background",
    "layer_geometry": "Geometry",
    "layer_codes": "Codes",
    "layer_text": "Text",
    "layer_registration": "Registration",
    "layer_guides": "Guides (do not engrave)",
}

# WHY: Capa por defecto de cada tipo de elemento. Vive aqui y no en el motor de
# render para que agregar un tipo de activo nuevo no obligue a tocar el renderer.
DEFAULT_LAYER_BY_KIND = {
    "code128": "layer_codes",
    "code39": "layer_codes",
    "qr": "layer_codes",
    "datamatrix": "layer_codes",
    "text": "layer_text",
    "rect": "layer_geometry",
    "line": "layer_geometry",
    "image": "layer_geometry",
}

# WHY: Prefijo legible por tipo. ``barcode_serial`` se entiende al abrir el archivo;
# ``obj45329875`` no. Este mapeo es lo que hace util el ciclo medir-en-Inkscape.
ID_PREFIX_BY_KIND = {
    "code128": "barcode",
    "code39": "barcode",
    "qr": "qr",
    "datamatrix": "dmx",
    "text": "text",
    "rect": "rect",
    "line": "line",
    "image": "image",
}

_ID_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


# WHY: Normaliza cualquier texto a un identificador XML valido sin perder legibilidad.
def slug(value: str, fallback: str = "") -> str:
    out = _ID_SAFE.sub("_", str(value or "").strip()).strip("_-")
    out = re.sub(r"_{2,}", "_", out)
    if out and not re.match(r"^[A-Za-z_]", out):
        out = "e_" + out
    return out[:80] or fallback


# WHY: Garantiza unicidad de identificadores dentro de un documento.
# Es la pieza que hace imposible reproducir el defecto de ``id="clip"`` repetido.
class IdRegistry:
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix
        self._used: set[str] = set()

    # WHY: Devuelve un identificador libre; si el nombre ya existe agrega un sufijo
    # numerico en lugar de sobrescribir, para que ningun elemento pierda su nodo.
    def reserve(self, base: str) -> str:
        candidate = f"{self.prefix}{base}"
        if candidate not in self._used:
            self._used.add(candidate)
            return candidate
        n = 2
        while f"{candidate}_{n}" in self._used:
            n += 1
        final = f"{candidate}_{n}"
        self._used.add(final)
        return final

    # WHY: Copia defensiva del conjunto usado; las pruebas verifican unicidad sin
    # poder alterar el estado interno del registro.
    @property
    def used(self) -> set[str]:
        return set(self._used)


# WHY: Nombre por defecto de un elemento derivado de su tipo y de su campo de datos,
# para que el ID del archivo describa el proposito y no la posicion en una lista.
def default_element_name(kind: str, source: str | None, literal: str | None, index: int) -> str:
    prefix = ID_PREFIX_BY_KIND.get(kind, "element")
    token = ""
    if source:
        token = slug(source.split("|")[0])
    elif literal:
        token = slug(literal)
    if token:
        return f"{prefix}_{token}"
    return f"{prefix}_{index + 1:02d}"


# WHY: Un nodo ya serializado con su identificador y su capa de destino.
@dataclass
class DocumentNode:
    element_id: str
    layer: str
    svg: str
    title: str = ""
    # WHY: El transform vive en el ``<g>`` del elemento y no dentro de su geometria.
    # Asi la geometria del archivo sigue siendo la misma que la del disenador y un
    # editor externo puede leer la rotacion como una propiedad del objeto, no como
    # coordenadas ya rotadas e irreversibles.
    transform: str = ""


# WHY: Construye el transform de rotacion alrededor del centro del propio elemento.
# Devuelve cadena vacia para 0 grados para no ensuciar el archivo con transforms
# neutros que un editor externo mostraria como objetos "transformados" sin serlo.
def rotation_transform(rotation_deg: float, cx_mm: float, cy_mm: float) -> str:
    angle = round(float(rotation_deg or 0.0) % 360.0, 4)
    if angle == 0.0:
        return ""
    return f"rotate({angle:.4f} {cx_mm:.4f} {cy_mm:.4f})"


# WHY: Acumula nodos y produce el documento final; unico punto que escribe ``<svg>``.
@dataclass
class SvgDocumentBuilder:
    width_mm: float
    height_mm: float
    mode: str = "production"          # "editable" | "production"
    metadata: dict[str, str] = field(default_factory=dict)
    nodes: list[DocumentNode] = field(default_factory=list)

    # WHY: Recoge un nodo sin decidir todavia su posicion en el documento,
    # de modo que el orden de capas no dependa del orden de creacion.
    def add(self, node: DocumentNode) -> None:
        if node.svg:
            self.nodes.append(node)

    # WHY: Serializa metadatos acotados; nunca rutas locales, secretos ni datos personales.
    def _metadata_block(self) -> str:
        if not self.metadata:
            return ""
        attrs = " ".join(
            f'{slug(k)}="{_escape_attr(str(v))}"'
            for k, v in self.metadata.items()
            if v is not None and str(v) != ""
        )
        return (
            f"<metadata><ms:mark xmlns:ms=\"{MS_NAMESPACE}\" {attrs}/></metadata>"
        )

    # WHY: Atributos de capa de Inkscape solo en modo editable; en produccion el
    # archivo queda libre de extensiones de un editor concreto.
    def _layer_attrs(self, layer: str) -> str:
        if self.mode != "editable":
            return ""
        label = LAYER_LABELS.get(layer, layer)
        return f' inkscape:groupmode="layer" inkscape:label="{_escape_attr(label)}"'

    # WHY: Ensambla el documento en el orden de capas declarado y no en el orden de
    # insercion, para que el archivo sea reproducible ante el mismo modelo de datos.
    def build(self) -> str:
        by_layer: dict[str, list[DocumentNode]] = {}
        for node in self.nodes:
            by_layer.setdefault(node.layer, []).append(node)

        body: list[str] = []
        for layer in LAYER_ORDER:
            items = by_layer.get(layer)
            if not items:
                continue
            inner = "".join(element_group(n) for n in items)
            body.append(f'<g id="{layer}"{self._layer_attrs(layer)}>{inner}</g>')

        # Capas no previstas: se emiten al final en orden alfabetico para no perderlas.
        for layer in sorted(set(by_layer) - set(LAYER_ORDER)):
            inner = "".join(element_group(n) for n in by_layer[layer])
            body.append(f'<g id="{slug(layer)}">{inner}</g>')

        ns = f'xmlns="http://www.w3.org/2000/svg"'
        if self.mode == "editable":
            ns += f' xmlns:inkscape="{INKSCAPE_NAMESPACE}" xmlns:sodipodi="{SODIPODI_NAMESPACE}"'
        return (
            f'<svg {ns} width="{self.width_mm:.4f}mm" height="{self.height_mm:.4f}mm" '
            f'viewBox="0 0 {self.width_mm:.4f} {self.height_mm:.4f}">'
            f"{self._metadata_block()}"
            f'{"".join(body)}'
            f"</svg>"
        )


# WHY: Serializa un elemento como un unico ``<g>`` con id, titulo y transform.
# Existe como funcion para que marca individual y lote produzcan un nodo identico.
def element_group(node: DocumentNode) -> str:
    transform = f' transform="{node.transform}"' if node.transform else ""
    return f'<g id="{node.element_id}"{transform}>{_title(node.title)}{node.svg}</g>'


# WHY: Escapa valores de atributo para que un dato del activo nunca rompa el XML.
def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


# WHY: ``<title>`` es el texto que Inkscape muestra al pasar el cursor; ayuda a
# identificar un objeto pequeno sin abrir el XML.
def _title(text: str) -> str:
    if not text:
        return ""
    return f"<title>{_escape_attr(text)}</title>"


# WHY: Envuelve un conjunto de marcas ya serializadas en el documento de un lote.
def build_batch_document(width_mm: float, height_mm: float, marks_svg: str,
                         guides_svg: str = "", mode: str = "production",
                         metadata: dict[str, str] | None = None) -> str:
    builder = SvgDocumentBuilder(width_mm, height_mm, mode=mode, metadata=metadata or {})
    body: list[str] = []
    ns = 'xmlns="http://www.w3.org/2000/svg"'
    if mode == "editable":
        ns += f' xmlns:inkscape="{INKSCAPE_NAMESPACE}" xmlns:sodipodi="{SODIPODI_NAMESPACE}"'
    layer_attrs_marks = (
        ' inkscape:groupmode="layer" inkscape:label="Marks"' if mode == "editable" else ""
    )
    layer_attrs_guides = (
        ' inkscape:groupmode="layer" inkscape:label="Guides (do not engrave)"'
        if mode == "editable" else ""
    )
    body.append(f'<g id="layer_marks"{layer_attrs_marks}>{marks_svg}</g>')
    if guides_svg:
        body.append(f'<g id="layer_guides"{layer_attrs_guides}>{guides_svg}</g>')
    return (
        f'<svg {ns} width="{width_mm:.4f}mm" height="{height_mm:.4f}mm" '
        f'viewBox="0 0 {width_mm:.4f} {height_mm:.4f}">'
        f"{builder._metadata_block()}"
        f'{"".join(body)}'
        f"</svg>"
    )
