"""AcoustiForge Platform Audio Execution Hook Package.

Provides platform-neutral execution boundaries, lifecycle controllers, and
offline and Linux ALSA backends for driving frozen ComputeGraph pipelines across desktop,
single-board computers (Raspberry Pi/SBC), mobile, and embedded runtimes.
"""

from __future__ import annotations

from .alsa import (
    AlsaCtypesBinding,
    AlsaExecutionBackend,
    AlsaPCMAdapter,
    IAlsaDeviceHandle,
    MockAlsaDeviceHandle,
    NativeAlsaDeviceHandle,
)
from .interface import (
    AudioExecutionBackend,
    AudioExecutionController,
    ExecutionConfigError,
    ExecutionDeviceError,
    ExecutionState,
    ExecutionStateError,
    StreamConfig,
)
from .linux import LinuxExecutionBackend, LinuxStreamConfig
from .offline import OfflineExecutionBackend

__all__ = [
    "ExecutionState",
    "ExecutionStateError",
    "ExecutionConfigError",
    "ExecutionDeviceError",
    "StreamConfig",
    "AudioExecutionBackend",
    "AudioExecutionController",
    "OfflineExecutionBackend",
    "LinuxExecutionBackend",
    "LinuxStreamConfig",
    "AlsaExecutionBackend",
    "AlsaPCMAdapter",
    "AlsaCtypesBinding",
    "IAlsaDeviceHandle",
    "MockAlsaDeviceHandle",
    "NativeAlsaDeviceHandle",
]
