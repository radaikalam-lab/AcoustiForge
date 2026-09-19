"""AcoustiForge Linux & Single-Board Computer (SBC) Audio Execution Hook Interface.

Defines the platform adapter boundary for Linux desktop (ALSA / PipeWire / JACK)
and headless SBCs (Raspberry Pi, Orange Pi, Rockchip) without introducing platform
dependencies or binary bindings.

Normative Authority:
- docs/architecture/PHASE_5_2_PLATFORM_AUDIO_EXECUTION_HOOK_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional, Union

from ..contracts.pcm import PCMBlock
from ..contracts.validation import (
    InvalidGraphError,
    MalformedBufferError,
)
from ..graph.compute_graph import ComputeGraph, GraphLifecycle
from .interface import (
    AudioExecutionBackend,
    ExecutionConfigError,
    ExecutionDeviceError,
    ExecutionState,
    ExecutionStateError,
    StreamConfig,
)


@dataclass(frozen=True, slots=True)
class LinuxStreamConfig(StreamConfig):
    """Extended stream configuration tailored for Linux & SBC audio subsystems.

    Attributes:
        alsa_device: Target ALSA PCM device string (e.g., 'default', 'hw:0,0', 'hw:CARD=DAC,DEV=0').
        periods_per_buffer: Number of period chunks per hardware ring buffer (default: 4).
        is_headless_appliance: Whether this stream is running inside a headless SBC appliance service.
    """
    alsa_device: str = "default"
    periods_per_buffer: int = 4
    is_headless_appliance: bool = False

    def __post_init__(self) -> None:
        StreamConfig.__post_init__(self)

        if not isinstance(self.alsa_device, str) or not self.alsa_device.strip():
            raise ExecutionConfigError(f"alsa_device must be a non-empty string, got {self.alsa_device!r}.")

        if (
            not isinstance(self.periods_per_buffer, int)
            or isinstance(self.periods_per_buffer, bool)
            or self.periods_per_buffer < 2
        ):
            raise ExecutionConfigError(
                f"periods_per_buffer must be an integer >= 2, got {self.periods_per_buffer!r}."
            )

        if not isinstance(self.is_headless_appliance, bool):
            raise ExecutionConfigError(
                f"is_headless_appliance must be a boolean, got {type(self.is_headless_appliance)!r}."
            )

        object.__setattr__(self, "alsa_device", self.alsa_device.strip())

    @property
    def total_buffer_frames(self) -> int:
        """Total hardware ring buffer capacity in frames."""
        return self.block_size * self.periods_per_buffer


class LinuxExecutionBackend(AudioExecutionBackend):
    """Platform-neutral Linux and Single-Board Computer audio execution adapter.

    Defines the contract for ALSA / PipeWire stream initialization, buffer periods,
    and xrun protection without calling platform binaries or importing external libraries.
    """

    def __init__(self, simulation_mode: bool = True) -> None:
        super().__init__()
        self._simulation_mode: bool = simulation_mode
        self._linux_config: Optional[LinuxStreamConfig] = None
        self._xrun_count: int = 0

    @property
    def linux_config(self) -> Optional[LinuxStreamConfig]:
        """Bound LinuxStreamConfig instance."""
        return self._linux_config

    @property
    def xrun_count(self) -> int:
        """Accumulated buffer underrun/overrun count."""
        return self._xrun_count

    def initialize(self, graph: ComputeGraph, config: StreamConfig) -> None:
        """Bind a frozen ComputeGraph and LinuxStreamConfig.

        Args:
            graph: Frozen ComputeGraph.
            config: StreamConfig or LinuxStreamConfig instance.

        Raises:
            ExecutionStateError: If backend is running or closed.
            InvalidGraphError: If graph is not frozen.
            ExecutionConfigError: If config is invalid.
        """
        if self._state == ExecutionState.RUNNING:
            raise ExecutionStateError("Cannot initialize while backend is in RUNNING state.")
        if self._state == ExecutionState.CLOSED:
            raise ExecutionStateError("Cannot initialize a CLOSED backend.")

        if not isinstance(graph, ComputeGraph):
            raise InvalidGraphError(f"Expected ComputeGraph instance, got {type(graph)!r}.")

        if graph.lifecycle != GraphLifecycle.FROZEN and not getattr(graph, "is_frozen", False):
            raise InvalidGraphError(
                f"ComputeGraph must be in FROZEN lifecycle state before binding, got {graph.lifecycle.value!r}."
            )

        if isinstance(config, LinuxStreamConfig):
            linux_cfg = config
        elif isinstance(config, StreamConfig):
            linux_cfg = LinuxStreamConfig(
                sample_rate=config.sample_rate,
                channels=config.channels,
                block_size=config.block_size,
                sample_format=config.sample_format,
                stream_name=config.stream_name,
            )
        else:
            raise ExecutionConfigError(f"Expected StreamConfig instance, got {type(config)!r}.")

        self._graph = graph
        self._config = linux_cfg
        self._linux_config = linux_cfg
        self._state = ExecutionState.CONFIGURED

    def start(self) -> None:
        """Start Linux/SBC audio stream execution."""
        if self._state == ExecutionState.RUNNING:
            return
        if self._state not in (ExecutionState.CONFIGURED, ExecutionState.STOPPED):
            raise ExecutionStateError(
                f"Cannot start backend from state {self._state.value!r}. Must be CONFIGURED or STOPPED."
            )
        self._state = ExecutionState.RUNNING

    def process(
        self,
        block: Union[PCMBlock, Mapping[str, PCMBlock]],
    ) -> Union[PCMBlock, dict[str, PCMBlock]]:
        """Process a block through the Linux execution pipeline.

        In simulation/offline mode, processes the block directly through the ComputeGraph.
        """
        if self._state != ExecutionState.RUNNING:
            raise ExecutionStateError(
                f"Cannot process block: backend is in state {self._state.value!r}, expected RUNNING."
            )

        if self._graph is None or self._config is None:
            raise ExecutionStateError("Backend is in RUNNING state but has no bound graph or configuration.")

        if isinstance(block, PCMBlock):
            if block.sample_rate != self._config.sample_rate:
                raise MalformedBufferError(
                    f"Block sample rate ({block.sample_rate} Hz) does not match Linux config ({self._config.sample_rate} Hz)."
                )
            if block.channels != self._config.channels:
                raise MalformedBufferError(
                    f"Block channel count ({block.channels}) does not match Linux config ({self._config.channels})."
                )

        return self._graph.process(block)

    def stop(self) -> None:
        """Pause Linux stream execution."""
        if self._state == ExecutionState.CLOSED:
            raise ExecutionStateError("Cannot stop a CLOSED backend.")
        if self._state == ExecutionState.RUNNING:
            self._state = ExecutionState.STOPPED

    def close(self) -> None:
        """Release Linux audio resources and enter CLOSED state."""
        self._state = ExecutionState.CLOSED
        self._graph = None
