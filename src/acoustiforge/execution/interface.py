"""AcoustiForge Audio Execution Hook Interfaces and Lifecycle Contracts.

Defines the platform-neutral boundary between the frozen ComputeGraph DSP engine
and external platform execution adapters (Linux/SBC, Windows, Mobile, Embedded).

Normative Authority:
- docs/architecture/PHASE_5_2_PLATFORM_AUDIO_EXECUTION_HOOK_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Iterator, Mapping, Optional, Union
import numpy as np

from ..contracts.pcm import AudioMetadata, PCMBlock
from ..contracts.validation import (
    AcoustiForgeError,
    InvalidGraphError,
    InvalidParameterError,
    InvalidSampleRateError,
    MalformedBufferError,
)
from ..graph.compute_graph import ComputeGraph, GraphLifecycle


# ==============================================================================
# Execution Exceptions
# ==============================================================================

class ExecutionStateError(AcoustiForgeError):
    """Raised when an invalid operation is attempted for the current execution lifecycle state."""


class ExecutionConfigError(InvalidParameterError):
    """Raised when stream configuration parameters are invalid or incompatible."""


class ExecutionDeviceError(AcoustiForgeError):
    """Base exception for platform hardware audio device, buffer, or transport errors."""


# ==============================================================================
# Lifecycle States & Stream Configuration
# ==============================================================================

class ExecutionState(str, Enum):
    """Formal lifecycle states of an audio execution backend."""
    UNINITIALIZED = "uninitialized"  # Instantiated, no graph or config bound
    CONFIGURED = "configured"        # Bound to frozen ComputeGraph & StreamConfig
    RUNNING = "running"              # Active and processing PCM blocks
    STOPPED = "stopped"              # Temporarily halted; can resume or close
    CLOSED = "closed"                # Terminated and resources released


@dataclass(frozen=True, slots=True)
class StreamConfig:
    """Immutable configuration for an audio execution stream.

    Attributes:
        sample_rate: Audio sampling frequency in Hz (must be positive integer).
        channels: Channel count (must be positive integer, typically 1 or 2 for stereo, up to N for multi-way).
        block_size: Nominal buffer quantum in frames (default: 512, must be positive).
        sample_format: Canonical sample representation string (default: "float32").
        stream_name: Non-empty identifier for telemetry and diagnostics.
    """
    sample_rate: int
    channels: int
    block_size: int = 512
    sample_format: str = "float32"
    stream_name: str = "AcoustiForgeStream"

    def __post_init__(self) -> None:
        if not isinstance(self.sample_rate, int) or isinstance(self.sample_rate, bool) or self.sample_rate <= 0:
            raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {self.sample_rate!r}.")

        if not isinstance(self.channels, int) or isinstance(self.channels, bool) or self.channels <= 0:
            raise ExecutionConfigError(f"channels must be a positive integer, got {self.channels!r}.")

        if not isinstance(self.block_size, int) or isinstance(self.block_size, bool) or self.block_size <= 0:
            raise ExecutionConfigError(f"block_size must be a positive integer frames count, got {self.block_size!r}.")

        if not isinstance(self.sample_format, str) or self.sample_format.lower() != "float32":
            raise ExecutionConfigError(
                f"Currently supported sample_format is 'float32', got {self.sample_format!r}."
            )

        if not isinstance(self.stream_name, str) or not self.stream_name.strip():
            raise ExecutionConfigError(f"stream_name must be a non-empty string, got {self.stream_name!r}.")

        object.__setattr__(self, "stream_name", self.stream_name.strip())

    @property
    def metadata(self) -> AudioMetadata:
        """Construct canonical AudioMetadata corresponding to this stream configuration."""
        return AudioMetadata(sample_rate=self.sample_rate, channels=self.channels)


# ==============================================================================
# Abstract Audio Execution Backend
# ==============================================================================

class AudioExecutionBackend(abc.ABC):
    """Abstract interface defining the execution boundary between ComputeGraph and audio runtimes."""

    def __init__(self) -> None:
        self._state: ExecutionState = ExecutionState.UNINITIALIZED
        self._graph: Optional[ComputeGraph] = None
        self._config: Optional[StreamConfig] = None

    @property
    def state(self) -> ExecutionState:
        """Current execution lifecycle state."""
        return self._state

    @property
    def graph(self) -> Optional[ComputeGraph]:
        """Bound ComputeGraph instance, if configured."""
        return self._graph

    @property
    def config(self) -> Optional[StreamConfig]:
        """Bound StreamConfig instance, if configured."""
        return self._config

    @abc.abstractmethod
    def initialize(self, graph: ComputeGraph, config: StreamConfig) -> None:
        """Bind a frozen ComputeGraph and stream configuration to this backend.

        Raises:
            ExecutionStateError: If backend is already running or closed.
            InvalidGraphError: If graph is not a frozen ComputeGraph.
            ExecutionConfigError: If configuration is invalid.
        """
        pass

    @abc.abstractmethod
    def start(self) -> None:
        """Transition backend into the RUNNING state to begin PCM processing.

        Raises:
            ExecutionStateError: If backend is not in CONFIGURED or STOPPED state.
        """
        pass

    @abc.abstractmethod
    def process(
        self,
        block: Union[PCMBlock, Mapping[str, PCMBlock]],
    ) -> Union[PCMBlock, dict[str, PCMBlock]]:
        """Process a discrete PCM block or multi-port block mapping through the execution pipeline.

        Args:
            block: Incoming PCMBlock or dictionary mapping input port names to PCMBlocks.

        Returns:
            Processed PCMBlock or dictionary of output port blocks.

        Raises:
            ExecutionStateError: If backend is not in RUNNING state.
            MalformedBufferError: If block sample rate, channel count, or dimensions mismatch config.
        """
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        """Transition backend into the STOPPED state, pausing processing while retaining state."""
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """Terminate backend, release all internal buffers and platform handles, and enter CLOSED state."""
        pass


# ==============================================================================
# Audio Execution Controller
# ==============================================================================

class AudioExecutionController:
    """Higher-level execution coordinator managing backend lifecycles and stream flows.

    Provides context-management, stream generators, and safe batching around an AudioExecutionBackend.
    """

    def __init__(self, backend: AudioExecutionBackend) -> None:
        if not isinstance(backend, AudioExecutionBackend):
            raise InvalidParameterError(
                f"backend must be an AudioExecutionBackend instance, got {type(backend)!r}."
            )
        self._backend: AudioExecutionBackend = backend

    @property
    def backend(self) -> AudioExecutionBackend:
        """Underlying execution backend instance."""
        return self._backend

    @property
    def state(self) -> ExecutionState:
        """Current lifecycle state of the underlying backend."""
        return self._backend.state

    def configure(self, graph: ComputeGraph, config: StreamConfig) -> None:
        """Configure the backend with a ComputeGraph and stream parameters."""
        self._backend.initialize(graph=graph, config=config)

    def start(self) -> None:
        """Start the execution backend."""
        self._backend.start()

    def process(
        self,
        block: Union[PCMBlock, Mapping[str, PCMBlock]],
    ) -> Union[PCMBlock, dict[str, PCMBlock]]:
        """Pass a PCM block through the underlying backend."""
        return self._backend.process(block)

    def process_stream(
        self,
        stream: Iterable[PCMBlock],
    ) -> Iterator[Union[PCMBlock, dict[str, PCMBlock]]]:
        """Stream an iterable sequence of PCMBlocks through the active backend.

        Args:
            stream: Iterable yielding PCMBlock objects.

        Yields:
            Processed output PCMBlock (or dict of blocks).
        """
        if self.state != ExecutionState.RUNNING:
            raise ExecutionStateError(
                f"Cannot process stream: backend is in state {self.state.value!r}, expected RUNNING."
            )
        for in_block in stream:
            yield self._backend.process(in_block)

    def stop(self) -> None:
        """Stop backend execution."""
        self._backend.stop()

    def close(self) -> None:
        """Close backend and release resources."""
        self._backend.close()

    def __enter__(self) -> AudioExecutionController:
        if self.state in (ExecutionState.CONFIGURED, ExecutionState.STOPPED):
            self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.state == ExecutionState.RUNNING:
            self.stop()
        if self.state != ExecutionState.CLOSED:
            self.close()
