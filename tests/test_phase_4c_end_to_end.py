"""End-to-End Vertical Slice and Integration Test for AcoustiForge Phase 4C.

Pipeline under test:
Raw WAV Time-Domain Impulse
       ↓ (parse_impulse_file)
ImpulseResponseData
       ↓ (apply_reflection_gate)
Gated ImpulseResponseData
       ↓ (transform_impulse_to_frequency_response)
FrequencyResponseData (Uncalibrated)
       ↓ (evaluate_measurement_quality)
MeasurementDiagnosticReport (CLEAN)
       ↓ (apply_microphone_calibration)
FrequencyResponseData (Calibrated)
       ↓ (calculate_response_metrics)
AcousticMetricsResult
       ↓ (synthesize_crossover_biquads / synthesize_parametric_eq)
CrossoverSynthesisResult + EQSynthesisResult
       ↓ (ThreeWayGraphBuilder)
ComputeGraph (Frozen Phase 2B DAG)
       ↓ (process across block size matrix [1, 7, 16, 31, 64, 127, 256])
Multi-Channel Output PCMBlocks
"""

from __future__ import annotations

import io
import math
import struct
import numpy as np
import pytest

from acoustiforge.acoustic_math.calibration import (
    CalibrationBoundaryPolicy,
    apply_microphone_calibration,
)
from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads
from acoustiforge.acoustic_math.diagnostics import (
    DiagnosticFlag,
    evaluate_measurement_quality,
)
from acoustiforge.acoustic_math.equalizer import synthesize_parametric_eq
from acoustiforge.acoustic_math.gating import (
    GateSpecification,
    apply_reflection_gate,
    transform_impulse_to_frequency_response,
)
from acoustiforge.acoustic_math.metrics import calculate_response_metrics
from acoustiforge.builders.multiway_builder import ThreeWayGraphBuilder
from acoustiforge.contracts.pcm import AudioMetadata, ChannelLayout, PCMBlock
from acoustiforge.domain.measurements import FrequencyResponseData, ImpulseResponseData
from acoustiforge.domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    EqualizerBudget,
)
from acoustiforge.io.impulse_parser import _parse_wav_bytes


def _generate_synthetic_impulse_wav_bytes(
    sample_rate: int = 48000,
    num_samples: int = 2048,
    peak_sample: int = 200,
    reflection_sample: int = 800,
) -> bytes:
    """Generate synthetic WAV byte stream containing direct arrival and room reflection echo."""
    samples = np.zeros(num_samples, dtype=np.float64)
    # Direct impulse
    samples[peak_sample] = 0.95
    # Exponential decay tail
    tail_len = 100
    samples[peak_sample : peak_sample + tail_len] += 0.95 * np.exp(-np.arange(tail_len) / 15.0)
    # Room floor reflection at sample 800 (t ~ 16.7 ms)
    samples[reflection_sample : reflection_sample + tail_len] += 0.4 * np.exp(-np.arange(tail_len) / 10.0)

    # Convert to 16-bit integer WAV byte stream
    bio = io.BytesIO()
    data_bytes = np.clip(np.round(samples * 32768.0), -32768, 32767).astype(np.int16).tobytes()

    bio.write(b"RIFF")
    bio.write(struct.pack("<I", 36 + len(data_bytes)))
    bio.write(b"WAVE")
    bio.write(b"fmt ")
    bio.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    bio.write(b"data")
    bio.write(struct.pack("<I", len(data_bytes)))
    bio.write(data_bytes)
    return bio.getvalue()


