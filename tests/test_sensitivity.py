"""Tests for Phase 3C Sensitivity Matching Mathematics.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
"""

from __future__ import annotations

import math
import pytest

from acoustiforge.acoustic_math.sensitivity import (
    GainDesignResult,
    calculate_sensitivity_gain,
    calculate_system_sensitivity_gains,
)
from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain.profiles import DriverProfile, DriverRole


class TestSensitivityMatching:
    """Mathematical verification of sensitivity gain calculations."""

    def test_calculate_sensitivity_gain_identical(self) -> None:
        """Verify 0 dB gain when driver sensitivity equals reference sensitivity."""
        res = calculate_sensitivity_gain(
            sensitivity_db=88.0,
            reference_sensitivity_db=88.0,
            driver_name="woofer",
        )
        assert isinstance(res, GainDesignResult)
        assert res.driver_name == "woofer"
        assert res.gain_db == 0.0
        assert res.gain_linear == 1.0
        assert not res.polarity_inverted

    def test_calculate_sensitivity_gain_attenuation(self) -> None:
        """Verify attenuation calculation for higher sensitivity driver."""
        # Tweeter is 92 dB SPL, reference is woofer at 86 dB SPL -> -6 dB gain
        res = calculate_sensitivity_gain(
            sensitivity_db=92.0,
            reference_sensitivity_db=86.0,
            driver_name="tweeter",
        )
        assert pytest.approx(-6.0, abs=1e-6) == res.gain_db
        assert pytest.approx(0.50118723, rel=1e-5) == res.gain_linear

    def test_calculate_sensitivity_gain_polarity_inversion(self) -> None:
        """Verify negative linear gain when polarity is inverted."""
        res = calculate_sensitivity_gain(
            sensitivity_db=86.0,
            reference_sensitivity_db=86.0,
            polarity_inverted=True,
            driver_name="tweeter",
        )
        assert res.gain_db == 0.0
        assert res.gain_linear == -1.0
        assert res.polarity_inverted

    def test_calculate_system_sensitivity_gains(self) -> None:
        """Verify system gains choose the least sensitive driver as reference."""
        woofer = DriverProfile(name="woofer", role=DriverRole.WOOFER, sensitivity_db=85.0)
        tweeter = DriverProfile(name="tweeter", role=DriverRole.TWEETER, sensitivity_db=91.0, polarity_inverted=True)

        gains = calculate_system_sensitivity_gains([woofer, tweeter])

        assert gains["woofer"].gain_db == 0.0
        assert gains["woofer"].gain_linear == 1.0

        # Tweeter: -6 dB attenuation and inverted sign
        assert pytest.approx(-6.0, abs=1e-6) == gains["tweeter"].gain_db
        assert pytest.approx(-0.50118723, rel=1e-5) == gains["tweeter"].gain_linear
        assert gains["tweeter"].polarity_inverted

    def test_invalid_parameters(self) -> None:
        """Verify error on boost or invalid input."""
        with pytest.raises(InvalidParameterError, match="positive"):
            # Driver sensitivity lower than reference -> would require boost (+6 dB)
            calculate_sensitivity_gain(sensitivity_db=80.0, reference_sensitivity_db=86.0)

        with pytest.raises(InvalidParameterError, match="empty drivers"):
            calculate_system_sensitivity_gains([])
