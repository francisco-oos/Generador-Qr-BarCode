"""Unified ingestion for CSV, TXT and XLSX sources.

WHY:
El area entrega inventarios en los dos formatos que produce cualquier oficina:
listas de texto exportadas de un sistema y libros de Excel armados a mano.  Antes
de v0.7.0 solo se aceptaba texto, asi que un XLSX obligaba al operador a
convertirlo antes de usar Marking Studio: un paso manual fuera de trazabilidad y
una fuente conocida de errores (guardar como CSV cambia separadores, pierde ceros
a la izquierda y altera fechas).

Decisiones tomadas y por que:

- **openpyxl** en lugar de pandas.  Solo se necesita leer celdas; pandas traeria
  numpy y decenas de MB para nada.  Licencia MIT, mantenido, sin dependencias
  nativas.
- **read_only=True** siempre.  Un libro de 10 000 filas cargado completo en
  memoria es innecesario cuando la vista previa muestra decenas de registros.
- **Se descarta ``.xls`` heredado.**  Requiere ``xlrd``, cuyo soporte de xls esta
  congelado y cuyo formato binario no aporta nada que el usuario no pueda
  resolver con «Guardar como» en el propio Excel.  Se detecta y se explica en
  lugar de fallar con un error opaco.
- **Los valores se convierten a texto con reglas explicitas.**  Excel guarda
  ``Q00525499`` como texto pero ``4281847`` como numero; sin control, Python lo
  devolveria como ``4281847.0`` y el codigo grabado seria incorrecto.  Ese caso
  esta cubierto por pruebas.
"""

from __future__ import annotations

import datetime as _dt
import io
from typing import Any

from .batch_engine import parse_csv_text

# WHY: Extensiones que este modulo sabe abrir directamente.
EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xltx", ".xltm")
LEGACY_EXCEL_EXTENSIONS = (".xls",)
TEXT_EXTENSIONS = (".csv", ".txt", ".tsv")

# WHY: Firma ZIP; un XLSX es un ZIP. Permite reconocer el formato aunque el
# archivo llegue con extension equivocada, que ocurre con adjuntos renombrados.
_ZIP_MAGIC = b"PK\x03\x04"
# WHY: Firma del formato binario heredado de Excel (OLE2 Compound File).
_OLE_MAGIC = b"\xd0\xcf\x11\xe0"

MAX_PREVIEW = 500
DEFAULT_PREVIEW = 25


# WHY: Convierte una celda de Excel en el texto que realmente debe grabarse, sin
# introducir decimales ni notacion cientifica que no existian en el activo.
def cell_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Un identificador entero guardado como numero debe volver como entero.
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, _dt.datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, _dt.time):
        return value.isoformat()
    return str(value).strip()


# WHY: Identifica el formato real por contenido y no solo por extension, porque un
# archivo renombrado es un fallo comun y el mensaje de error debe ser util.
def detect_format(filename: str, raw: bytes) -> str:
    name = (filename or "").lower()
    if raw.startswith(_ZIP_MAGIC):
        return "xlsx"
    if raw.startswith(_OLE_MAGIC):
        return "xls_legacy"
    if name.endswith(EXCEL_EXTENSIONS):
        return "xlsx"
    if name.endswith(LEGACY_EXCEL_EXTENSIONS):
        return "xls_legacy"
    return "text"


# WHY: Lista las hojas para que el usuario elija; nunca se asume la primera, que
# en libros reales suele ser una portada o un instructivo.
def list_sheets(raw: bytes) -> list[str]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


