"""AcoustiForge Deterministic Offline Audio Execution Backend.

Reference implementation of AudioExecutionBackend executing in-memory PCMBlock streams
against a frozen ComputeGraph without external platform dependencies.

Normative Authority:
- docs/architecture/PHASE_5_2_PLATFORM_AUDIO_EXECUTION_HOOK_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

from typing import Mapping, Union

from ..contracts.pcm import PCMBlock
from ..contracts.validation import (
    InvalidGraphError,
    MalformedBufferError,
)
from ..graph.compute_graph import ComputeGraph, GraphLifecycle
from .interface import (
    AudioExecutionBackend,
    ExecutionConfigError,
    ExecutionState,
    ExecutionStateError,
    StreamConfig,
)


class OfflineExecutionBackend(AudioExecutionBackend):
    """Deterministic in-memory audio execution backend.

    Executes blocks synchronously through a validated and frozen ComputeGraph.
    Provides strict lifecycle enforcement, metadata consistency checks, and
    preserves DSP time-domain filter state across sequential process calls.
    """

    def initialize(self, graph: ComputeGraph, config: StreamConfig) -> None:
        """Bind a frozen ComputeGraph and stream configuration.

        Args:
            graph: Validated and frozen ComputeGraph instance.
            config: Validated StreamConfig instance.

        Raises:
            ExecutionStateError: If backend is running or closed.
            InvalidGraphError: If graph is not frozen or not a ComputeGraph.
            ExecutionConfigError: If config is not a StreamConfig.
        """
        if self._state == ExecutionState.RUNNING:
            raise ExecutionStateError("Cannot initialize while backend is in RUNNING state. Call stop() first.")
        if self._state == ExecutionState.CLOSED:
            raise ExecutionStateError("Cannot initialize a CLOSED backend.")

        if not isinstance(graph, ComputeGraph):
            raise InvalidGraphError(f"Expected ComputeGraph instance, got {type(graph)!r}.")

        if graph.lifecycle != GraphLifecycle.FROZEN and not getattr(graph, "is_frozen", False):
            raise InvalidGraphError(
                f"ComputeGraph must be in FROZEN lifecycle state before execution binding, got {graph.lifecycle.value!r}."
            )

        if not isinstance(config, StreamConfig):
            raise ExecutionConfigError(f"Expected StreamConfig instance, got {type(config)!r}.")

        self._graph = graph
        self._config = config
        self._state = ExecutionState.CONFIGURED

    def start(self) -> None:
        """Start the offline backend for processing."""
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
        """Process a PCM block synchronously through the bound ComputeGraph.

        Args:
            block: Incoming PCMBlock or dictionary mapping input port names to PCMBlocks.

        Returns:
            Processed PCMBlock or dictionary of output port blocks.

        Raises:
            ExecutionStateError: If backend is not in RUNNING state.
            MalformedBufferError: If block sample rate or channel count does not match configuration.
        """
        if self._state != ExecutionState.RUNNING:
            raise ExecutionStateError(
                f"Cannot process block: backend is in state {self._state.value!r}, expected RUNNING."
            )

        if self._graph is None or self._config is None:
            raise ExecutionStateError("Backend is in RUNNING state but has no bound graph or configuration.")

        # Validate input block against configured stream parameters
        if isinstance(block, PCMBlock):
            if block.sample_rate != self._config.sample_rate:
                raise MalformedBufferError(
                    f"Block sample rate ({block.sample_rate} Hz) does not match stream config ({self._config.sample_rate} Hz)."
                )
            if block.channels != self._config.channels:
                raise MalformedBufferError(
                    f"Block channel count ({block.channels}) does not match stream config ({self._config.channels})."
                )
        elif hasattr(block, "values"):
            for port_id, b_val in block.items():
                if not isinstance(b_val, PCMBlock):
                    raise MalformedBufferError(
                        f"Multi-port input for {port_id!r} must be PCMBlock, got {type(b_val)!r}."
                    )
                if b_val.sample_rate != self._config.sample_rate:
                    raise MalformedBufferError(
                        f"Port {port_id!r} block sample rate ({b_val.sample_rate} Hz) "
                        f"mismatches stream config ({self._config.sample_rate} Hz)."
                    )

        # Delegate execution directly to the frozen ComputeGraph
        return self._graph.process(block)

    def stop(self) -> None:
        """Pause offline backend execution."""
        if self._state == ExecutionState.CLOSED:
            raise ExecutionStateError("Cannot stop a CLOSED backend.")
        if self._state == ExecutionState.RUNNING:
            self._state = ExecutionState.STOPPED

    def close(self) -> None:
        """Terminate backend and release references."""
        self._state = ExecutionState.CLOSED
        self._graph = None