class TestPhase4CEndToEnd:
    """Complete end-to-end integration and execution test suite for Phase 4C."""

    def test_complete_impulse_to_pcm_vertical_slice(self) -> None:
        """Execute full pipeline: WAV -> Gate -> FFT -> Calibrate -> Metrics -> 3-Way Builder -> PCM execution."""
        sample_rate = 48000

        # Step 1: Ingest raw WAV impulse response
        wav_bytes = _generate_synthetic_impulse_wav_bytes(sample_rate=sample_rate)
        raw_ir = _parse_wav_bytes(wav_bytes)
        assert raw_ir.sample_rate == sample_rate
        assert raw_ir.peak_index == 200

        # Step 2: Apply Reflection Gate (isolate direct arrival, eliminate reflection at sample 800)
        # 1.0 ms left (48 samples), 5.0 ms right (240 samples) -> gate ends at sample 440 (before sample 800)
        gate_spec = GateSpecification(left_time_ms=1.0, right_time_ms=5.0)
        gated_result = apply_reflection_gate(raw_ir, gate_spec=gate_spec)
        assert gated_result.gated_impulse.samples[800] == 0.0

        # Step 3: Spectral FFT Transformation
        raw_frd = transform_impulse_to_frequency_response(gated_result, n_fft=2048)
        assert raw_frd.frequencies_hz[0] == 48000.0 / 2048.0  # 23.4375 Hz

        # Step 4: Quality Diagnostics
        diagnostic_report = evaluate_measurement_quality(
            impulse=gated_result.gated_impulse,
            frequency_response=raw_frd,
            gated_result=gated_result,
        )
        assert diagnostic_report.is_valid is True
        assert diagnostic_report.snr_db > 20.0

        # Step 5: Microphone Calibration
        cal_freqs = np.array([20.0, 1000.0, 10000.0, 20000.0, 24000.0], dtype=np.float64)
        cal_mags = np.array([0.0, 0.0, 0.5, 1.5, 2.0], dtype=np.float64)
        mic_cal = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        calibrated_frd = apply_microphone_calibration(
            raw_frd,
            mic_cal,
            boundary_policy=CalibrationBoundaryPolicy.CLAMP,
        )

        # Step 6: Quantitative Response Metrics
        target_curve = AcousticTargetCurve(
            name="E2E Target Curve",
            points=((20.0, 85.0), (20000.0, 85.0)),
        )
        metrics = calculate_response_metrics(
            calibrated_frd,
            target_curve=target_curve,
            passband_hz=(300.0, 3000.0),
        )
        assert math.isfinite(metrics.passband_sensitivity_db)
        assert math.isfinite(metrics.passband_ripple_db)
        assert math.isfinite(metrics.spectral_tilt_db_per_oct)

        # Step 7: Crossover & Equalizer Synthesis
        xo_low = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=500.0,
        )
        xo_high = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=3000.0,
        )
        crossover_low_res = synthesize_crossover_biquads(
            specification=xo_low,
            sample_rate=sample_rate,
        )
        crossover_high_res = synthesize_crossover_biquads(
            specification=xo_high,
            sample_rate=sample_rate,
        )
        eq_res = synthesize_parametric_eq(
            measurement=calibrated_frd,
            budget=EqualizerBudget(max_bands=2, max_boost_db=6.0, max_cut_db=6.0),
            sample_rate=sample_rate,
            target_curve=target_curve,
        )

        # Step 8: Build 3-Way Graph
        builder = ThreeWayGraphBuilder(
            sample_rate=sample_rate,
            channels=1,
            woofer_name="woofer",
            midrange_name="midrange",
            tweeter_name="tweeter",
            graph_name="e2e_3way_impulse_graph",
        )
        graph = builder.build_3way_graph(
            crossover_low=crossover_low_res,
            crossover_high=crossover_high_res,
            equalizers={
                "woofer": eq_res,
                "midrange": eq_res,
                "tweeter": eq_res,
            },
        )
        graph.freeze()

        # Step 9: Multi-Block PCM Processing Matrix
        block_sizes = [1, 7, 16, 31, 64, 127, 256]

        for b_size in block_sizes:
            graph.reset()
            # Generate deterministic test burst
            pcm_in = np.sin(2.0 * np.pi * 1000.0 * np.arange(b_size) / sample_rate).astype(np.float32)
            input_block = PCMBlock.from_array(pcm_in[np.newaxis, :], sample_rate=sample_rate)

            outputs = graph.process(input_block)
            assert isinstance(outputs, dict)
            assert len(outputs) == 3

            for port_key, out_block in outputs.items():
                assert out_block.samples.shape == (1, b_size)
                assert np.all(np.isfinite(out_block.samples))

        # Step 10: State Reset Determinism
        graph.reset()
        test_data = np.random.normal(0.0, 0.5, size=(1, 128)).astype(np.float32)
        in_block = PCMBlock.from_array(test_data, sample_rate=sample_rate)

        out_run_1 = graph.process(in_block)
        graph.reset()
        out_run_2 = graph.process(in_block)

        for port_key in out_run_1.keys():
            np.testing.assert_array_equal(out_run_1[port_key].samples, out_run_2[port_key].samples)
