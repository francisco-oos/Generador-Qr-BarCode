import io
import json
import zipfile

import app.machine_bridge as mb


def sample_clb() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8"?>
<MaterialLibrary>
  <Material name="INOVA yellow housing">
    <Entry Thickness="2.0" Desc="Existing shop-visible engraving">
      <CutSetting type="Scan">
        <name Value="INOVA visible"/>
        <speed Value="3200"/>
        <minPower Value="18"/>
        <maxPower Value="32"/>
        <interval Value="0.08"/>
        <numPasses Value="1"/>
      </CutSetting>
    </Entry>
  </Material>
</MaterialLibrary>'''


def test_parse_grbl_dump_extracts_controller_limits_and_laser_mode():
    parsed = mb.parse_grbl_dump("[VER:1.1h]\n$30=1000\n$32=1\n$130=410.000\n$131=415.000\nok\n")
    assert parsed["settings"]["$30"] == 1000
    assert parsed["laser_mode"] == 1
    assert parsed["travel_x_mm"] == 410
    assert parsed["travel_y_mm"] == 415


def test_parse_lightburn_material_library_preserves_shop_settings():
    parsed = mb.parse_lightburn_clb(sample_clb(), "existing.clb")
    assert parsed.source_type == "lightburn_clb"
    assert len(parsed.material_presets) == 1
    preset = parsed.material_presets[0]
    assert preset["material"] == "INOVA yellow housing"
    assert preset["settings"]["speed"] == 3200
    assert preset["settings"]["maxPower"] == 32
    assert preset["settings"]["interval"] == 0.08


def test_parse_lightburn_project_extracts_cut_settings():
    data = b'''<LightBurnProject><CutSetting type="Scan"><name Value="Node mark"/><speed Value="3000"/><maxPower Value="30"/><numPasses Value="1"/></CutSetting></LightBurnProject>'''
    parsed = mb.parse_lightburn_project(data, "node.lbrn2")
    assert len(parsed.material_presets) == 1
    assert parsed.material_presets[0]["settings"]["speed"] == 3000


def test_parse_lbset_json_desc_value_records():
    data = json.dumps({"Settings": [{"Desc": "$30", "Value": 1000}, {"Desc": "$32", "Value": 1}]}).encode()
    parsed = mb.parse_lightburn_lbset(data, "machine.lbset")
    assert parsed.settings["$30"] == 1000
    assert parsed.settings["$32"] == 1


def test_parse_lightburn_bundle_collects_materials_and_machine_settings():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("materials.clb", sample_clb())
        z.writestr("machine.lbset", json.dumps({"a": {"Desc": "$32", "Value": 1}}))
    parsed = mb.parse_lightburn_bundle(buffer.getvalue(), "shop.lbzip")
    assert parsed.source_type == "lightburn_bundle"
    assert len(parsed.material_presets) == 1
    assert any(key.endswith(":$32") for key in parsed.settings)


def test_readonly_probe_never_sends_motion_power_or_setting_writes(monkeypatch):
    writes = []

    class FakeSerial:
        def __init__(self, *args, **kwargs):
            self.lines = []
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def write(self, payload):
            writes.append(payload)
            if payload == b"$I\n":
                self.lines = [b"[VER:1.1h.20190825:]\n", b"ok\n"]
            elif payload == b"$$\n":
                self.lines = [b"$30=1000\n", b"$32=1\n", b"$130=410\n", b"$131=415\n", b"ok\n"]
        def flush(self):
            pass
        def reset_input_buffer(self):
            pass
        def readline(self):
            return self.lines.pop(0) if self.lines else b""

    class FakeSerialModule:
        Serial = FakeSerial

    monkeypatch.setattr(mb, "serial", FakeSerialModule)
    result = mb.probe_grbl_readonly("FAKE", 115200, timeout=0.01)
    assert result["read_only"] is True
    assert result["laser_mode"] == 1
    assert writes == [b"\r\n", b"$I\n", b"$$\n"]
    joined = b"".join(writes)
    for forbidden in (b"G0", b"G1", b"M3", b"M4", b"M5", b"$H", b"$32=", b"S100"):
        assert forbidden not in joined


def test_compare_grbl_to_profile_is_diagnostic_only():
    from app.config_loader import load_machines
    machine = load_machines()["sculpfun_s9_pro_10w"]
    parsed = mb.parse_grbl_dump("$32=1\n$130=410\n$131=415\n")
    notes = mb.compare_grbl_to_profile(parsed, machine)
    assert notes
    assert any("GRBL X" in n for n in notes)
    # The comparison returns notes only; it does not mutate either input.
    assert parsed["travel_x_mm"] == 410
    assert machine.bed_width_mm == 400


def test_parse_lightburn_material_test_lbmt_preserves_grid_and_cut_settings():
    data = json.dumps({
        "INOVA visible mark test": {
            "XParam": "Speed", "XMin": 1500, "XMax": 3500, "XCount": 5,
            "YParam": "Power", "YMin": 10, "YMax": 40, "YCount": 4,
            "MaterialCut": {"type": "Scan", "speed": 2500, "maxPower": 28, "numPasses": 1},
            "TextCut": {"type": "Line", "speed": 3000, "maxPower": 10},
            "BorderCut": {"type": "Line", "speed": 3000, "maxPower": 10},
        }
    }).encode()
    parsed = mb.parse_lightburn_lbmt(data, "material_test_presets.lbmt")
    assert parsed.source_type == "lightburn_material_test"
    assert len(parsed.material_presets) == 1
    settings = parsed.material_presets[0]["settings"]
    assert settings["grid"]["XParam"] == "Speed"
    assert settings["material_cut"]["maxPower"] == 28


def test_lightburn_pref_roots_are_platform_specific(tmp_path):
    win = mb.lightburn_pref_roots(tmp_path, "Windows", {"LOCALAPPDATA": str(tmp_path / "Local")})
    assert win == [tmp_path / "Local" / "LightBurn"]
    linux = mb.lightburn_pref_roots(tmp_path, "Linux", {})
    assert linux == [tmp_path / ".config" / "LightBurn"]
    mac = mb.lightburn_pref_roots(tmp_path, "Darwin", {})
    assert mac == [tmp_path / "Library" / "Preferences" / "LightBurn"]


def test_discover_and_restricted_import_lightburn_artifacts(tmp_path):
    root = tmp_path / "LightBurn"
    presets = root / "presets"
    presets.mkdir(parents=True)
    lbmt = presets / "material_test_presets.lbmt"
    lbmt.write_text(json.dumps({"Phone test": {"MaterialCut": {"type": "Scan", "speed": 2400, "maxPower": 22}}}), encoding="utf-8")
    library = tmp_path / "shop.clb"
    library.write_bytes(sample_clb())
    (root / "prefs.ini").write_text(json.dumps({"LastLibraryPath": str(library)}), encoding="utf-8")

    discovered = mb.discover_lightburn_artifacts([root])
    names = {x["name"] for x in discovered["artifacts"]}
    assert "prefs.ini" in names
    assert "material_test_presets.lbmt" in names
    assert "shop.clb" in names

    parsed = mb.import_discovered_lightburn_artifact(str(lbmt), discovered["artifacts"])
    assert parsed.source_type == "lightburn_material_test"
    try:
        mb.import_discovered_lightburn_artifact(str(tmp_path / "secret.txt"), discovered["artifacts"])
    except ValueError as exc:
        assert "detectado" in str(exc)
    else:
        raise AssertionError("arbitrary local file should be rejected")


def test_parse_lasergrbl_psh_and_windows_discovery(tmp_path):
    xml = b'''<?xml version="1.0" standalone="yes"?>
