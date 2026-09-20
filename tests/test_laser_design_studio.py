from __future__ import annotations
import base64, io
from PIL import Image, ImageDraw
from app.laser_design_studio import (
    PapercutRequest, HalftoneRequest, StencilRequest, BridgeCouponRequest,
    generate_papercut, generate_halftone, generate_stencil,
    generate_bridge_coupon, capabilities,
)


def png_uri(drawer) -> str:
    im = Image.new('L', (96, 96), 255)
    d = ImageDraw.Draw(im)
    drawer(d)
    out = io.BytesIO(); im.save(out, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()


def test_papercut_is_deterministic_and_cuttable_contract():
    req = PapercutRequest(seed=42, rows=6, cols=6, motif='star', min_bridge_mm=1.2)
    a = generate_papercut(req); b = generate_papercut(req)
    assert a['svg'] == b['svg']
    assert a['recipe']['design_genome'].startswith('papercut:42')
    assert a['machine_control'] is False
    assert 'data-operation="cut"' in a['svg']
    assert a['preflight']['component_count'] == 1


def test_halftone_limits_hole_size_to_keep_web():
    uri = png_uri(lambda d: d.rectangle((0,0,95,95), fill=0))
    r = generate_halftone(HalftoneRequest(
        image_data_uri=uri, width_mm=80, height_mm=80, margin_mm=4,
        cell_mm=5, min_diameter_mm=.5, max_diameter_mm=9,
        min_bridge_mm=1.5, shape='circle'
    ))
    assert r['recipe']['effective_max_diameter_mm'] < 9
    assert r['preflight']['min_web_mm'] >= 1.45
    assert any('limitado automáticamente' in w for w in r['warnings'])
    assert r['preflight']['component_count'] == 1


def test_stencil_auto_bridges_interior_island():
    def draw(d):
        d.ellipse((15,15,80,80), fill=0)
        d.ellipse((35,35,60,60), fill=255)
    r = generate_stencil(StencilRequest(
        image_data_uri=png_uri(draw), width_mm=100, height_mm=100,
        threshold=128, frame_mm=4, bridge_width_mm=2.0, sample_max_px=80,
        max_auto_bridges=10, min_bridge_mm=.8,
    ))
    assert r['bridge_plan']['auto_bridges'] >= 1
    assert r['bridge_plan']['remaining_islands'] == 0
    assert r['preflight']['component_count'] == 1
    assert 'layer_guides' in r['preview_svg']
    assert 'layer_guides' not in r['svg']


def test_bridge_coupon_is_reproducible_document_only():
    r = generate_bridge_coupon(BridgeCouponRequest(widths_mm=[.6, 1.0, 1.5]))
    assert r['kind'] == 'bridge-coupon'
    assert r['machine_control'] is False
    assert len(r['calibration_steps']) == 3
    assert 'G0 ' not in r['svg'] and 'M3 ' not in r['svg']


def test_capabilities_reserve_optional_providers_without_requiring_them():
    c = capabilities()
    assert c['engines']['papercut']['available'] is True
    assert c['engines']['nesting']['available'] is False
    assert c['openai_lab']['cut_survival_map'] is True
