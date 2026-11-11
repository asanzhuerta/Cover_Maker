import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from cover_maker.audio.mixer import PEAK_LIMIT, mix_gains, pan_gains, protect_peaks, without
from cover_maker.domain import (
    ALL_STEMS,
    ResidualMode,
    Stem,
    as_parts,
    finest,
    parent_of,
    split_for,
    stem_label,
)

FRAMES = 256
signal = arrays(np.float32, (FRAMES, 2), elements=st.floats(-0.5, 0.5, width=32))


@settings(max_examples=50, deadline=None)
@given(
    mix=signal,
    stems=st.lists(signal, min_size=6, max_size=6),
    removed=st.sets(st.sampled_from(ALL_STEMS), min_size=1),
)
def test_keep_residual_is_mix_minus_removed(
    mix: np.ndarray, stems: list[np.ndarray], removed: set[Stem]
) -> None:
    by_stem = dict(zip(ALL_STEMS, stems, strict=True))

    result = without(mix, by_stem, removed, ResidualMode.KEEP)

    expected = mix - sum(by_stem[stem] for stem in removed)
    np.testing.assert_allclose(result, expected, atol=1e-5)


@settings(max_examples=50, deadline=None)
@given(
    stems=st.lists(signal, min_size=6, max_size=6),
    removed=st.sets(st.sampled_from(ALL_STEMS), min_size=1),
)
def test_drop_residual_sums_remaining(stems: list[np.ndarray], removed: set[Stem]) -> None:
    by_stem = dict(zip(ALL_STEMS, stems, strict=True))
    mix = np.zeros((FRAMES, 2), dtype=np.float32)

    result = without(mix, by_stem, removed, ResidualMode.DROP)

    remaining = [by_stem[stem] for stem in ALL_STEMS if stem not in removed]
    expected = np.sum(remaining, axis=0) if remaining else np.zeros_like(mix)
    np.testing.assert_allclose(result, expected, atol=1e-5)


def test_perfect_separation_keep_equals_drop() -> None:
    rng = np.random.default_rng(1)
    stems = {stem: rng.uniform(-0.1, 0.1, (FRAMES, 2)).astype(np.float32) for stem in ALL_STEMS}
    mix = np.sum(list(stems.values()), axis=0).astype(np.float32)

    keep = without(mix, stems, {Stem.VOCALS}, ResidualMode.KEEP)
    drop = without(mix, stems, {Stem.VOCALS}, ResidualMode.DROP)

    np.testing.assert_allclose(keep, drop, atol=1e-5)


def test_shorter_stems_are_padded() -> None:
    mix = np.ones((10, 2), dtype=np.float32)
    short = {Stem.VOCALS: np.ones((6, 2), dtype=np.float32)}

    result = without(mix, short, {Stem.VOCALS}, ResidualMode.KEEP)

    assert result.shape == (10, 2)
    np.testing.assert_allclose(result[6:], 1.0)


def test_peaks_only_reduced_when_clipping() -> None:
    quiet = np.full((4, 2), 0.5, dtype=np.float32)
    loud = np.full((4, 2), 2.0, dtype=np.float32)

    assert protect_peaks(quiet).gain_db == 0.0
    result = protect_peaks(loud)
    assert np.max(np.abs(result.audio)) <= PEAK_LIMIT + 1e-6
    assert result.gain_db < 0


@settings(max_examples=50, deadline=None)
@given(
    mix=signal,
    stems=st.lists(signal, min_size=6, max_size=6),
    removed=st.sets(st.sampled_from(ALL_STEMS), min_size=1),
    residual=st.sampled_from(list(ResidualMode)),
)
def test_muting_in_the_mixer_matches_without(
    mix: np.ndarray, stems: list[np.ndarray], removed: set[Stem], residual: ResidualMode
) -> None:
    by_stem = dict(zip(ALL_STEMS, stems, strict=True))

    result = mix_gains(mix, by_stem, {stem: 0.0 for stem in removed}, residual)

    np.testing.assert_allclose(result, without(mix, by_stem, removed, residual), atol=1e-5)


