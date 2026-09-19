"""Tests for ThreeWayGraphBuilder Structure and Invariants.

Normative Authority:
- docs/contracts/MULTIWAY_GRAPH_BUILDER_CONTRACT.md
- docs/phases/PHASE_4B_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import pytest

from acoustiforge.acoustic_math.alignment import DriverAlignmentResult
from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads
from acoustiforge.acoustic_math.equalizer import synthesize_parametric_eq
from acoustiforge.acoustic_math.protection import design_infrasonic_protection_filter
from acoustiforge.acoustic_math.sensitivity import GainDesignResult
from acoustiforge.builders.multiway_builder import ThreeWayGraphBuilder
from acoustiforge.contracts.validation import InvalidParameterError, InvalidSampleRateError
from acoustiforge.domain import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    EqualizerBudget,
    FrequencyResponseData,
)
import numpy as np


class TestThreeWayGraphBuilder:
    """Test suite verifying structural correctness and validation rules of ThreeWayGraphBuilder."""

    @pytest.fixture
    def crossover_low(self):
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=2,
            frequency_hz=500.0,
        )
        return synthesize_crossover_biquads(spec, sample_rate=48000)

    @pytest.fixture
    def crossover_high(self):
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=2,
            frequency_hz=3000.0,
        )
        return synthesize_crossover_biquads(spec, sample_rate=48000)

    def test_build_basic_3way_graph(self, crossover_low, crossover_high) -> None:
        """Verify building a basic 3-way graph with 3 branches and 3 declared outputs."""
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(
            crossover_low=crossover_low,
            crossover_high=crossover_high,
        )

        assert graph.is_frozen
        assert len(graph.inputs) == 1
        assert graph.inputs[0] == ("input", "in")

        # 3 outputs: woofer, midrange, tweeter
        assert len(graph.outputs) == 3
        out_nodes = [node_id for node_id, _ in graph.outputs]
        assert "woofer.crossover.1" in out_nodes
        assert "midrange.crossover.lp.1" in out_nodes
        assert "tweeter.crossover.1" in out_nodes

        # Verify Midrange HP -> LP topology in execution schedule
        schedule = list(graph.schedule)
        idx_in = schedule.index("input")
        idx_m_delay = schedule.index("midrange.delay")
        idx_m_gain = schedule.index("midrange.gain")
        idx_m_hp0 = schedule.index("midrange.crossover.hp.0")
        idx_m_hp1 = schedule.index("midrange.crossover.hp.1")
        idx_m_lp0 = schedule.index("midrange.crossover.lp.0")
        idx_m_lp1 = schedule.index("midrange.crossover.lp.1")

        assert idx_in < idx_m_delay < idx_m_gain < idx_m_hp0 < idx_m_hp1 < idx_m_lp0 < idx_m_lp1

    def test_build_full_3way_with_delay_gain_eq_protection(self, crossover_low, crossover_high) -> None:
        """Verify full 3-way pipeline with alignment, gain, EQ, and protection on all branches."""
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0002, 9.6, 10, 50.0, 50.0, 48000, 343.2),
            "midrange": DriverAlignmentResult("midrange", 0.0001, 4.8, 5, 25.0, 50.0, 48000, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", 0.0, 0.0, 0, 10.0, 50.0, 48000, 343.2),
        }
        gains = {
            "woofer": GainDesignResult("woofer", 86.0, 86.0, 0.0, 1.0, False),
            "midrange": GainDesignResult("midrange", 89.0, 86.0, -3.0, 0.707946, False),
            "tweeter": GainDesignResult("tweeter", 91.0, 86.0, -5.0, 0.562341, False),
        }
        protections = {
            "woofer": design_infrasonic_protection_filter(cutoff_frequency_hz=35.0, sample_rate=48000, order=2, driver_name="woofer"),
            "midrange": design_infrasonic_protection_filter(cutoff_frequency_hz=200.0, sample_rate=48000, order=2, driver_name="midrange"),
        }

        # Synthesize parametric EQ for midrange
        freqs = np.geomspace(100.0, 10000.0, 50)
        mags = 86.0 + 4.0 * np.exp(-0.5 * ((np.log(freqs) - np.log(1000.0)) / 0.3) ** 2)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)
        target = AcousticTargetCurve("flat", tuple((f, 86.0) for f in freqs))
        budget = EqualizerBudget(max_bands=1)
        midrange_eq = synthesize_parametric_eq(frd, budget, sample_rate=48000, target_curve=target)

        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(
            crossover_low=crossover_low,
            crossover_high=crossover_high,
            alignments=alignments,
            gains=gains,
            equalizers={"midrange": midrange_eq},
            protections=protections,
        )

        assert "midrange.eq.0" in graph.nodes
        assert "woofer.protection.0" in graph.nodes
        assert "midrange.protection.0" in graph.nodes
        assert "tweeter.protection.0" not in graph.nodes  # tweeter had no protection

        # Woofer output node is protection.0
        out_nodes = [node_id for node_id, _ in graph.outputs]
        assert "woofer.protection.0" in out_nodes
        assert "midrange.protection.0" in out_nodes
        assert "tweeter.crossover.1" in out_nodes

    def test_invalid_crossover_frequency_ordering_rejected(self, crossover_low, crossover_high) -> None:
        """Verify that f_low >= f_high is deterministically rejected."""
        builder = ThreeWayGraphBuilder(sample_rate=48000)

        # Inverted: low=3000 Hz, high=500 Hz
        with pytest.raises(InvalidParameterError, match="0 < f_low < f_high"):
            builder.build_3way_graph(
                crossover_low=crossover_high,
                crossover_high=crossover_low,
            )

        # Equal: low=500 Hz, high=500 Hz
        with pytest.raises(InvalidParameterError, match="0 < f_low < f_high"):
            builder.build_3way_graph(
                crossover_low=crossover_low,
                crossover_high=crossover_low,
            )

    def test_invalid_constructor_parameters(self) -> None:
        """Verify constructor validation rules."""
        with pytest.raises(InvalidSampleRateError):
            ThreeWayGraphBuilder(sample_rate=0)

        with pytest.raises(InvalidParameterError, match="channels"):
            ThreeWayGraphBuilder(sample_rate=48000, channels=0)

        with pytest.raises(InvalidParameterError, match="pairwise distinct"):
            ThreeWayGraphBuilder(sample_rate=48000, woofer_name="w", midrange_name="w", tweeter_name="t")