# WHY: Extrae una hoja como matriz de texto reutilizando despues la misma logica de
# encabezados que el CSV, para que ambos formatos se comporten igual.
def _sheet_matrix(raw: bytes, sheet: str | None) -> tuple[str, list[list[str]]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        if sheet and sheet not in wb.sheetnames:
            raise ValueError(f"La hoja '{sheet}' no existe en el libro")
        ws = wb[sheet] if sheet else wb[wb.sheetnames[0]]
        matrix: list[list[str]] = []
        for row in ws.iter_rows(values_only=True):
            cells = [cell_to_text(v) for v in row]
            if any(c.strip() for c in cells):
                matrix.append(cells)
        return ws.title, matrix
    finally:
        wb.close()


# WHY: Recorta columnas totalmente vacias a la derecha, que Excel agrega cuando
# alguien dio formato a celdas sin escribir en ellas.
def _trim_empty_columns(matrix: list[list[str]]) -> list[list[str]]:
    if not matrix:
        return matrix
    width = max(len(r) for r in matrix)
    keep = [i for i in range(width) if any(str(r[i]).strip() for r in matrix if i < len(r))]
    if not keep:
        return []
    last = keep[-1]
    return [list(r)[: last + 1] + [""] * max(0, last + 1 - len(r)) for r in matrix]


# WHY: Aplica el mismo contrato de encabezados del CSV sobre una matriz ya leida,
# de modo que 'auto / si / no' signifique exactamente lo mismo en ambos formatos.
def rows_from_matrix(matrix: list[list[str]], has_header: bool | None) -> tuple[list[str], list[dict[str, str]]]:
    matrix = _trim_empty_columns(matrix)
    if not matrix:
        raise ValueError("La hoja no contiene datos")
    width = max(len(r) for r in matrix)
    if has_header is None:
        first = matrix[0]
        rest = matrix[1:]
        # Heuristica deliberadamente conservadora: la primera fila es encabezado
        # solo si no parece un dato.  Un identificador suele contener digitos; un
        # encabezado normalmente no.  Ante la duda se trata como dato, porque
        # perder el primer registro es peor que mostrar 'col_1'.
        looks_texty = all(c.strip() and not any(ch.isdigit() for ch in c) for c in first if c.strip())
        has_data_below = bool(rest)
        has_header = bool(looks_texty and has_data_below)
    if has_header:
        headers = [str(v).strip() or f"col_{i+1}" for i, v in enumerate(matrix[0])]
        body = matrix[1:]
    else:
        headers = ["value"] if width == 1 else [f"col_{i+1}" for i in range(width)]
        body = matrix
    headers = _unique_headers(headers)
    rows: list[dict[str, str]] = []
    for raw_row in body:
        padded = list(raw_row) + [""] * (len(headers) - len(raw_row))
        row = {headers[i]: str(padded[i]).strip() for i in range(len(headers))}
        if any(row.values()):
            rows.append(row)
    return headers, rows


# WHY: Dos columnas con el mismo titulo destruirian silenciosamente una de ellas al
# construir el diccionario de la fila; se desambiguan de forma visible.
def _unique_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for h in headers:
        count = seen.get(h, 0) + 1
        seen[h] = count
        out.append(h if count == 1 else f"{h}_{count}")
    return out


# WHY: Punto unico de entrada de datos tabulares para la API; devuelve siempre la
# misma forma de respuesta venga de CSV o de Excel, para que el frontend tenga un
# solo camino de codigo y el mapeo de columnas no dependa del formato de origen.
def inspect_tabular(filename: str, raw: bytes, header_mode: str = "auto",
                    sheet: str | None = None, preview_limit: int = DEFAULT_PREVIEW) -> dict[str, Any]:
    if header_mode not in {"auto", "yes", "no"}:
        raise ValueError("header_mode debe ser auto, yes o no")
    has_header = {"yes": True, "no": False, "auto": None}[header_mode]
    preview_limit = max(1, min(int(preview_limit or DEFAULT_PREVIEW), MAX_PREVIEW))

    kind = detect_format(filename, raw)
    if kind == "xls_legacy":
        raise ValueError(
            "El formato .xls heredado no es compatible. Abra el archivo en Excel o "
            "LibreOffice y use «Guardar como» en formato .xlsx o .csv."
        )

    sheets: list[str] = []
    sheet_used: str | None = None
    if kind == "xlsx":
        sheets = list_sheets(raw)
        if not sheets:
            raise ValueError("El libro no contiene hojas")
        sheet_used, matrix = _sheet_matrix(raw, sheet)
        headers, rows = rows_from_matrix(matrix, has_header)
        delimiter = None
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        headers, rows = parse_csv_text(text, has_header=has_header)
        delimiter = _sniff_delimiter(text)

    return {
        "filename": filename,
        "format": "xlsx" if kind == "xlsx" else "text",
        "sheets": sheets,
        "sheet": sheet_used,
        "delimiter": delimiter,
        "headers": headers,
        "count": len(rows),
        "rows": rows,
        "preview": rows[:preview_limit],
        "preview_limit": preview_limit,
        "header_mode": header_mode,
    }


# WHY: Se informa el delimitador detectado para que el operador pueda confirmar que
# el archivo se leyo como esperaba antes de acomodar equipo fisico.
def _sniff_delimiter(text: str) -> str | None:
    import csv

    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter
    except csv.Error:
        return None