def test_unity_gains_with_keep_give_the_original_mix() -> None:
    rng = np.random.default_rng(7)
    mix = rng.uniform(-0.5, 0.5, (FRAMES, 2)).astype(np.float32)
    stems = {stem: rng.uniform(-0.2, 0.2, (FRAMES, 2)).astype(np.float32) for stem in ALL_STEMS}

    np.testing.assert_allclose(mix_gains(mix, stems, {}, ResidualMode.KEEP), mix, atol=1e-5)


def test_gains_scale_only_their_stem() -> None:
    mix = np.full((FRAMES, 2), 0.5, dtype=np.float32)
    stems = {Stem.VOCALS: np.full((FRAMES, 2), 0.2, dtype=np.float32)}

    keep = mix_gains(mix, stems, {Stem.VOCALS: 0.5}, ResidualMode.KEEP)
    drop = mix_gains(mix, stems, {Stem.VOCALS: 0.5}, ResidualMode.DROP)

    np.testing.assert_allclose(keep, 0.4, atol=1e-6)  # residual 0.3 + 0.5 * 0.2
    np.testing.assert_allclose(drop, 0.1, atol=1e-6)


def test_pan_law_keeps_the_centre_at_unity() -> None:
    assert pan_gains(0.0) == (1.0, 1.0)
    assert pan_gains(-1.0) == (1.0, 0.0)
    assert pan_gains(0.25) == (0.75, 1.0)
    assert pan_gains(5.0) == (0.0, 1.0)


def test_pan_moves_a_stem_between_channels() -> None:
    mix = np.full((FRAMES, 2), 0.5, dtype=np.float32)
    stems = {Stem.GUITAR: np.full((FRAMES, 2), 0.2, dtype=np.float32)}

    keep = mix_gains(mix, stems, {}, ResidualMode.KEEP, {Stem.GUITAR: -1.0})
    drop = mix_gains(mix, stems, {Stem.GUITAR: 0.5}, ResidualMode.DROP, {Stem.GUITAR: 0.5})

    # Hard left with the residual kept: the right channel loses the guitar.
    np.testing.assert_allclose(keep[:, 0], 0.5, atol=1e-6)
    np.testing.assert_allclose(keep[:, 1], 0.3, atol=1e-6)
    # Half right at half gain: left at 0.5 * 0.5 * 0.2, right at 0.5 * 0.2.
    np.testing.assert_allclose(drop[:, 0], 0.05, atol=1e-6)
    np.testing.assert_allclose(drop[:, 1], 0.1, atol=1e-6)


# ---------------------------------------------------------------- sub-stems

LEAD, BACKING = Stem.VOCALS_LEAD, Stem.VOCALS_BACKING


def with_sub_stems(stems: list[np.ndarray], lead: np.ndarray) -> dict[Stem, np.ndarray]:
    """Top-level stems plus a lead/backing split of the vocals that adds up exactly."""
    by_stem = dict(zip(ALL_STEMS, stems, strict=True))
    by_stem[LEAD] = lead
    by_stem[BACKING] = by_stem[Stem.VOCALS] - lead
    return by_stem


def test_sub_stem_helpers() -> None:
    assert parent_of(LEAD) is Stem.VOCALS
    assert parent_of(Stem.VOCALS) is None
    assert stem_label(LEAD) == "Lead vocals"
    assert stem_label(BACKING) == "Backing vocals"
    assert stem_label(Stem.VOCALS) == "Vocals"
    assert split_for({Stem.DRUMS}) == set(ALL_STEMS)
    assert split_for({BACKING}) == set(ALL_STEMS) - {Stem.VOCALS} | {LEAD, BACKING}
    assert finest(set(Stem)) == set(ALL_STEMS) - {Stem.VOCALS} | {LEAD, BACKING}
    assert finest({Stem.VOCALS, LEAD}) == {Stem.VOCALS, LEAD}  # backing missing: keep vocals
    assert as_parts({Stem.VOCALS}, split_for({LEAD})) == {LEAD, BACKING}


