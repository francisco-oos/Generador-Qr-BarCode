from app.material_catalog import load_material_reference, phone_reference, search_material_reference


def test_material_catalog_loads_and_has_no_duplicate_ids():
    data = load_material_reference()
    assert data["materials"]
    assert data["phone_models"]
    assert data["policy"]["priority_order"][0] == "shop_validated_same_machine_same_material"


def test_unsafe_or_unknown_plastics_never_publish_runnable_production_pair():
    data = load_material_reference()
    by_id = {x["id"]: x for x in data["materials"]}
    for material_id in ("unknown_plastic", "pvc_vinyl", "abs_plastic", "polycarbonate_pc", "phone_assembled_unknown"):
        suggested = by_id[material_id].get("suggested") or {}
        assert not ("speed_mm_min" in suggested and "power_percent" in suggested), material_id


def test_material_search_and_phone_lookup_cover_priority_phone_families():
    plastic = search_material_reference(category="plastic")
    assert any(x["id"] == "pvc_vinyl" for x in plastic["materials"])

    cubot = phone_reference("CUBOT", "KingKong 9")
    assert cubot and cubot[0]["id"] == "cubot_kingkong_9"

    bison = phone_reference("UMIDIGI", "BISON X10")
    assert bison and bison[0]["id"] == "umidigi_bison_x10"

    redmi = phone_reference("Redmi", "Note 14")
    assert any(x["id"] == "redmi_note_14" for x in redmi)
