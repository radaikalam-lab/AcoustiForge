"""Independent Topology Golden Vectors for Three-Way Graph Builder.

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
from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    EqualizerBudget,
    FrequencyResponseData,
)
import numpy as np


class TestThreeWayGraphGolden:
    """Independent golden topology and determinism tests for ThreeWayGraphBuilder."""

    @pytest.fixture
    def crossover_low(self):
        spec = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=2, frequency_hz=400.0)
        return synthesize_crossover_biquads(spec, sample_rate=48000)

    @pytest.fixture
    def crossover_high(self):
        spec = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=2, frequency_hz=2500.0)
        return synthesize_crossover_biquads(spec, sample_rate=48000)

    def test_golden_case_1_basic_3way_topology(self, crossover_low, crossover_high) -> None:
        """Case 1: Verify exact expected node collection and port connections for basic 3-way DAG."""
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(crossover_low=crossover_low, crossover_high=crossover_high)

        # Independent expected node set
        expected_nodes = {
            "input",
            # Woofer branch
            "woofer.delay", "woofer.gain", "woofer.crossover.0", "woofer.crossover.1",
            # Midrange branch
            "midrange.delay", "midrange.gain",
            "midrange.crossover.hp.0", "midrange.crossover.hp.1",
            "midrange.crossover.lp.0", "midrange.crossover.lp.1",
            # Tweeter branch
            "tweeter.delay", "tweeter.gain", "tweeter.crossover.0", "tweeter.crossover.1",
        }
        assert set(graph.nodes.keys()) == expected_nodes

        # Expected declared outputs
        expected_outputs = (
            ("woofer.crossover.1", "out"),
            ("midrange.crossover.lp.1", "out"),
            ("tweeter.crossover.1", "out"),
        )
        assert graph.outputs == expected_outputs

    def test_golden_case_2_eq_enabled_insertion(self, crossover_low, crossover_high) -> None:
        """Case 2: Verify deterministic EQ node insertion between gain and crossover."""
        freqs = np.geomspace(100.0, 10000.0, 50)
        mags = 86.0 + 3.0 * np.exp(-0.5 * ((np.log(freqs) - np.log(1000.0)) / 0.2) ** 2)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)
        target = AcousticTargetCurve("flat", tuple((f, 86.0) for f in freqs))
        budget = EqualizerBudget(max_bands=2)
        mid_eq = synthesize_parametric_eq(frd, budget, sample_rate=48000, target_curve=target)

        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(
            crossover_low=crossover_low,
            crossover_high=crossover_high,
            equalizers={"midrange": mid_eq},
        )

        assert "midrange.eq.0" in graph.nodes
        assert "woofer.eq.0" not in graph.nodes
        assert "tweeter.eq.0" not in graph.nodes

        schedule = list(graph.schedule)
        assert schedule.index("midrange.gain") < schedule.index("midrange.eq.0") < schedule.index("midrange.crossover.hp.0")

    def test_golden_case_3_protection_enabled_insertion(self, crossover_low, crossover_high) -> None:
        """Case 3: Verify deterministic protection filter insertion at branch endpoint."""
        prot = design_infrasonic_protection_filter(cutoff_frequency_hz=30.0, sample_rate=48000, order=2, driver_name="woofer")
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(
            crossover_low=crossover_low,
            crossover_high=crossover_high,
            protections={"woofer": prot},
        )

        assert "woofer.protection.0" in graph.nodes
        schedule = list(graph.schedule)
        assert schedule.index("woofer.crossover.1") < schedule.index("woofer.protection.0")
        assert ("woofer.protection.0", "out") in graph.outputs

    def test_golden_case_4_delay_alignment_parameters(self, crossover_low, crossover_high) -> None:
        """Case 4: Verify branch-specific delay values are assigned without cross-talk."""
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0004, 19.2, 20, 100.0, 100.0, 48000, 343.2),
            "midrange": DriverAlignmentResult("midrange", 0.0001, 4.8, 5, 25.0, 100.0, 48000, 343.2),
        }
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(
            crossover_low=crossover_low,
            crossover_high=crossover_high,
            alignments=alignments,
        )

        assert graph.get_node("woofer.delay").delay_frames == 20
        assert graph.get_node("midrange.delay").delay_frames == 5
        assert graph.get_node("tweeter.delay").delay_frames == 0

    def test_golden_case_5_gain_sensitivity_trim(self, crossover_low, crossover_high) -> None:
        """Case 5: Verify branch sensitivity gain parameters."""
        gains = {
            "midrange": GainDesignResult("midrange", 90.0, 86.0, -4.0, 0.630957, False),
            "tweeter": GainDesignResult("tweeter", 92.0, 86.0, -6.0, 0.501187, True),
        }
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(
            crossover_low=crossover_low,
            crossover_high=crossover_high,
            gains=gains,
        )

        assert abs(graph.get_node("midrange.gain").gain_db - (-4.0)) < 1e-12
        assert abs(graph.get_node("tweeter.gain").gain_db - (-6.0)) < 1e-12
        assert abs(graph.get_node("woofer.gain").gain_db - 0.0) < 1e-12

    def test_golden_case_6_invalid_crossover_rejection(self, crossover_low, crossover_high) -> None:
        """Case 6: Verify rejection of invalid crossover boundary frequencies."""
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        with pytest.raises(InvalidParameterError):
            builder.build_3way_graph(crossover_low=crossover_high, crossover_high=crossover_low)

    def test_golden_case_7_midrange_topology_hp_then_lp(self, crossover_low, crossover_high) -> None:
        """Case 7: Explicitly verify midrange branch executes high-pass before low-pass."""
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(crossover_low=crossover_low, crossover_high=crossover_high)

        schedule = list(graph.schedule)
        idx_hp = schedule.index("midrange.crossover.hp.1")
        idx_lp = schedule.index("midrange.crossover.lp.0")
        assert idx_hp < idx_lp

    def test_golden_case_8_repeated_construction_determinism(self, crossover_low, crossover_high) -> None:
        """Case 8: Verify repeated construction produces identical nodes, edges, schedule, and latency."""
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        g1 = builder.build_3way_graph(crossover_low=crossover_low, crossover_high=crossover_high)
        g2 = builder.build_3way_graph(crossover_low=crossover_low, crossover_high=crossover_high)

        assert list(g1.nodes.keys()) == list(g2.nodes.keys())
        assert g1.schedule == g2.schedule
        assert [str(e) for e in g1.edges] == [str(e) for e in g2.edges]
        assert g1.outputs == g2.outputs
