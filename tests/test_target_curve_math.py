"""Tests for Phase 3C Acoustic Target Curve Evaluation Mathematics.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_3B_ACOUSTIC_DOMAIN_VALUE_TYPES_IMPLEMENTATION_AND_VERIFICATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.target_curve import evaluate_target_curve
from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain.specifications import AcousticTargetCurve


class TestTargetCurveEvaluation:
    """Mathematical verification of target curve interpolation."""

    @pytest.fixture
    def harman_sample_curve(self) -> AcousticTargetCurve:
        """Sample Harman-like target curve points."""
        points = [
            (20.0, 5.0),
            (100.0, 3.0),
            (1000.0, 0.0),
            (10000.0, -3.0),
            (20000.0, -5.0),
        ]
        return AcousticTargetCurve(name="Harman_Sample", points=points)

    def test_evaluate_exact_boundary_points(self, harman_sample_curve: AcousticTargetCurve) -> None:
        """Verify evaluation at exact coordinate points."""
        assert pytest.approx(5.0) == evaluate_target_curve(harman_sample_curve, 20.0)
        assert pytest.approx(3.0) == evaluate_target_curve(harman_sample_curve, 100.0)
        assert pytest.approx(0.0) == evaluate_target_curve(harman_sample_curve, 1000.0)
        assert pytest.approx(-3.0) == evaluate_target_curve(harman_sample_curve, 10000.0)
        assert pytest.approx(-5.0) == evaluate_target_curve(harman_sample_curve, 20000.0)

    def test_evaluate_log_frequency_interpolation(self, harman_sample_curve: AcousticTargetCurve) -> None:
        """Verify exact linear interpolation in log10(frequency) domain."""
        # Midpoint in log-frequency between 100 Hz and 1000 Hz:
        # log10(100) = 2.0, log10(1000) = 3.0 -> log-midpoint is 2.5 -> f = 10^2.5 = 316.227766 Hz
        # Value should be linear midpoint between 3.0 dB and 0.0 dB -> 1.5 dB
        f_mid = 10.0 ** 2.5
        val = evaluate_target_curve(harman_sample_curve, f_mid)
        assert pytest.approx(1.5, abs=1e-5) == val

    def test_evaluate_out_of_bounds_clamping(self, harman_sample_curve: AcousticTargetCurve) -> None:
        """Verify boundary clamping below f_min and above f_max."""
        # Below 20 Hz -> clamp to 5.0 dB
        assert pytest.approx(5.0) == evaluate_target_curve(harman_sample_curve, 10.0)
        assert pytest.approx(5.0) == evaluate_target_curve(harman_sample_curve, 1.0)

        # Above 20 kHz -> clamp to -5.0 dB
        assert pytest.approx(-5.0) == evaluate_target_curve(harman_sample_curve, 25000.0)
        assert pytest.approx(-5.0) == evaluate_target_curve(harman_sample_curve, 48000.0)

    def test_evaluate_array_inputs(self, harman_sample_curve: AcousticTargetCurve) -> None:
        """Verify vectorized evaluation over NumPy arrays."""
        freqs = np.array([10.0, 20.0, 10.0**2.5, 20000.0, 40000.0])
        expected = np.array([5.0, 5.0, 1.5, -5.0, -5.0])

        results = evaluate_target_curve(harman_sample_curve, freqs)
        assert isinstance(results, np.ndarray)
        np.testing.assert_allclose(results, expected, atol=1e-5)

    def test_invalid_parameters(self, harman_sample_curve: AcousticTargetCurve) -> None:
        """Verify error on invalid frequencies."""
        with pytest.raises(InvalidParameterError):
            evaluate_target_curve(harman_sample_curve, 0.0)

        with pytest.raises(InvalidParameterError):
            evaluate_target_curve(harman_sample_curve, -100.0)

        with pytest.raises(InvalidParameterError):
            evaluate_target_curve("not_a_curve", 1000.0)  # type: ignore
