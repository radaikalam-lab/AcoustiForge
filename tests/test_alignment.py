"""Tests for Phase 3C Driver Acoustic Time Alignment Mathematics.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from acoustiforge.acoustic_math.alignment import (
    DEFAULT_SPEED_OF_SOUND_MPS,
    DriverAlignmentResult,
    calculate_driver_alignment,
    calculate_system_alignments,
)
from acoustiforge.contracts.validation import InvalidParameterError, InvalidSampleRateError
from acoustiforge.domain.profiles import DriverProfile, DriverRole


class TestDriverAlignment:
    """Mathematical verification of acoustic alignment."""

    def test_calculate_driver_alignment_reference_case(self) -> None:
        """Verify alignment calculation when driver is at reference plane."""
        res = calculate_driver_alignment(
            driver_depth_mm=50.0,
            reference_depth_mm=50.0,
            sample_rate=48000,
            driver_name="woofer",
        )
        assert isinstance(res, DriverAlignmentResult)
        assert res.driver_name == "woofer"
        assert res.physical_delay_seconds == 0.0
        assert res.requested_delay_frames == 0.0
        assert res.applied_delay_frames == 0

    def test_calculate_driver_alignment_forward_driver(self) -> None:
        """Verify non-negative delay calculation for forward mounted driver."""
        # Tweeter at 0 mm depth, woofer voice coil at 25.4 mm depth (1 inch)
        res = calculate_driver_alignment(
            driver_depth_mm=0.0,
            reference_depth_mm=25.4,
            sample_rate=48000,
            speed_of_sound_mps=DEFAULT_SPEED_OF_SOUND_MPS,
            driver_name="tweeter",
        )
        # delta = 25.4 mm = 0.0254 m
        # tau = 0.0254 / 343.2 = 7.4009324e-5 s
        # requested frames = 7.4009324e-5 * 48000 = 3.552447 frames
        # applied integer frames = round(3.552447) = 4
        assert pytest.approx(0.0254 / 343.2, rel=1e-7) == res.physical_delay_seconds
        assert pytest.approx(3.55244755, rel=1e-6) == res.requested_delay_frames
        assert res.applied_delay_frames == 4

    def test_golden_vectors_conformance(self) -> None:
        """Verify alignment against frozen golden reference vector file."""
        golden_file = Path(__file__).resolve().parent.parent / "docs" / "phases" / "golden" / "alignment_golden_vectors.json"
        assert golden_file.exists(), f"Golden vectors file missing: {golden_file}"

        with open(golden_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for vec in data["vectors"]:
            res = calculate_driver_alignment(
                driver_depth_mm=vec["driver_depth_mm"],
                reference_depth_mm=vec["reference_depth_mm"],
                sample_rate=vec["sample_rate"],
                speed_of_sound_mps=vec["speed_of_sound_mps"],
                driver_name=vec["driver_name"],
            )
            tol = vec["tolerance"]
            exp = vec["expected"]
            assert pytest.approx(exp["physical_delay_seconds"], abs=tol) == res.physical_delay_seconds
            assert pytest.approx(exp["requested_delay_frames"], abs=tol) == res.requested_delay_frames
            assert exp["applied_delay_frames"] == res.applied_delay_frames

    def test_calculate_system_alignments(self) -> None:
        """Verify system alignment chooses the acoustically furthest back driver as common reference."""
        tweeter = DriverProfile(name="tweeter", role=DriverRole.TWEETER, sensitivity_db=90.0, depth_offset_mm=0.0)
        mid = DriverProfile(name="midrange", role=DriverRole.MIDRANGE, sensitivity_db=88.0, depth_offset_mm=15.0)
        woofer = DriverProfile(name="woofer", role=DriverRole.WOOFER, sensitivity_db=86.0, depth_offset_mm=40.0)

        alignments = calculate_system_alignments([tweeter, mid, woofer], sample_rate=48000)

        assert "tweeter" in alignments
        assert "midrange" in alignments
        assert "woofer" in alignments

        # Woofer is reference (deepest at 40 mm) -> 0 delay
        assert alignments["woofer"].applied_delay_frames == 0
        assert alignments["woofer"].reference_depth_mm == 40.0

        # Midrange delta = 40 - 15 = 25 mm -> delay > 0
        assert alignments["midrange"].applied_delay_frames > 0

        # Tweeter delta = 40 - 0 = 40 mm -> delay > midrange delay
        assert alignments["tweeter"].applied_delay_frames > alignments["midrange"].applied_delay_frames

    def test_invalid_parameters(self) -> None:
        """Verify strict error handling on invalid alignment inputs."""
        with pytest.raises(InvalidSampleRateError):
            calculate_driver_alignment(0.0, 10.0, sample_rate=0)

        with pytest.raises(InvalidParameterError, match="speed_of_sound_mps"):
            calculate_driver_alignment(0.0, 10.0, sample_rate=48000, speed_of_sound_mps=-343.0)

        with pytest.raises(InvalidParameterError, match="non-negative delay policy"):
            # Driver depth greater than reference depth
            calculate_driver_alignment(20.0, 10.0, sample_rate=48000)

        with pytest.raises(InvalidParameterError, match="empty drivers"):
            calculate_system_alignments([], sample_rate=48000)