@settings(max_examples=50, deadline=None)
@given(
    stems=st.lists(signal, min_size=6, max_size=6),
    lead=signal,
    removed=st.sets(st.sampled_from(list(Stem)), min_size=1),
)
def test_perfect_separation_keep_equals_drop_with_sub_stems(
    stems: list[np.ndarray], lead: np.ndarray, removed: set[Stem]
) -> None:
    by_stem = with_sub_stems(stems, lead)
    mix = np.sum(stems, axis=0).astype(np.float32)

    keep = without(mix, by_stem, removed, ResidualMode.KEEP)
    drop = without(mix, by_stem, removed, ResidualMode.DROP)

    np.testing.assert_allclose(keep, drop, atol=1e-5)


@settings(max_examples=50, deadline=None)
@given(mix=signal, stems=st.lists(signal, min_size=6, max_size=6), lead=signal)
def test_removing_the_lead_keeps_the_backing(
    mix: np.ndarray, stems: list[np.ndarray], lead: np.ndarray
) -> None:
    by_stem = with_sub_stems(stems, lead)

    keep = without(mix, by_stem, {LEAD}, ResidualMode.KEEP)
    drop = without(mix, by_stem, {LEAD}, ResidualMode.DROP)
    both = without(mix, by_stem, {Stem.VOCALS, LEAD}, ResidualMode.KEEP)

    np.testing.assert_allclose(keep, mix - lead, atol=1e-5)
    band = sum(by_stem[stem] for stem in ALL_STEMS if stem is not Stem.VOCALS)
    np.testing.assert_allclose(drop, band + by_stem[BACKING], atol=1e-5)
    np.testing.assert_allclose(both, mix - by_stem[Stem.VOCALS], atol=1e-5)


@settings(max_examples=50, deadline=None)
@given(
    mix=signal,
    stems=st.lists(signal, min_size=6, max_size=6),
    lead=signal,
    removed=st.sets(st.sampled_from(list(Stem)), min_size=1),
    residual=st.sampled_from(list(ResidualMode)),
)
def test_muting_sub_stems_in_the_mixer_matches_without(
    mix: np.ndarray,
    stems: list[np.ndarray],
    lead: np.ndarray,
    removed: set[Stem],
    residual: ResidualMode,
) -> None:
    by_stem = with_sub_stems(stems, lead)

    result = mix_gains(mix, by_stem, {stem: 0.0 for stem in removed}, residual)

    np.testing.assert_allclose(result, without(mix, by_stem, removed, residual), atol=1e-5)


@settings(max_examples=50, deadline=None)
@given(
    mix=signal,
    stems=st.lists(signal, min_size=6, max_size=6),
    lead=signal,
    gain=st.floats(0, 4),
    pan=st.floats(-1, 1),
    residual=st.sampled_from(list(ResidualMode)),
)
def test_sub_stems_at_one_gain_sound_like_their_parent(
    mix: np.ndarray,
    stems: list[np.ndarray],
    lead: np.ndarray,
    gain: float,
    pan: float,
    residual: ResidualMode,
) -> None:
    by_stem = with_sub_stems(stems, lead)
    top_level = {stem: by_stem[stem] for stem in ALL_STEMS}

    parent = mix_gains(mix, top_level, {Stem.VOCALS: gain}, residual, {Stem.VOCALS: pan})
    split = mix_gains(
        mix, by_stem, {LEAD: gain, BACKING: gain}, residual, {LEAD: pan, BACKING: pan}
    )
    group = mix_gains(mix, by_stem, {Stem.VOCALS: gain}, residual, {Stem.VOCALS: pan})

    np.testing.assert_allclose(split, parent, atol=1e-4)
    np.testing.assert_allclose(group, parent, atol=1e-4)


def test_unity_gains_with_sub_stems_give_the_original_mix() -> None:
    rng = np.random.default_rng(3)
    mix = rng.uniform(-0.5, 0.5, (FRAMES, 2)).astype(np.float32)
    stems = [rng.uniform(-0.2, 0.2, (FRAMES, 2)).astype(np.float32) for _ in ALL_STEMS]
    by_stem = with_sub_stems(stems, rng.uniform(-0.1, 0.1, (FRAMES, 2)).astype(np.float32))

    np.testing.assert_allclose(mix_gains(mix, by_stem, {}, ResidualMode.KEEP), mix, atol=1e-5)
