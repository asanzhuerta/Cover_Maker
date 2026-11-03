import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from cover_maker.audio.mixer import PEAK_LIMIT, protect_peaks, without
from cover_maker.domain import ALL_STEMS, ResidualMode, Stem

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
