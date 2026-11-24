"""Guards on the drug class config. A typo here silently drops a drug from every
downstream table, so it is worth testing."""

from obesity_ci import config

VALID_AREAS = {"t2d", "obesity", "both"}
VALID_GENERATIONS = {"legacy", "newer"}
VALID_ROUTES = {"sc", "oral", "iv", "inhaled"}


def test_every_class_has_required_fields():
    for class_id, c in config.drug_config()["classes"].items():
        for field in ["label", "mechanism", "area", "generation", "molecules"]:
            assert field in c, f"{class_id} missing {field}"
        assert c["area"] in VALID_AREAS, class_id
        assert c["generation"] in VALID_GENERATIONS, class_id
        assert c["molecules"], f"{class_id} has no molecules"


def test_molecules_are_unique_and_valid():
    mols = config.molecules()
    dupes = mols[mols["generic"].duplicated()]["generic"].tolist()
    assert not dupes, f"molecule listed in more than one class: {dupes}"
    assert set(mols["route"]) <= VALID_ROUTES


def test_scope_covers_brief():
    """The classes Lucas's brief names must all be present."""
    classes = set(config.molecules()["class_id"])
    for required in ["glp1_injectable", "glp1_oral", "gip_glp1", "glucagon_combos",
                     "amylin", "sglt2", "dpp4", "insulin_basal"]:
        assert required in classes


def test_settings_load_and_paths_resolve():
    st = config.settings()
    assert st["sources"]["ctgov"]["base_url"].startswith("https://")
    assert config.path("raw").is_dir()


def test_secrets_never_in_settings():
    text = (config.CONFIG_DIR / "settings.yaml").read_text().lower()
    assert "sk-ant" not in text and "api_key:" not in text
