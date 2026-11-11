from pathlib import Path

import pytest
from pydantic import ValidationError

from cover_maker.domain import ALL_STEMS, JobSpec, Mode, Preset, ResidualMode, Stem
from cover_maker.pipeline.runner import preset_models, stems_to_separate
from cover_maker.separation import recipes
from cover_maker.separation.catalog import Catalog, LicenceClass
from cover_maker.separation.hardware import Gpu, Hardware, Tier, parse_nvidia_smi


@pytest.mark.parametrize("preset", list(Preset))
def test_every_preset_covers_all_stems_with_catalogue_models(preset: Preset) -> None:
    recipe = recipes.load(preset)
    catalog = Catalog.load()

    assert set(recipe.outputs) == set(Stem)
    for model_id in recipe.models(set(Stem)):
        catalog.get(model_id)


KARAOKE = "bs-roformer-karaoke-anvuew"


@pytest.mark.parametrize("preset", list(Preset))
def test_lead_and_backing_run_on_the_vocals_stem(preset: Preset) -> None:
    recipe = recipes.load(preset)
    vocals = recipe.output_ref(Stem.VOCALS)

    nodes = recipe.prune({Stem.VOCALS_LEAD})

    assert nodes[-1].model == KARAOKE
    assert nodes[-1].input == f"stem:{vocals}"
    assert vocals.node in [node.id for node in nodes]
    assert recipe.output_ref(Stem.VOCALS_BACKING).node == nodes[-1].id


@pytest.mark.parametrize("preset", list(Preset))
def test_top_level_stems_never_need_the_karaoke_model(preset: Preset) -> None:
    assert KARAOKE not in recipes.load(preset).models(set(ALL_STEMS))
    assert KARAOKE not in preset_models()[preset]


def test_max_lead_skips_instrumental_pass() -> None:
    nodes = recipes.load(Preset.MAX).prune({Stem.VOCALS_BACKING})

    assert [node.id for node in nodes] == ["sw", "res", "voc", "lead"]


def test_stems_to_separate_splits_only_what_the_job_needs(tmp_path: Path) -> None:
    def needed(**kwargs: object) -> set[Stem]:
        return stems_to_separate(
            JobSpec.model_validate({"inputs": ["a.wav"], "output_dir": tmp_path, **kwargs})
        )

    lead = [Stem.VOCALS_LEAD]
    assert needed(stems=lead, mode=Mode.WITHOUT) == {Stem.VOCALS_LEAD}
    assert needed(stems=lead, mode=Mode.WITHOUT, residual=ResidualMode.DROP) == (
        set(ALL_STEMS) - {Stem.VOCALS} | {Stem.VOCALS_LEAD, Stem.VOCALS_BACKING}
    )
    assert needed(stems=[Stem.DRUMS], mode=Mode.BOTH, residual=ResidualMode.DROP) == set(ALL_STEMS)


def test_recipe_rejects_stem_input_from_a_later_node() -> None:
    with pytest.raises(ValidationError):
        recipes.Recipe.model_validate(
            {
                "nodes": [
                    {"id": "a", "model": "x", "input": "stem:b.vocals"},
                    {"id": "b", "model": "x"},
                ],
                "outputs": {"vocals": "b.vocals"},
            }
        )


def test_karaoke_model_maps_its_outputs_to_sub_stems() -> None:
    model = Catalog.load().get(KARAOKE)

    assert model.stems == {"Vocals": Stem.VOCALS_LEAD, "Instrumental": Stem.VOCALS_BACKING}
    assert model.licence_class is LicenceClass.COPYLEFT
    assert model.sha256 and len(model.sha256) == 64


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
        assert model.licence_url.startswith("https://")
        assert model.verified_on.year >= 2026
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
