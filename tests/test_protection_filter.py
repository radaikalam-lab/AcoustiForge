"""Tests for Phase 3C Driver Protection Filter Mathematics.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.protection import (
    ProtectionFilterResult,
    derive_protection_filter_for_driver,
    design_infrasonic_protection_filter,
)
from acoustiforge.contracts.validation import InvalidParameterError, InvalidSampleRateError
from acoustiforge.domain.profiles import DriverProfile, DriverRole, EnclosureProfile, EnclosureType
from acoustiforge.domain.specifications import TransducerLimits


class TestProtectionFilter:
    """Mathematical verification of protection filter synthesis."""

    def test_design_infrasonic_protection_filter_order_2(self) -> None:
        """Verify 2nd-order high-pass protection filter design."""
        res = design_infrasonic_protection_filter(
            cutoff_frequency_hz=30.0,
            sample_rate=48000,
            order=2,
            driver_name="woofer",
        )
        assert isinstance(res, ProtectionFilterResult)
        assert res.cutoff_frequency_hz == 30.0
        assert res.order == 2
        assert len(res.sections) == 1
        assert res.sections[0].is_stable()

    def test_derive_protection_filter_vented_enclosure(self) -> None:
        """Verify protection cutoff derived from vented enclosure tuning frequency (0.8 * Fb)."""
        enclosure = EnclosureProfile(
            enclosure_type=EnclosureType.VENTED,
            volume_liters=40.0,
            tuning_frequency_hz=35.0,
        )
        driver = DriverProfile(name="woofer", role=DriverRole.WOOFER, sensitivity_db=88.0)

        res = derive_protection_filter_for_driver(driver, enclosure, sample_rate=48000)
        # Expected cutoff: 0.8 * 35.0 = 28.0 Hz
        assert pytest.approx(28.0) == res.cutoff_frequency_hz
        assert res.driver_name == "woofer"

    def test_derive_protection_filter_transducer_limits(self) -> None:
        """Verify protection cutoff derived from transducer Fs when sealed (0.7 * Fs)."""
        limits = TransducerLimits(x_max_mm=5.0, p_max_rms_watts=100.0, f_s_hz=45.0, r_e_ohms=6.0)
        driver = DriverProfile(name="subwoofer", role=DriverRole.SUBWOOFER, sensitivity_db=86.0, limits=limits)
        enclosure = EnclosureProfile(enclosure_type=EnclosureType.SEALED, volume_liters=25.0)

        res = derive_protection_filter_for_driver(driver, enclosure, sample_rate=48000)
        # Expected cutoff: max(15.0, 0.7 * 45.0 = 31.5) = 31.5 Hz
        assert pytest.approx(31.5) == res.cutoff_frequency_hz

    def test_derive_protection_filter_explicit_override(self) -> None:
        """Verify explicit cutoff frequency override bypasses heuristics."""
        enclosure = EnclosureProfile(
            enclosure_type=EnclosureType.VENTED,
            volume_liters=40.0,
            tuning_frequency_hz=35.0,
        )
        driver = DriverProfile(name="woofer", role=DriverRole.WOOFER, sensitivity_db=88.0)

        res = derive_protection_filter_for_driver(
            driver,
            enclosure,
            sample_rate=48000,
            explicit_cutoff_hz=32.5,
        )
        assert res.cutoff_frequency_hz == 32.5

    def test_derive_protection_filter_custom_scale_factors(self) -> None:
        """Verify configurable heuristic scale factors for vented and sealed alignments."""
        enclosure = EnclosureProfile(
            enclosure_type=EnclosureType.VENTED,
            volume_liters=40.0,
            tuning_frequency_hz=40.0,
        )
        driver = DriverProfile(name="woofer", role=DriverRole.WOOFER, sensitivity_db=88.0)

        res = derive_protection_filter_for_driver(
            driver,
            enclosure,
            sample_rate=48000,
            vented_scale_factor=0.85,
        )
        # 0.85 * 40.0 = 34.0 Hz
        assert pytest.approx(34.0) == res.cutoff_frequency_hz

    def test_derive_protection_filter_insufficient_data(self) -> None:
        """Verify error when neither enclosure tuning nor transducer limits are present."""
        driver = DriverProfile(name="woofer", role=DriverRole.WOOFER, sensitivity_db=88.0)
        enclosure = EnclosureProfile(enclosure_type=EnclosureType.SEALED, volume_liters=20.0)

        with pytest.raises(InvalidParameterError, match="Cannot derive protection filter"):
            derive_protection_filter_for_driver(driver, enclosure, sample_rate=48000)
