import pytest
from pydantic import ValidationError

from cover_maker.domain import ALL_STEMS, Preset, Stem
from cover_maker.separation import recipes
from cover_maker.separation.catalog import Catalog, LicenceClass
from cover_maker.separation.hardware import Gpu, Hardware, Tier, parse_nvidia_smi


@pytest.mark.parametrize("preset", list(Preset))
def test_every_preset_covers_all_stems_with_catalogue_models(preset: Preset) -> None:
    recipe = recipes.load(preset)
    catalog = Catalog.load()

    assert set(recipe.outputs) == set(ALL_STEMS)
    for model_id in recipe.models(set(ALL_STEMS)):
        catalog.get(model_id)


def test_max_vocals_only_skips_instrumental_pass() -> None:
    nodes = recipes.load(Preset.MAX).prune({Stem.VOCALS})

    assert [node.id for node in nodes] == ["sw", "res", "voc"]


def test_max_guitar_needs_vocal_ensemble_first() -> None:
    nodes = recipes.load(Preset.MAX).prune({Stem.GUITAR})

    assert [node.id for node in nodes] == ["sw", "res", "voc", "inst"]


def test_recipe_rejects_forward_reference() -> None:
    with pytest.raises(ValidationError):
        recipes.Recipe.model_validate(
            {
                "nodes": [
                    {"id": "a", "model": "x", "input": "mix-minus:b.vocals"},
                    {"id": "b", "model": "x"},
                ],
                "outputs": {"vocals": "b.vocals"},
            }
        )


def test_catalogue_has_licence_and_notice_for_every_model() -> None:
    catalog = Catalog.load()

    for model in catalog.models.values():
        assert model.licence_class in LicenceClass
        assert model.licence and model.source
        assert len(model.notice_sha256()) == 64


def test_parse_nvidia_smi_line() -> None:
    gpu = parse_nvidia_smi("NVIDIA GeForce RTX 3050 Laptop GPU, 4096, 3466, 8.6, 596.21\n")

    assert gpu == Gpu("NVIDIA GeForce RTX 3050 Laptop GPU", 4096, 3466, 8.6, "596.21")


@pytest.mark.parametrize(
    ("total", "capability", "tier"),
    [
        (4096, 8.6, Tier.VRAM_4),
        (6144, 8.9, Tier.VRAM_6),
        (8188, 8.9, Tier.VRAM_8),
        (12282, 8.6, Tier.VRAM_12),
        (4096, 6.1, Tier.CPU),
    ],
)
def test_tiers(total: int, capability: float, tier: Tier) -> None:
    hw = Hardware("cpu", 6, 12, 16.0, Gpu("gpu", total, total, capability, "1"), None, 100.0)

    assert hw.tier is tier
