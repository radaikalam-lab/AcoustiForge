"""Tests for End-to-End Acoustic Graph Construction and PCM Execution.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import numpy as np
import pytest

from acoustiforge.acoustic_math.alignment import calculate_system_alignments
from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads
from acoustiforge.acoustic_math.protection import derive_protection_filter_for_driver
from acoustiforge.acoustic_math.sensitivity import calculate_system_sensitivity_gains
from acoustiforge.builders.crossover_builder import CrossoverGraphBuilder
from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.domain.profiles import DriverProfile, DriverRole, EnclosureProfile, EnclosureType
from acoustiforge.domain.specifications import CrossoverFamily, CrossoverSpecification, TransducerLimits


class TestEndToEndAcousticGraph:
    """End-to-end integration and PCM execution verification."""

    def test_pure_lr4_crossover_impulse_summation_flat_allpass(self) -> None:
        """Verify that pure LR-4 crossover graph execution sums to flat all-pass magnitude response."""
        fs = 48000
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=2000.0,
        )
        synth = synthesize_crossover_biquads(spec, sample_rate=fs)

        builder = CrossoverGraphBuilder(sample_rate=fs, woofer_name="woofer", tweeter_name="tweeter")
        graph = builder.build_2way_graph(crossover_result=synth)

        # Create Dirac unit impulse block: 1 channel, 4096 frames
        num_frames = 4096
        impulse_samples = np.zeros((1, num_frames), dtype=np.float32)
        impulse_samples[0, 0] = 1.0
        meta = AudioMetadata(sample_rate=fs, channels=1)
        input_block = PCMBlock(samples=impulse_samples, metadata=meta)

        # Execute through graph
        out_blocks = graph.process(input_block)
        assert isinstance(out_blocks, dict)

        # graph.outputs: (woofer_node, "out"), (tweeter_node, "out")
        woofer_key = f"{graph.outputs[0][0]}.{graph.outputs[0][1]}"
        tweeter_key = f"{graph.outputs[1][0]}.{graph.outputs[1][1]}"
        woofer_out = out_blocks[woofer_key].samples[0]
        tweeter_out = out_blocks[tweeter_key].samples[0]

        # Sum the acoustic impulse responses
        summed_ir = woofer_out + tweeter_out

        # Compute FFT
        fft_sum = np.fft.rfft(summed_ir)
        mag_sum = np.abs(fft_sum)
        freqs = np.fft.rfftfreq(num_frames, d=1.0 / fs)

        # Verify flat magnitude across passband [40 Hz, 20000 Hz]
        valid_mask = (freqs >= 40.0) & (freqs <= 20000.0)
        np.testing.assert_allclose(mag_sum[valid_mask], 1.0, rtol=1e-3, atol=1e-3)

    def test_full_system_vertical_slice_execution(self) -> None:
        """Verify full vertical slice: Domain Profiles -> 3C Math -> 3D Graph -> PCM Execution."""
        fs = 48000
        # 1. Domain Data
        woofer_limits = TransducerLimits(x_max_mm=5.0, p_max_rms_watts=60.0, f_s_hz=42.0, r_e_ohms=5.6)
        woofer = DriverProfile(
            name="woofer",
            role=DriverRole.WOOFER,
            sensitivity_db=86.0,
            depth_offset_mm=35.0,
            limits=woofer_limits,
        )
        tweeter = DriverProfile(
            name="tweeter",
            role=DriverRole.TWEETER,
            sensitivity_db=91.0,
            depth_offset_mm=0.0,
        )
        enclosure = EnclosureProfile(
            enclosure_type=EnclosureType.VENTED,
            volume_liters=30.0,
            tuning_frequency_hz=38.0,
        )
        xover_spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=2200.0,
        )

        # 2. Phase 3C Mathematics
        xover_result = synthesize_crossover_biquads(xover_spec, sample_rate=fs)
        alignments = calculate_system_alignments([woofer, tweeter], sample_rate=fs)
        gains = calculate_system_sensitivity_gains([woofer, tweeter])
        woofer_prot = derive_protection_filter_for_driver(woofer, enclosure, sample_rate=fs, order=2)
        protections = {"woofer": woofer_prot}

        # 3. Phase 3D Graph Construction
        builder = CrossoverGraphBuilder(sample_rate=fs, woofer_name="woofer", tweeter_name="tweeter")
        graph = builder.build_2way_graph(
            crossover_result=xover_result,
            alignments=alignments,
            gains=gains,
            protections=protections,
        )

        assert graph.is_frozen

        # 4. Stream Execution: Multi-block audio processing
        num_blocks = 5
        block_size = 256
        rng = np.random.default_rng(12345)

        for b_idx in range(num_blocks):
            noise = rng.standard_normal((1, block_size)).astype(np.float32) * 0.1
            meta = AudioMetadata(sample_rate=fs, channels=1)
            block = PCMBlock(samples=noise, metadata=meta)

            outputs = graph.process(block)
            assert isinstance(outputs, dict)

            assert len(outputs) == 2
            for port_id, out_block in outputs.items():
                assert out_block.shape == (1, block_size)
                assert np.all(np.isfinite(out_block.samples))
                assert out_block.sample_rate == fs
                assert out_block.channels == 1
