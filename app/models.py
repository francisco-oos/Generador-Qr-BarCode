"""Validated configuration and API contracts for the marking system.

All machine-, jig-, scanner- and asset-specific behavior is modeled as data so the
rendering core can scale to new equipment without hardcoded branches.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


ElementKind = Literal[
    "text", "code128", "code39", "qr", "datamatrix", "rect", "line", "image"
]


# WHY: Regla declarativa de captura por campo, incluido prefijo/sufijo manual y política para valores importados.
class InputRule(BaseModel):
    """How one logical field behaves during manual capture vs. imported lists.

    A common INOVA rule is: the operator can type only ``525499`` manually and
    the UI adds ``Q00``; a CSV value such as ``Q00525499`` is accepted exactly
    as supplied.  This prevents double-prefixing batch imports.
    """
    field: str
    manual_prefix_enabled: bool = False
    manual_prefix: str = Field(default="", max_length=64)
    manual_suffix_enabled: bool = False
    manual_suffix: str = Field(default="", max_length=64)
    imported_values: Literal["as_is", "ensure_prefix_suffix"] = "as_is"
    uppercase: bool = False
    # WHY: Alternativa a ``uppercase`` para flujos cuyo identificador oficial va en
    # minusculas.  Si ambos quedaran activos gana ``uppercase``, y el validador lo
    # impide en lugar de dejar una plantilla con comportamiento ambiguo.
    lowercase: bool = False
    trim: bool = True
    # WHY: Rellena con ceros a la izquierda hasta un ancho fijo.  Existe porque una
    # exportacion de Excel pierde los ceros iniciales de ``00184`` al tratarlo como
    # numero, y reponerlos a mano es justo el tipo de error que llega al grabado.
    # ``0`` desactiva la regla; nunca recorta un valor mas largo que el ancho.
    pad_zeros_to: int = Field(default=0, ge=0, le=64)
    description: str = ""

    # WHY: Dos conversiones de caja opuestas en la misma regla no tienen un
    # resultado previsible para el usuario; se rechaza al guardar la plantilla.
    @model_validator(mode="after")
    def case_rules_not_contradictory(self) -> "InputRule":
        if self.uppercase and self.lowercase:
            raise ValueError("uppercase and lowercase cannot both be enabled for the same field")
        return self

    # WHY: Normaliza y valida el nombre del campo para impedir reglas ambiguas o claves peligrosas.
    @field_validator("field")
    @classmethod
    def input_field_safe(cls, value: str) -> str:
        import re
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("input rule field must be a simple identifier")
        return value


# WHY: Campo compuesto a partir de otros campos ya normalizados.
class DerivedField(BaseModel):
    """Concatenate existing fields into a new one, declaratively.

    Existe para cubrir el caso real ``{prefijo}{serial}`` o
    ``{modelo}-{economico}`` sin obligar a preparar el CSV fuera del programa.

    Deliberadamente NO es un lenguaje de expresiones: solo sustitucion de
    marcadores y texto literal.  Una calculadora completa dentro de la plantilla
    seria imposible de auditar y convertiria un archivo de configuracion en
    codigo ejecutable.  Si un caso necesita mas que concatenar, corresponde
    resolverlo en el origen de datos.
    """
    field: str
    expression: str = Field(min_length=1, max_length=400)
    # WHY: Por defecto no pisa un valor que ya venia en el CSV; el archivo del area
    # es la fuente autoritativa salvo que el usuario decida lo contrario.
    overwrite: bool = False
    description: str = ""

    # WHY: Mismo formato de identificador que el resto de campos del sistema.
    @field_validator("field")
    @classmethod
    def derived_field_safe(cls, value: str) -> str:
        import re
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("derived field must be a simple identifier")
        return value




# WHY: El modo de marcado describe la estrategia física del trabajo sin
# contaminar la definición matemática del QR/barcode. Vive en la plantilla como
# valor validado y puede sobreescribirse temporalmente por trabajo.
class MarkingMode(BaseModel):
    polarity: Literal["positive", "negative"] = "positive"
    polarity_scope: Literal["codes", "all"] = "codes"
    negative_field: Literal["islands", "template"] = "islands"
    field_margin_mm: float = Field(default=0.0, ge=0.0, le=100.0)
    # Semántica acordada: compensación TOTAL deseada del ancho del módulo; la
    # geometría protege la mitad por cada lado. 0 significa no compensar.
    kerf_compensation_mm: float = Field(default=0.0, ge=0.0, le=10.0)
    validated_on: str = Field(default="", max_length=1000, validation_alias=AliasChoices("validated_on", "validado_sobre"))

    # WHY: Centraliza compatibilidad del contrato para impedir combinaciones silenciosamente ambiguas al crecer el modelo.
    @model_validator(mode="after")
    def validate_combination(self) -> "MarkingMode":
        # codes+template exige una segunda operación física para que texto positivo
        # coexista con un campo completo rebajado. Se representa para investigación,
        # pero el renderer productivo la rechaza hasta validación física.
        if self.polarity == "positive":
            return self
        return self

    # WHY: Evita repetir comparaciones de cadenas en render/preflight y conserva una única semántica de polaridad.
    @property
    def is_negative(self) -> bool:
        return self.polarity == "negative"

    def physical_fingerprint(self) -> tuple:
        """Campos que cambian físicamente la pieza; validated_on es sólo evidencia."""
        return (
            self.polarity, self.polarity_scope, self.negative_field,
            round(self.field_margin_mm, 6), round(self.kerf_compensation_mm, 6),
        )


# WHY: Describe un objeto visual de plantilla con geometría, fuente de datos y propiedades específicas de cada simbología.
class ElementSpec(BaseModel):
    kind: ElementKind
    x_mm: float = Field(ge=0)
    y_mm: float = Field(ge=0)
    source: str | None = None
    literal: str | None = None
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    font_size_mm: float = Field(default=4.0, gt=0)
    align: Literal["left", "center", "right"] = "center"
    module_mm: float | None = Field(default=None, gt=0)
    error_correction: Literal["L", "M", "Q", "H"] = "M"
    stroke_mm: float = Field(default=0.25, gt=0)
    label: str | None = None
    # WHY: Rotacion en grados, sentido horario, alrededor del centro geometrico del
    # propio elemento. Se guarda en el modelo (no como un transform escrito a mano)
    # para que el editor, la vista real y ambos SVG produzcan exactamente el mismo
    # resultado y para que el valor pueda medirse y devolverse desde Inkscape.
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    # WHY: Quiet zone propia del elemento, en modulos. ``None`` hereda el perfil de
    # calidad, que es el comportamiento seguro por defecto. Se permite bajarla porque
    # hay piezas donde fisicamente no cabe el margen recomendado, pero el motor emite
    # una advertencia explicita: el riesgo se informa, no se oculta ni se bloquea.
    quiet_modules: int | None = Field(default=None, ge=0, le=64)
    # WHY (v0.7.1): Estrategia de grabado por elemento de codigo. ``positive``
    # conserva el comportamiento historico: el laser marca barras/modulos oscuros.
    # ``negative_background`` graba el fondo/espacios y deja barras/modulos en
    # relieve. Esta segunda opcion sirve para superficies de poco contraste donde
    # el taller quiera frotar marcador/pintura sobre el relieve despues del laser.
    # No se llama "inverse barcode" porque la polaridad optica final depende del
    # acabado fisico y del lector, no solamente del SVG.
    # DEPRECATED compatibility v0.7.1: el modo productivo ahora vive en TemplateSpec.marking_mode.
    engraving_mode: Literal["positive", "negative_background"] = "positive"
    # WHY (v0.8.0 final): Las imágenes se embeben en la plantilla para que un logo no
    # dependa de una ruta local que podría cambiar entre Windows/Linux/macOS. El backend
    # limita tamaño y sanea SVG antes de serializarlo; no se permiten URLs externas.
    image_data_uri: str | None = Field(default=None, max_length=4_500_000)
    image_processing: Literal["auto", "vector", "threshold", "floyd_steinberg"] = "auto"
    image_threshold: int = Field(default=128, ge=0, le=255)
    # DPI de muestreo del arte raster -> geometría 1-bit. No es potencia/velocidad ni
    # pretende ser una receta física de la máquina.
    image_dpi: int = Field(default=254, ge=50, le=1200)
    image_preserve_aspect: bool = True
    image_source_name: str = Field(default="", max_length=255)

    # WHY: Normaliza la rotacion al rango 0-360 para que -90 y 270 produzcan el mismo
    # archivo y las comparaciones de plantillas no dependan de como se escribio el valor.
    @field_validator("rotation_deg")
    @classmethod
    def rotation_normalized(cls, value: float) -> float:
        return round(float(value) % 360.0, 4)
    # WHY: Nombre estable elegido por el usuario. Se convierte en el ``id`` del SVG
    # (``barcode_serial``), que es lo que permite medir un objeto en Inkscape y
    # devolver esa medida a la plantilla sin adivinar de que elemento se trata.
    name: str | None = Field(default=None, max_length=80)
    # WHY: Capa semantica de destino. Si no se indica, se deduce del tipo de elemento;
    # declararla permite, por ejemplo, mandar un rectangulo a la capa de registro.
    layer: str | None = Field(default=None, max_length=40)

    # WHY: Restringe el nombre a un identificador apto para XML, ficheros y referencias externas.
    @field_validator("name")
    @classmethod
    def name_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        import re
        cleaned = value.strip()
        if not cleaned:
            return None
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", cleaned):
            raise ValueError("element name must start with a letter/underscore and use letters, numbers, _ or -")
        return cleaned

    # WHY: Exige que un elemento de contenido tenga una fuente o literal coherente, evitando SVG vacíos difíciles de detectar.
    @model_validator(mode="after")
    def validate_content_source(self) -> "ElementSpec":
        if self.kind in {"text", "code128", "code39", "qr", "datamatrix"}:
            if not self.source and self.literal is None:
                raise ValueError(f"{self.kind} requires source or literal")
        if self.kind == "image":
            if not self.image_data_uri:
                raise ValueError("image requires image_data_uri")
            if self.width_mm is None or self.height_mm is None:
                raise ValueError("image requires width_mm and height_mm")
            # Sólo se aceptan data URIs embebidas de los tres formatos que el backend
            # sabe sanear/convertir. Rechazar aquí da feedback al guardar la plantilla,
            # no varios pasos después durante un render de producción.
            uri = self.image_data_uri.lower().strip()
            supported = (
                uri.startswith("data:image/png;base64,"),
                uri.startswith("data:image/jpeg;base64,"),
                uri.startswith("data:image/svg+xml;base64,"),
            )
            if not any(supported):
                raise ValueError("image_data_uri must be an embedded PNG, JPEG or SVG data URI")
            is_svg = supported[2]
            if is_svg and self.image_processing not in {"auto", "vector"}:
                raise ValueError("SVG image elements support auto/vector processing only")
            if not is_svg and self.image_processing == "vector":
                raise ValueError("PNG/JPEG image elements cannot use vector processing; choose auto, threshold or floyd_steinberg")
        if self.engraving_mode != "positive" and self.kind not in {"code128", "code39", "qr", "datamatrix"}:
            raise ValueError("negative_background is only valid for barcode/2D code elements")
        return self


# WHY: Contrato completo de una plantilla visual versionada y libre de dependencias de una grabadora concreta.
class TemplateSpec(BaseModel):
    id: str
    name: str
    version: str = "1.0"
    category: str
    description: str = ""
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    quality_profile: str
    calibration_required: bool = True
    expected_fields: list[str] = Field(default_factory=list)
    input_rules: list[InputRule] = Field(default_factory=list)
    # WHY: Se aplican DESPUES de input_rules para que un campo compuesto use los
    # valores ya normalizados y no el texto crudo del archivo.
    derived_fields: list[DerivedField] = Field(default_factory=list)
    marking_mode: MarkingMode = Field(default_factory=MarkingMode)
    elements: list[ElementSpec]
    metadata: dict[str, Any] = Field(default_factory=dict)

    # WHY: Restringe el identificador de plantilla a un formato estable apto para archivos, API y referencias históricas.
    @field_validator("id")
    @classmethod
    def id_safe(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("template id may contain letters, numbers, _ and - only")
        return value


# WHY: Límites de legibilidad y robustez reutilizables por distintas plantillas.
class QualityProfile(BaseModel):
    id: str
    name: str
    code128_module_mm: float = Field(gt=0)
    code128_quiet_modules: int = Field(default=10, ge=10)
    code128_bar_height_mm: float = Field(gt=0)
    qr_module_mm: float = Field(gt=0)
    qr_quiet_modules: int = Field(default=4, ge=4)
    datamatrix_module_mm: float = Field(gt=0)
    datamatrix_quiet_modules: int = Field(default=1, ge=1)
    render_dpi: int = Field(default=600, ge=150, le=2400)
    notes: list[str] = Field(default_factory=list)


# WHY: Describe capacidades de una grabadora/controlador sin conceder permiso para operarla directamente.
class MachineProfile(BaseModel):
    id: str
    name: str
    controller: str
    connection: str
    bed_width_mm: float = Field(gt=0)
    bed_height_mm: float = Field(gt=0)
    laser_wavelength_nm: int | None = None
    optical_power_w: float | None = None
    vector_formats: list[str] = Field(default_factory=list)
    raster_formats: list[str] = Field(default_factory=list)
    recommended_software: list[str] = Field(default_factory=list)
    direct_machine_output_enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


# WHY: Describe simbologías y restricciones conocidas de un lector para validar compatibilidad de diseño.
class ScannerProfile(BaseModel):
    id: str
    name: str
    technology: str
    interfaces: list[str] = Field(default_factory=list)
    symbologies: list[str] = Field(default_factory=list)
    supports_qr: bool = False
    supports_datamatrix: bool = False
    minimum_print_contrast_percent: float | None = None
    notes: list[str] = Field(default_factory=list)


# WHY: Geometría repetitiva de una base física usada para calcular posiciones.
class JigGrid(BaseModel):
    rows: int = Field(ge=1, le=50)
    cols: int = Field(ge=1, le=50)
    origin_x_mm: float = Field(ge=0)
    origin_y_mm: float = Field(ge=0)
    pitch_x_mm: float = Field(gt=0)
    pitch_y_mm: float = Field(gt=0)
    mark_offset_x_mm: float = Field(ge=0)
    mark_offset_y_mm: float = Field(ge=0)
    slot_width_mm: float = Field(gt=0)
    slot_height_mm: float = Field(gt=0)


# WHY: Define una base/jig, su capacidad y sus referencias de calibración.
class JigProfile(BaseModel):
    id: str
    name: str
    machine_profile_id: str
    target_category: str
    template_id: str
    grid: JigGrid
    calibration_required: bool = True
    disabled_slots: list[int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # WHY: Calcula capacidad efectiva desde slots habilitados para que el batch no dependa de cifras duplicadas.
    @property
    def capacity(self) -> int:
        return self.grid.rows * self.grid.cols - len(set(self.disabled_slots))


# WHY: Entrada para renderizar una marca individual con datos y modo de captura explícitos.
class RenderRequest(BaseModel):
    template_id: str
    data: dict[str, str]
    capture_mode: Literal["manual", "import"] = "manual"
    output: Literal["svg", "png"] = "svg"
    dpi: int | None = Field(default=None, ge=150, le=2400)
    # WHY: El usuario elige el artefacto; el sistema no impone generar ambos.
    #
    # WHY (alias): los endpoints de artefacto unico llaman a este concepto ``svg_mode``,
    # mientras que los de lote lo llaman ``export_mode`` porque ademas admiten ``both``.
    # Un cliente que usara el nombre del otro endpoint recibiria en silencio el modo por
    # defecto: Pydantic ignora los campos desconocidos y el error solo se descubriria al
    # abrir el archivo. Aceptar ambos nombres elimina esa clase de fallo silencioso.
    svg_mode: Literal["editable", "production"] = Field(
        default="production", validation_alias=AliasChoices("svg_mode", "export_mode")
    )
    # WHY: Solo aplica a produccion. Se declara aparte del modo para que activar
    # curvas sea una decision consciente y visible, no un efecto secundario.
    text_as_paths: bool = False
    # WHY: Permite probar otra estrategia sin contaminar la plantilla validada.
    marking_mode_override: MarkingMode | None = None


# WHY: Seleccion de artefactos de un trabajo. "both" existe para calibracion y
# depuracion, pero no es el valor por defecto para no duplicar miles de archivos.
ExportMode = Literal["editable", "production", "both"]


# WHY: Vincula una fila de datos con una posición física y, opcionalmente, con la identidad observada por el operador.
class BatchAssignment(BaseModel):
    slot_index: int = Field(ge=0)
    row_index: int = Field(ge=0)
    physical_id: str | None = None


# WHY: Contrato de exportación de un lote colocado sobre jig con trazabilidad y confirmación física.
class BatchExportRequest(BaseModel):
    template_id: str
    jig_id: str
    material_preset_id: int | None = Field(default=None, ge=1)
    rows: list[dict[str, str]]
    assignments: list[BatchAssignment]
    require_physical_confirmation: bool = True
    output_dpi: int | None = Field(default=None, ge=150, le=2400)
    export_mode: ExportMode = "production"
    text_as_paths: bool = False
    marking_mode_override: MarkingMode | None = None


# WHY: Entrada controlada para crear numeraciones conocidas sin inferir seriales perdidos.
class SeriesGenerateRequest(BaseModel):
    field: str = Field(default="value", min_length=1, max_length=64)
    prefix: str = Field(default="", max_length=64)
    start: int = Field(default=1, ge=0)
    count: int = Field(default=100, ge=1, le=100000)
    width: int = Field(default=0, ge=0, le=32)
    suffix: str = Field(default="", max_length=64)

    # WHY: Valida el campo de salida de una serie con las mismas reglas usadas por plantillas y CSV.
    @field_validator("field")
    @classmethod
    def field_safe(cls, value: str) -> str:
        import re
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("field must be a simple identifier")
        return value


# WHY: Entrada mínima para comparar lo esperado contra lo leído después del grabado.
class ScanVerifyRequest(BaseModel):
    expected: str
    scanned: str
    normalize: bool = False


# WHY: Envuelve una plantilla antes de persistirla y fuerza validación Pydantic completa.
class TemplateSaveRequest(BaseModel):
    template: TemplateSpec


# WHY: Permite previsualizar una plantilla todavía no guardada usando el mismo motor de producción.
class TemplatePreviewRequest(BaseModel):
    """Render an unsaved visual-designer draft without persisting it."""
    template: TemplateSpec
    data: dict[str, str] = Field(default_factory=dict)
    capture_mode: Literal["manual", "import"] = "manual"
    output: Literal["svg", "png"] = "svg"
    dpi: int | None = Field(default=None, ge=150, le=2400)
    # WHY (alias): mismo motivo que en RenderRequest; ver la nota alli.
    svg_mode: Literal["editable", "production"] = Field(
        default="production", validation_alias=AliasChoices("svg_mode", "export_mode")
    )
    text_as_paths: bool = False
    marking_mode_override: MarkingMode | None = None


# WHY: Solicita un SVG por registro para escenarios sin jig o composición posterior en el software de la máquina.


# WHY: Solicita una evaluación de legibilidad sobre una plantilla guardada o borrador visual sin controlar el láser.
class CodeQualityCheckRequest(BaseModel):
    template: TemplateSpec
    data: dict[str, str] = Field(default_factory=dict)
    capture_mode: Literal["manual", "import"] = "manual"
    scanner_profile_id: str | None = None
    dpi: int | None = Field(default=None, ge=150, le=2400)
    digital_stress: bool = True
    marking_mode_override: MarkingMode | None = None

# WHY: Contrato dedicado para comparar lectura positiva vs. artefacto de ablación negativo sin tocar la plantilla guardada.
class MarkingComparisonRequest(BaseModel):
    template: TemplateSpec
    data: dict[str, str] = Field(default_factory=dict)
    capture_mode: Literal["manual", "import"] = "manual"
    negative_mode: MarkingMode = Field(default_factory=lambda: MarkingMode(polarity="negative"))
    dpi: int = Field(default=600, ge=150, le=2400)
    # WHY: PNG is optional because SVG is the canonical preview and large base64
    # payloads are unnecessary during normal interaction.  When requested, both
    # PNGs are rasterized from the exact SVGs returned by this endpoint.
    include_png: bool = False


# WHY: Solicita un cupón físico de cuatro paneles para caracterizar polaridad sin inventar ajustes de máquina.
class MarkingCouponRequest(BaseModel):
    template: TemplateSpec
    data: dict[str, str] = Field(default_factory=dict)
    capture_mode: Literal["manual", "import"] = "manual"
    negative_mode: MarkingMode = Field(default_factory=lambda: MarkingMode(polarity="negative"))


class BulkTemplateExportRequest(BaseModel):
    """Export one SVG per row using a saved template.

    This is intentionally geometry-only. Machine control remains in LightBurn,
    Sculpfun Space or the configured handoff application.
    """
    template_id: str
    rows: list[dict[str, str]] = Field(min_length=1, max_length=10000)
    filename_field: str | None = Field(default=None, max_length=64)
    # WHY: Patron libre tipo ``{economico}_{serial}``; se sanea despues contra las
    # restricciones de nombre de Windows, Linux y macOS.
    filename_pattern: str | None = Field(default=None, max_length=200)
    export_mode: ExportMode = "production"
    text_as_paths: bool = False
    marking_mode_override: MarkingMode | None = None


# WHY: Envuelve un jig antes de persistirlo y reutiliza la validación del modelo.
class JigSaveRequest(BaseModel):
    jig: JigProfile


# WHY: Datos firmados que identifican edición, vigencia y capacidades de una licencia.
class LicensePayload(BaseModel):
    license_id: str
    organization: str
    edition: str
    issued_at: str
    expires_at: str | None = None
    features: list[str]
    machine_limit: int = Field(default=1, ge=1)
    server_oficina_ready: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


# WHY: Entrada textual para interpretar un dump GRBL sin abrir un puerto serial.
class GrblParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200000)


# WHY: Parámetros de una lectura GRBL segura y explícita.
class GrblProbeRequest(BaseModel):
    port: str = Field(min_length=1, max_length=256)
    baud: int = Field(default=115200, ge=1200, le=1000000)
    machine_profile_id: str | None = None


# WHY: Permite editar reglas de captura sin reemplazar manualmente todo el JSON de una plantilla.
class TemplateInputRuleUpdateRequest(BaseModel):
    template_id: str
    field: str
    manual_prefix_enabled: bool = False
    manual_prefix: str = Field(default="", max_length=64)
    manual_suffix_enabled: bool = False
    manual_suffix: str = Field(default="", max_length=64)
    imported_values: Literal["as_is", "ensure_prefix_suffix"] = "as_is"
    uppercase: bool = False


# WHY: Referencia un artefacto local previamente descubierto para importarlo de forma controlada.
class LocalArtifactImportRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    machine_profile_id: str | None = None
# WHY: Coordenada medida de una referencia física del jig.
class CalibrationPoint(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    x_mm: float
    y_mm: float


# WHY: Agrupa las mediciones necesarias para comparar geometría esperada y real.
class CalibrationEvaluationRequest(BaseModel):
    jig_id: str
    measured: list[CalibrationPoint] = Field(min_length=2, max_length=10)


# WHY: Captura un ajuste que el área ya probó, junto con contexto suficiente para no reutilizarlo fuera de su superficie/máquina.
class ShopMaterialPresetRequest(BaseModel):
    """A material/surface setting already proven by the workshop.

    This record never drives the laser directly.  It is audit/configuration data
    that can be selected into a marking job and re-entered/verified in LightBurn,
    Sculpfun Space or LaserGRBL.
    """
    name: str = Field(min_length=1, max_length=160)
    machine_profile_id: str
    material: str = Field(min_length=1, max_length=160)
    surface_or_model: str = Field(default="", max_length=200)
    operation: str = Field(default="engrave", max_length=64)
    speed_mm_min: float = Field(gt=0, le=200000)
    power_percent: float = Field(gt=0, le=100)
    passes: int = Field(default=1, ge=1, le=100)
    interval_mm: float | None = Field(default=None, gt=0, le=5)
    focus_reference_mm: float | None = Field(default=None, gt=0, le=500)
    laser_mode: Literal["M3", "M4", "unknown"] = "unknown"
    validated_on_exact_machine_surface: bool = False
    notes: str = Field(default="", max_length=2000)
    marking_mode: MarkingMode | None = None
    scanner_profile_id: str | None = Field(default=None, max_length=160)
    scan_validation: Literal["not_tested", "pass", "fail", "partial"] = "not_tested"
    scan_attempts: int | None = Field(default=None, ge=0, le=1000)
    scan_successes: int | None = Field(default=None, ge=0, le=1000)

    # WHY: Una evidencia de lectura imposible (más éxitos que intentos o resultado sin intentos) degradaría la biblioteca validada.
    @model_validator(mode="after")
    def validate_scan_evidence(self) -> "ShopMaterialPresetRequest":
        if self.scan_attempts is not None and self.scan_successes is not None and self.scan_successes > self.scan_attempts:
            raise ValueError("scan_successes cannot exceed scan_attempts")
        if self.scan_validation != "not_tested" and (self.scan_attempts is None or self.scan_successes is None):
            raise ValueError("scan_attempts and scan_successes are required when scan_validation is recorded")
        if self.scan_validation == "pass" and self.scan_attempts is not None and self.scan_successes != self.scan_attempts:
            raise ValueError("scan_validation=pass requires all recorded attempts to succeed")
        return self

