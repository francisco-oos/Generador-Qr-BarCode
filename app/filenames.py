"""Resolve output file names from a user-defined pattern.

WHY:
El nombre del archivo es la unica pista que tendra el operador al abrir una
carpeta con miles de SVG en LightBurn.  Debe poder componerlo con los campos que
le importan (``{economico}_{serial}``), pero el sistema no puede confiar en que
el dato venga limpio: un CSV real trae espacios, barras, dos puntos y acentos.

El saneado apunta a la interseccion de Windows, Linux y macOS, que es mas
restrictiva que cualquiera de los tres por separado.  Se prefiere un nombre feo
pero abrible en los tres sistemas a un nombre bonito que falle al copiar la
carpeta a otra maquina del area.
"""

from __future__ import annotations

import re
import unicodedata

from .barcode_engine import SafeFormatDict

# WHY: Caracteres prohibidos por NTFS y problematicos en rutas POSIX.
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

# WHY: Nombres reservados por Windows; un archivo llamado ``CON.svg`` no se puede
# crear ni borrar con herramientas normales.
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

MAX_LENGTH = 100


# WHY: Convierte cualquier valor en un nombre de archivo valido en los tres sistemas
# operativos objetivo, sin perder legibilidad del identificador del activo.
def sanitize_filename(value: str, fallback: str = "mark") -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _FORBIDDEN.sub("_", text)
    text = text.replace(" ", "_")
    text = re.sub(r"_{2,}", "_", text).strip("._-")
    text = text[:MAX_LENGTH].strip("._-")
    if not text:
        return fallback
    if text.split(".")[0].upper() in _RESERVED:
        text = f"_{text}"
    return text


# WHY: Resuelve el nombre segun la prioridad patron -> campo unico -> identidad
# principal de la plantilla -> primer campo esperado -> indice, para que siempre
# exista un nombre estable aunque el usuario no configure nada.
def resolve_filename(data: dict[str, str], template, pattern: str | None,
                     field: str | None, index: int) -> str:
    if pattern:
        rendered = str(pattern).format_map(SafeFormatDict({k: str(v) for k, v in data.items()}))
        # Un marcador sin resolver queda visible como ``{campo}``; se limpia igual
        # que cualquier otro caracter invalido en lugar de fallar la exportacion.
        return sanitize_filename(rendered, f"mark_{index:05d}")
    value = ""
    if field:
        value = str(data.get(field, ""))
    if not value:
        primary = str(getattr(template, "metadata", {}).get("primary_identity_field", ""))
        if primary:
            value = str(data.get(primary, ""))
    if not value and getattr(template, "expected_fields", None):
        value = str(data.get(template.expected_fields[0], ""))
    return sanitize_filename(value, f"mark_{index:05d}")
