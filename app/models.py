"""Validated configuration and API contracts for the marking system.

All machine-, jig-, scanner- and asset-specific behavior is modeled as data so the
rendering core can scale to new equipment without hardcoded branches.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


ElementKind = Literal[
    "text", "code128", "code39", "qr", "datamatrix", "rect", "line"
]


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
    trim: bool = True
    description: str = ""

    @field_validator("field")
    @classmethod
    def input_field_safe(cls, value: str) -> str:
        import re
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("input rule field must be a simple identifier")
        return value


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

    @model_validator(mode="after")
    def validate_content_source(self) -> "ElementSpec":
        if self.kind in {"text", "code128", "code39", "qr", "datamatrix"}:
            if not self.source and self.literal is None:
                raise ValueError(f"{self.kind} requires source or literal")
        return self


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
    elements: list[ElementSpec]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def id_safe(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("template id may contain letters, numbers, _ and - only")
        return value


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

    @property
    def capacity(self) -> int:
        return self.grid.rows * self.grid.cols - len(set(self.disabled_slots))


class RenderRequest(BaseModel):
    template_id: str
    data: dict[str, str]
    capture_mode: Literal["manual", "import"] = "manual"
    output: Literal["svg", "png"] = "svg"
    dpi: int | None = Field(default=None, ge=150, le=2400)


class BatchAssignment(BaseModel):
    slot_index: int = Field(ge=0)
    row_index: int = Field(ge=0)
    physical_id: str | None = None


class BatchExportRequest(BaseModel):
    template_id: str
    jig_id: str
    material_preset_id: int | None = Field(default=None, ge=1)
    rows: list[dict[str, str]]
    assignments: list[BatchAssignment]
    require_physical_confirmation: bool = True
    output_dpi: int | None = Field(default=None, ge=150, le=2400)


class SeriesGenerateRequest(BaseModel):
    field: str = Field(default="manufacturer_id", min_length=1, max_length=64)
    prefix: str = Field(default="", max_length=64)
    start: int = Field(default=1, ge=0)
    count: int = Field(default=100, ge=1, le=100000)
    width: int = Field(default=0, ge=0, le=32)
    suffix: str = Field(default="", max_length=64)

    @field_validator("field")
    @classmethod
    def field_safe(cls, value: str) -> str:
        import re
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("field must be a simple identifier")
        return value


class ScanVerifyRequest(BaseModel):
    expected: str
    scanned: str
    normalize: bool = False


class TemplateSaveRequest(BaseModel):
    template: TemplateSpec


class JigSaveRequest(BaseModel):
    jig: JigProfile


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


class GrblParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200000)


class GrblProbeRequest(BaseModel):
    port: str = Field(min_length=1, max_length=256)
    baud: int = Field(default=115200, ge=1200, le=1000000)
    machine_profile_id: str | None = None


class TemplateInputRuleUpdateRequest(BaseModel):
    template_id: str
    field: str
    manual_prefix_enabled: bool = False
    manual_prefix: str = Field(default="", max_length=64)
    manual_suffix_enabled: bool = False
    manual_suffix: str = Field(default="", max_length=64)
    imported_values: Literal["as_is", "ensure_prefix_suffix"] = "as_is"
    uppercase: bool = False


class LocalArtifactImportRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    machine_profile_id: str | None = None
class CalibrationPoint(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    x_mm: float
    y_mm: float


class CalibrationEvaluationRequest(BaseModel):
    jig_id: str
    measured: list[CalibrationPoint] = Field(min_length=2, max_length=10)


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