<MaterialDB xmlns="http://tempuri.org/MaterialDB.xsd">
  <Materials><id>00000000-0000-0000-0000-000000000001</id><Visible>true</Visible><Model>SCULPFUN S9 Pro</Model><Material>INOVA yellow</Material><Thickness>-</Thickness><Action>Engrave</Action><Power>32</Power><Speed>3200</Speed><Cycles>1</Cycles><Remarks>Visible shop mark</Remarks></Materials>
</MaterialDB>'''
    parsed = mb.parse_lasergrbl_psh(xml, "UserMaterials.psh")
    assert parsed.source_type == "lasergrbl_material_db"
    assert len(parsed.material_presets) == 1
    p = parsed.material_presets[0]
    assert p["material"] == "INOVA yellow"
    assert p["settings"]["speed_mm_min"] == 3200
    assert p["settings"]["power_percent"] == 32
    assert p["settings"]["passes"] == 1

    root = tmp_path / "Roaming" / "LaserGRBL"
    root.mkdir(parents=True)
    f = root / "UserMaterials.psh"; f.write_bytes(xml)
    roots = mb.lasergrbl_roots(tmp_path, "Windows", {"APPDATA": str(tmp_path / "Roaming")})
    assert roots == [root]
    discovered = mb.discover_lasergrbl_artifacts(roots)
    assert discovered["artifacts"][0]["name"] == "UserMaterials.psh"
    imported = mb.import_discovered_lasergrbl_artifact(str(f), discovered["artifacts"])
    assert imported.material_presets[0]["settings"]["speed_mm_min"] == 3200


def test_lasergrbl_has_no_local_discovery_on_linux(tmp_path):
    assert mb.lasergrbl_roots(tmp_path, "Linux", {}) == []
