"""AcoustiForge Linux ALSA Hardware Audio Execution Backend.

Provides real ALSA PCM playback integration, planar-to-interleaved buffer conversion,
xrun detection and recovery, and lifecycle management for Linux desktops and
Single-Board Computers (Raspberry Pi/SBCs).

Normative Authority:
- docs/architecture/PHASE_5_2_PLATFORM_AUDIO_EXECUTION_HOOK_DISCOVERY.md
- docs/architecture/PHASE_5_3_LINUX_SBC_EXECUTION_HOOK_IMPLEMENTATION.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import ctypes
import math
import os
import sys
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Union
import numpy as np

from ..contracts.pcm import AudioMetadata, PCMBlock
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
from .linux import LinuxExecutionBackend, LinuxStreamConfig


# ==============================================================================
# ALSA C Constants & Error Codes
# ==============================================================================

SND_PCM_STREAM_PLAYBACK = 0
SND_PCM_STREAM_CAPTURE = 1

SND_PCM_ACCESS_MMAP_INTERLEAVED = 0
SND_PCM_ACCESS_MMAP_NONINTERLEAVED = 1
SND_PCM_ACCESS_RW_INTERLEAVED = 3
SND_PCM_ACCESS_RW_NONINTERLEAVED = 4

SND_PCM_FORMAT_UNKNOWN = -1
SND_PCM_FORMAT_S8 = 0
SND_PCM_FORMAT_U8 = 1
SND_PCM_FORMAT_S16_LE = 2
SND_PCM_FORMAT_S16_BE = 3
SND_PCM_FORMAT_S24_LE = 6
SND_PCM_FORMAT_S32_LE = 10
SND_PCM_FORMAT_FLOAT_LE = 14

SND_PCM_STATE_OPEN = 0
SND_PCM_STATE_SETUP = 1
SND_PCM_STATE_PREPARED = 2
SND_PCM_STATE_RUNNING = 3
SND_PCM_STATE_XRUN = 4
SND_PCM_STATE_DRAINING = 5
SND_PCM_STATE_PAUSED = 6
SND_PCM_STATE_SUSPENDED = 7
SND_PCM_STATE_DISCONNECTED = 8

# Standard POSIX errno values on Linux
EPIPE = 32       # Broken pipe (ALSA underrun)
ESTRPIPE = 86    # Streams pipe error (ALSA suspended)
EBADFD = 77      # File descriptor in bad state
EINVAL = 22      # Invalid argument
EIO = 5          # I/O error (fatal hardware failure)


# ==============================================================================
# Planar <-> Interleaved PCM Format Adapter
# ==============================================================================

class AlsaPCMAdapter:
    """Deterministic converter between AcoustiForge planar PCMBlock and ALSA buffers."""

    @staticmethod
    def planar_float32_to_interleaved_float32(block: PCMBlock) -> np.ndarray:
        """Convert a planar float32 PCMBlock (channels, frames) to interleaved float32 (frames * channels).

        Args:
            block: Valid planar float32 PCMBlock.

        Returns:
            1D contiguous float32 numpy array of interleaved samples.
        """
        if not isinstance(block, PCMBlock):
            raise MalformedBufferError(f"Expected PCMBlock, got {type(block)!r}.")
        # samples shape: (channels, frames) -> transpose to (frames, channels) -> flatten to 1D
        interleaved = np.ascontiguousarray(block.samples.T.reshape(-1), dtype=np.float32)
        return interleaved

    @staticmethod
    def interleaved_float32_to_planar_pcm_block(
        interleaved: np.ndarray,
        sample_rate: int,
        channels: int,
    ) -> PCMBlock:
        """Convert an interleaved float32 buffer to a canonical planar float32 PCMBlock.

        Args:
            interleaved: 1D array of interleaved float32 samples.
            sample_rate: Audio sampling rate in Hz.
            channels: Channel count.

        Returns:
            Canonical planar float32 PCMBlock of shape (channels, frames).
        """
        if not isinstance(interleaved, np.ndarray):
            raise MalformedBufferError(f"Expected numpy ndarray, got {type(interleaved)!r}.")
        if interleaved.size % channels != 0:
            raise MalformedBufferError(
                f"Buffer size {interleaved.size} is not divisible by channel count {channels}."
            )
        frames = interleaved.size // channels
        planar = np.ascontiguousarray(interleaved.reshape(frames, channels).T, dtype=np.float32)
        metadata = AudioMetadata(sample_rate=sample_rate, channels=channels)
        return PCMBlock(samples=planar, metadata=metadata)

    @staticmethod
    def planar_float32_to_interleaved_int16(block: PCMBlock) -> np.ndarray:
        """Convert a planar float32 PCMBlock to interleaved 16-bit signed integer PCM.

        Applies symmetrical clipping to [-1.0, 1.0] and scales to [-32768, 32767].
        """
        if not isinstance(block, PCMBlock):
            raise MalformedBufferError(f"Expected PCMBlock, got {type(block)!r}.")
        clamped = np.clip(block.samples, -1.0, 1.0)
        scaled = np.round(clamped * 32767.0).astype(np.int16)
        interleaved = np.ascontiguousarray(scaled.T.reshape(-1), dtype=np.int16)
        return interleaved

    @staticmethod
    def interleaved_int16_to_planar_pcm_block(
        interleaved: np.ndarray,
        sample_rate: int,
        channels: int,
    ) -> PCMBlock:
        """Convert interleaved 16-bit signed integer PCM to canonical planar float32 PCMBlock."""
        if not isinstance(interleaved, np.ndarray):
            raise MalformedBufferError(f"Expected numpy ndarray, got {type(interleaved)!r}.")
        if interleaved.size % channels != 0:
            raise MalformedBufferError(
                f"Buffer size {interleaved.size} is not divisible by channel count {channels}."
            )
        frames = interleaved.size // channels
        planar_int16 = interleaved.reshape(frames, channels).T
        planar_float = np.ascontiguousarray(planar_int16.astype(np.float32) / 32767.0, dtype=np.float32)
        metadata = AudioMetadata(sample_rate=sample_rate, channels=channels)
        return PCMBlock(samples=planar_float, metadata=metadata)


# ==============================================================================
# ALSA Ctypes Library Dynamic Binding
# ==============================================================================

class AlsaCtypesBinding:
    """Dynamic binding to Linux libasound.so.2 using ctypes.

    Provides transparent binding when on Linux with libasound installed, or graceful
    indication of unavailability on Windows / non-ALSA environments.
    """

    _lib: Optional[ctypes.CDLL] = None
    _is_available: Optional[bool] = None

    @classmethod
    def is_available(cls) -> bool:
        """Check whether libasound.so.2 is available on the current host runtime."""
        if cls._is_available is not None:
            return cls._is_available

        if not sys.platform.startswith("linux"):
            cls._is_available = False
            return False

        try:
            cls._lib = ctypes.CDLL("libasound.so.2")
            cls._is_available = True
            cls._setup_prototypes()
        except OSError:
            cls._is_available = False

        return cls._is_available

    @classmethod
    def get_lib(cls) -> ctypes.CDLL:
        """Return the loaded libasound library instance, or raise ExecutionDeviceError."""
        if not cls.is_available() or cls._lib is None:
            raise ExecutionDeviceError(
                "ALSA library (libasound.so.2) is not available on this platform/environment."
            )
        return cls._lib

    @classmethod
    def _setup_prototypes(cls) -> None:
        """Configure C function prototypes for libasound calls."""
        if cls._lib is None:
            return

        # snd_pcm_open(snd_pcm_t **pcm, const char *name, snd_pcm_stream_t stream, int mode)
        cls._lib.snd_pcm_open.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        cls._lib.snd_pcm_open.restype = ctypes.c_int

        # snd_pcm_close(snd_pcm_t *pcm)
        cls._lib.snd_pcm_close.argtypes = [ctypes.c_void_p]
        cls._lib.snd_pcm_close.restype = ctypes.c_int

        # snd_pcm_prepare(snd_pcm_t *pcm)
        cls._lib.snd_pcm_prepare.argtypes = [ctypes.c_void_p]
        cls._lib.snd_pcm_prepare.restype = ctypes.c_int

        # snd_pcm_writei(snd_pcm_t *pcm, const void *buffer, snd_pcm_uframes_t size)
        cls._lib.snd_pcm_writei.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        cls._lib.snd_pcm_writei.restype = ctypes.c_long

        # snd_pcm_readi(snd_pcm_t *pcm, void *buffer, snd_pcm_uframes_t size)
        cls._lib.snd_pcm_readi.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        cls._lib.snd_pcm_readi.restype = ctypes.c_long

        # snd_pcm_recover(snd_pcm_t *pcm, int err, int silent)
        cls._lib.snd_pcm_recover.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        cls._lib.snd_pcm_recover.restype = ctypes.c_int

        # snd_pcm_drop(snd_pcm_t *pcm)
        cls._lib.snd_pcm_drop.argtypes = [ctypes.c_void_p]
        cls._lib.snd_pcm_drop.restype = ctypes.c_int

        # snd_pcm_drain(snd_pcm_t *pcm)
        cls._lib.snd_pcm_drain.argtypes = [ctypes.c_void_p]
        cls._lib.snd_pcm_drain.restype = ctypes.c_int

        # snd_strerror(int errnum)
        cls._lib.snd_strerror.argtypes = [ctypes.c_int]
        cls._lib.snd_strerror.restype = ctypes.c_char_p


# ==============================================================================
# ALSA Device Abstraction & Mock Interface
# ==============================================================================

class IAlsaDeviceHandle:
    """Interface representing an open ALSA PCM device handle."""

    def prepare(self) -> int:
        raise NotImplementedError

    def writei(self, buffer: np.ndarray, frames: int) -> int:
        raise NotImplementedError

    def readi(self, buffer: np.ndarray, frames: int) -> int:
        raise NotImplementedError

    def recover(self, err: int, silent: int = 1) -> int:
        raise NotImplementedError

    def drop(self) -> int:
        raise NotImplementedError

    def close(self) -> int:
        raise NotImplementedError


class MockAlsaDeviceHandle(IAlsaDeviceHandle):
    """In-memory mock ALSA device handle for platform-independent Layer A validation.

    Simulates buffer transfers, frames accounting, underruns, and recovery.
    """

    def __init__(
        self,
        device_name: str,
        sample_rate: int,
        channels: int,
        block_size: int,
        fail_on_write_count: Optional[int] = None,
        xrun_on_write_count: Optional[int] = None,
        mock_capture_source: Optional[np.ndarray] = None,
        fail_on_read_count: Optional[int] = None,
        xrun_on_read_count: Optional[int] = None,
    ) -> None:
        self.device_name: str = device_name
        self.sample_rate: int = sample_rate
        self.channels: int = channels
        self.block_size: int = block_size
        self.fail_on_write_count: Optional[int] = fail_on_write_count
        self.xrun_on_write_count: Optional[int] = xrun_on_write_count
        self.mock_capture_source: Optional[np.ndarray] = mock_capture_source
        self.fail_on_read_count: Optional[int] = fail_on_read_count
        self.xrun_on_read_count: Optional[int] = xrun_on_read_count

        self.is_prepared: bool = False
        self.is_closed: bool = False
        self.total_writes: int = 0
        self.total_frames_written: int = 0
        self.total_reads: int = 0
        self.total_frames_read: int = 0
        self._read_cursor: int = 0
        self.recovered_xruns: int = 0
        self.captured_buffers: list[np.ndarray] = []

    def prepare(self) -> int:
        if self.is_closed:
            return -EBADFD
        self.is_prepared = True
        return 0

    def writei(self, buffer: np.ndarray, frames: int) -> int:
        if self.is_closed:
            return -EBADFD
        if not self.is_prepared:
            return -EBADFD

        self.total_writes += 1

        # Simulate fatal hardware failure if programmed
        if self.fail_on_write_count is not None and self.total_writes == self.fail_on_write_count:
            return -EIO

        # Simulate recoverable xrun if programmed
        if self.xrun_on_write_count is not None and self.total_writes == self.xrun_on_write_count:
            self.is_prepared = False
            return -EPIPE

        self.captured_buffers.append(buffer.copy())
        self.total_frames_written += frames
        return frames

    def readi(self, buffer: np.ndarray, frames: int) -> int:
        if self.is_closed:
            return -EBADFD
        if not self.is_prepared:
            return -EBADFD

        self.total_reads += 1

        # Simulate fatal hardware read failure if programmed
        if self.fail_on_read_count is not None and self.total_reads == self.fail_on_read_count:
            return -EIO

        # Simulate recoverable xrun on read (overrun) if programmed
        if self.xrun_on_read_count is not None and self.total_reads == self.xrun_on_read_count:
            self.is_prepared = False
            return -EPIPE

        needed_samples = frames * self.channels
        if self.mock_capture_source is not None:
            available = len(self.mock_capture_source) - self._read_cursor
            if available <= 0:
                buffer[:needed_samples] = 0
            else:
                to_copy = min(needed_samples, available)
                buffer[:to_copy] = self.mock_capture_source[self._read_cursor : self._read_cursor + to_copy]
                if to_copy < needed_samples:
                    buffer[to_copy:needed_samples] = 0
                self._read_cursor += to_copy
        else:
            buffer[:needed_samples] = 0

        self.total_frames_read += frames
        return frames

    def recover(self, err: int, silent: int = 1) -> int:
        if self.is_closed:
            return -EBADFD
        if err in (-EPIPE, -ESTRPIPE):
            self.is_prepared = True
            self.recovered_xruns += 1
            return 0
        return err

    def drop(self) -> int:
        if self.is_closed:
            return -EBADFD
        self.is_prepared = False
        return 0

    def close(self) -> int:
        self.is_closed = True
        self.is_prepared = False
        return 0


class NativeAlsaDeviceHandle(IAlsaDeviceHandle):
    """Real native Linux ALSA device handle invoking libasound via ctypes."""

    def __init__(self, pcm_ptr: ctypes.c_void_p, lib: ctypes.CDLL) -> None:
        self._pcm_ptr: ctypes.c_void_p = pcm_ptr
        self._lib: ctypes.CDLL = lib
        self._is_closed: bool = False

    def prepare(self) -> int:
        if self._is_closed:
            return -EBADFD
        return int(self._lib.snd_pcm_prepare(self._pcm_ptr))

    def writei(self, buffer: np.ndarray, frames: int) -> int:
        if self._is_closed:
            return -EBADFD
        buf_ptr = buffer.ctypes.data_as(ctypes.c_void_p)
        return int(self._lib.snd_pcm_writei(self._pcm_ptr, buf_ptr, ctypes.c_ulong(frames)))

    def readi(self, buffer: np.ndarray, frames: int) -> int:
        if self._is_closed:
            return -EBADFD
        buf_ptr = buffer.ctypes.data_as(ctypes.c_void_p)
        return int(self._lib.snd_pcm_readi(self._pcm_ptr, buf_ptr, ctypes.c_ulong(frames)))

    def recover(self, err: int, silent: int = 1) -> int:
        if self._is_closed:
            return -EBADFD
        return int(self._lib.snd_pcm_recover(self._pcm_ptr, ctypes.c_int(err), ctypes.c_int(silent)))

    def drop(self) -> int:
        if self._is_closed:
            return -EBADFD
        return int(self._lib.snd_pcm_drop(self._pcm_ptr))

    def close(self) -> int:
        if self._is_closed:
            return 0
        res = int(self._lib.snd_pcm_close(self._pcm_ptr))
        self._is_closed = True
        self._pcm_ptr = None
        return res


# ==============================================================================
# ALSA Execution Backend
# ==============================================================================

class AlsaExecutionBackend(LinuxExecutionBackend):
    """Concrete Linux ALSA hardware audio execution backend.

    Executes blocks through the frozen ComputeGraph and transfers the resulting PCM
    directly to configured ALSA audio hardware with xrun recovery and error isolation.
    """

    def __init__(
        self,
        mock_handle: Optional[IAlsaDeviceHandle] = None,
        auto_recover_xruns: bool = True,
    ) -> None:
        super().__init__(simulation_mode=(mock_handle is not None or not AlsaCtypesBinding.is_available()))
        self._mock_handle: Optional[IAlsaDeviceHandle] = mock_handle
        self._handle: Optional[IAlsaDeviceHandle] = None
        self._auto_recover_xruns: bool = auto_recover_xruns
        self._recovered_xrun_count: int = 0
        self._frames_transferred: int = 0

    @property
    def recovered_xrun_count(self) -> int:
        """Total number of successfully recovered buffer underruns (xruns)."""
        return self._recovered_xrun_count

    @property
    def frames_transferred(self) -> int:
        """Total number of PCM frames transferred to ALSA hardware."""
        return self._frames_transferred

    def start(self) -> None:
        """Open ALSA PCM device, prepare stream, and enter RUNNING state."""
        if self._state == ExecutionState.RUNNING:
            return
        if self._state not in (ExecutionState.CONFIGURED, ExecutionState.STOPPED):
            raise ExecutionStateError(
                f"Cannot start ALSA backend from state {self._state.value!r}. Must be CONFIGURED or STOPPED."
            )

        if self._linux_config is None:
            raise ExecutionStateError("ALSA backend has no valid stream configuration.")

        # Open device handle if not already opened
        if self._handle is None:
            if self._mock_handle is not None:
                self._handle = self._mock_handle
            elif AlsaCtypesBinding.is_available():
                lib = AlsaCtypesBinding.get_lib()
                pcm_ptr = ctypes.c_void_p()
                dev_bytes = self._linux_config.alsa_device.encode("utf-8")
                err = lib.snd_pcm_open(
                    ctypes.byref(pcm_ptr),
                    dev_bytes,
                    SND_PCM_STREAM_PLAYBACK,
                    0,
                )
                if err < 0:
                    err_str = lib.snd_strerror(err).decode("utf-8") if hasattr(lib, "snd_strerror") else str(err)
                    raise ExecutionDeviceError(
                        f"Failed to open ALSA playback device {self._linux_config.alsa_device!r}: {err_str} (error {err})."
                    )
                self._handle = NativeAlsaDeviceHandle(pcm_ptr, lib)
            else:
                # On Windows / non-ALSA runtime without explicit mock handle, create default mock handle
                self._handle = MockAlsaDeviceHandle(
                    device_name=self._linux_config.alsa_device,
                    sample_rate=self._linux_config.sample_rate,
                    channels=self._linux_config.channels,
                    block_size=self._linux_config.block_size,
                )

        # Prepare ALSA PCM device for streaming
        prep_err = self._handle.prepare()
        if prep_err < 0:
            raise ExecutionDeviceError(f"Failed to prepare ALSA PCM stream: error code {prep_err}.")

        self._state = ExecutionState.RUNNING

    def process(
        self,
        block: Union[PCMBlock, Mapping[str, PCMBlock]],
    ) -> Union[PCMBlock, dict[str, PCMBlock]]:
        """Process incoming block through ComputeGraph and transfer PCM to ALSA hardware.

        Args:
            block: Incoming planar float32 PCMBlock.

        Returns:
            Processed PCMBlock resulting from the ComputeGraph execution.

        Raises:
            ExecutionStateError: If backend is not RUNNING.
            ExecutionDeviceError: If an unrecoverable ALSA hardware error occurs.
            MalformedBufferError: If block sample rate or channels mismatch stream config.
        """
        if self._state != ExecutionState.RUNNING:
            raise ExecutionStateError(
                f"Cannot process block: ALSA backend is in state {self._state.value!r}, expected RUNNING."
            )

        if self._graph is None or self._linux_config is None or self._handle is None:
            raise ExecutionStateError("ALSA backend has missing graph, config, or device handle.")

        # 1. Validate block properties
        if isinstance(block, PCMBlock):
            if block.sample_rate != self._linux_config.sample_rate:
                raise MalformedBufferError(
                    f"Block sample rate ({block.sample_rate} Hz) does not match ALSA config ({self._linux_config.sample_rate} Hz)."
                )
            if block.channels != self._linux_config.channels:
                raise MalformedBufferError(
                    f"Block channel count ({block.channels}) does not match ALSA config ({self._linux_config.channels})."
                )

        # 2. Execute deterministic DSP graph
        out_result = self._graph.process(block)

        # 3. Format conversion: Planar float32 -> Interleaved float32
        if isinstance(out_result, PCMBlock):
            interleaved = AlsaPCMAdapter.planar_float32_to_interleaved_float32(out_result)
            frames_to_write = out_result.frames
        elif isinstance(out_result, dict):
            # For multi-port crossover outputs, take the primary output port
            first_key = next(iter(out_result.keys()))
            first_block = out_result[first_key]
            interleaved = AlsaPCMAdapter.planar_float32_to_interleaved_float32(first_block)
            frames_to_write = first_block.frames
        else:
            raise MalformedBufferError(f"Unexpected graph output type {type(out_result)!r}.")

        # 4. Transfer to ALSA hardware via snd_pcm_writei
        written = self._handle.writei(interleaved, frames_to_write)

        # 5. Handle write result & xruns
        if written < 0:
            self._xrun_count += 1
            if self._auto_recover_xruns and written in (-EPIPE, -ESTRPIPE):
                rec_err = self._handle.recover(written, silent=1)
                if rec_err == 0:
                    self._recovered_xrun_count += 1
                    # Retry write after successful recovery
                    retry_written = self._handle.writei(interleaved, frames_to_write)
                    if retry_written > 0:
                        self._frames_transferred += retry_written
                        return out_result
            # Unrecoverable error or failed retry
            self._state = ExecutionState.STOPPED
            raise ExecutionDeviceError(
                f"ALSA hardware write error: code {written} on device {self._linux_config.alsa_device!r}."
            )

        self._frames_transferred += written
        return out_result

    def stop(self) -> None:
        """Stop ALSA playback stream."""
        if self._state == ExecutionState.CLOSED:
            raise ExecutionStateError("Cannot stop a CLOSED ALSA backend.")
        if self._state == ExecutionState.RUNNING:
            if self._handle is not None:
                self._handle.drop()
            self._state = ExecutionState.STOPPED

    def close(self) -> None:
        """Release ALSA device handle and enter CLOSED state."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None
        self._state = ExecutionState.CLOSED
        self._graph = None


# ==============================================================================
# ALSA Audio Capture Subsystem (Unit C)
# ==============================================================================

@dataclass(frozen=True, slots=True)
class AlsaCaptureConfig:
    """Immutable configuration specification for ALSA audio capture devices."""

    alsa_device: str = "default"
    sample_rate: int = 48000
    channels: int = 1
    block_size: int = 256
    use_int16: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.alsa_device, str) or not self.alsa_device.strip():
            raise ExecutionConfigError(f"alsa_device must be a non-empty string, got {self.alsa_device!r}.")
        if not isinstance(self.sample_rate, int) or isinstance(self.sample_rate, bool) or self.sample_rate <= 0:
            raise ExecutionConfigError(f"sample_rate must be a positive integer, got {self.sample_rate!r}.")
        if not (8000 <= self.sample_rate <= 384000):
            raise ExecutionConfigError(
                f"sample_rate ({self.sample_rate} Hz) is outside supported range [8000, 384000] Hz."
            )
        if not isinstance(self.channels, int) or isinstance(self.channels, bool) or self.channels < 1:
            raise ExecutionConfigError(f"channels must be an integer >= 1, got {self.channels!r}.")
        if not isinstance(self.block_size, int) or isinstance(self.block_size, bool) or self.block_size < 1:
            raise ExecutionConfigError(f"block_size must be an integer >= 1, got {self.block_size!r}.")


class AlsaAudioCapture:
    """Concrete Linux ALSA hardware audio recording and capture engine.

    Acquires audio frames from physical or simulated ALSA capture devices (e.g. USB measurement microphones),
    performs format conversion to canonical planar float32 PCMBlocks, and handles overrun recovery.
    """

    def __init__(
        self,
        config: AlsaCaptureConfig,
        mock_handle: Optional[IAlsaDeviceHandle] = None,
        auto_recover_xruns: bool = True,
    ) -> None:
        if not isinstance(config, AlsaCaptureConfig):
            raise ExecutionConfigError(f"Expected AlsaCaptureConfig, got {type(config)!r}.")
        self._config: AlsaCaptureConfig = config
        self._mock_handle: Optional[IAlsaDeviceHandle] = mock_handle
        self._handle: Optional[IAlsaDeviceHandle] = None
        self._auto_recover_xruns: bool = auto_recover_xruns
        self._state: ExecutionState = ExecutionState.UNINITIALIZED
        self._xrun_count: int = 0
        self._recovered_xrun_count: int = 0
        self._frames_captured: int = 0

    @property
    def config(self) -> AlsaCaptureConfig:
        """Capture configuration."""
        return self._config

    @property
    def state(self) -> ExecutionState:
        """Current execution lifecycle state."""
        return self._state

    @property
    def xrun_count(self) -> int:
        """Total number of detected buffer overruns (xruns)."""
        return self._xrun_count

    @property
    def recovered_xrun_count(self) -> int:
        """Total number of successfully recovered buffer overruns (xruns)."""
        return self._recovered_xrun_count

    @property
    def frames_captured(self) -> int:
        """Total number of PCM frames successfully captured."""
        return self._frames_captured

    def start(self) -> None:
        """Open ALSA capture device, prepare stream, and enter RUNNING state."""
        if self._state == ExecutionState.RUNNING:
            return
        if self._state == ExecutionState.CLOSED:
            raise ExecutionStateError("Cannot start a CLOSED ALSA capture instance.")

        if self._handle is None:
            if self._mock_handle is not None:
                self._handle = self._mock_handle
            elif AlsaCtypesBinding.is_available():
                lib = AlsaCtypesBinding.get_lib()
                pcm_ptr = ctypes.c_void_p()
                dev_bytes = self._config.alsa_device.encode("utf-8")
                err = lib.snd_pcm_open(
                    ctypes.byref(pcm_ptr),
                    dev_bytes,
                    SND_PCM_STREAM_CAPTURE,
                    0,
                )
                if err < 0:
                    err_str = lib.snd_strerror(err).decode("utf-8") if hasattr(lib, "snd_strerror") else str(err)
                    raise ExecutionDeviceError(
                        f"Failed to open ALSA capture device {self._config.alsa_device!r}: {err_str} (error {err})."
                    )
                self._handle = NativeAlsaDeviceHandle(pcm_ptr, lib)
            else:
                self._handle = MockAlsaDeviceHandle(
                    device_name=self._config.alsa_device,
                    sample_rate=self._config.sample_rate,
                    channels=self._config.channels,
                    block_size=self._config.block_size,
                )

        prep_err = self._handle.prepare()
        if prep_err < 0:
            raise ExecutionDeviceError(f"Failed to prepare ALSA capture stream: error code {prep_err}.")

        self._state = ExecutionState.RUNNING

    def read_block(self) -> PCMBlock:
        """Read a single block of audio frames and return a canonical planar float32 PCMBlock."""
        if self._state != ExecutionState.RUNNING or self._handle is None:
            raise ExecutionStateError(
                f"Cannot read block: ALSA capture is in state {self._state.value!r}, expected RUNNING."
            )

        frames = self._config.block_size
        channels = self._config.channels
        dtype = np.int16 if self._config.use_int16 else np.float32
        interleaved = np.empty(frames * channels, dtype=dtype)

        read_res = self._handle.readi(interleaved, frames)

        if read_res < 0:
            self._xrun_count += 1
            if self._auto_recover_xruns and read_res in (-EPIPE, -ESTRPIPE):
                rec_err = self._handle.recover(read_res, silent=1)
                if rec_err == 0:
                    self._recovered_xrun_count += 1
                    retry_res = self._handle.readi(interleaved, frames)
                    if retry_res > 0:
                        self._frames_captured += retry_res
                        if self._config.use_int16:
                            return AlsaPCMAdapter.interleaved_int16_to_planar_pcm_block(
                                interleaved, self._config.sample_rate, channels
                            )
                        else:
                            return AlsaPCMAdapter.interleaved_float32_to_planar_pcm_block(
                                interleaved, self._config.sample_rate, channels
                            )
            self._state = ExecutionState.STOPPED
            raise ExecutionDeviceError(
                f"ALSA hardware read error: code {read_res} on device {self._config.alsa_device!r}."
            )

        self._frames_captured += read_res
        if self._config.use_int16:
            return AlsaPCMAdapter.interleaved_int16_to_planar_pcm_block(
                interleaved, self._config.sample_rate, channels
            )
        else:
            return AlsaPCMAdapter.interleaved_float32_to_planar_pcm_block(
                interleaved, self._config.sample_rate, channels
            )

    def record_frames(self, total_frames: int) -> PCMBlock:
        """Record an exact number of frames and return a consolidated canonical PCMBlock."""
        if not isinstance(total_frames, int) or total_frames <= 0:
            raise ExecutionConfigError(f"total_frames must be a positive integer, got {total_frames!r}.")

        if self._state != ExecutionState.RUNNING:
            self.start()

        accumulated_blocks: list[PCMBlock] = []
        frames_gathered = 0
        while frames_gathered < total_frames:
            needed = total_frames - frames_gathered
            block = self.read_block()
            if block.frames > needed:
                # Slice last block to exact needed frames
                sliced_samples = block.samples[:, :needed]
                sliced_metadata = AudioMetadata(sample_rate=self._config.sample_rate, channels=self._config.channels)
                accumulated_blocks.append(PCMBlock(samples=sliced_samples, metadata=sliced_metadata))
                frames_gathered += needed
            else:
                accumulated_blocks.append(block)
                frames_gathered += block.frames

        all_samples = np.ascontiguousarray(np.concatenate([b.samples for b in accumulated_blocks], axis=1), dtype=np.float32)
        metadata = AudioMetadata(sample_rate=self._config.sample_rate, channels=self._config.channels)
        return PCMBlock(samples=all_samples, metadata=metadata)

    def record_duration(self, duration_seconds: float) -> PCMBlock:
        """Record audio for the specified duration in seconds."""
        if not isinstance(duration_seconds, (int, float)) or duration_seconds <= 0.0:
            raise ExecutionConfigError(f"duration_seconds must be a positive float, got {duration_seconds!r}.")
        total_frames = int(round(duration_seconds * self._config.sample_rate))
        return self.record_frames(total_frames)

    def stop(self) -> None:
        """Stop ALSA capture stream."""
        if self._state == ExecutionState.CLOSED:
            raise ExecutionStateError("Cannot stop a CLOSED ALSA capture.")
        if self._state == ExecutionState.RUNNING:
            if self._handle is not None:
                self._handle.drop()
            self._state = ExecutionState.STOPPED

    def close(self) -> None:
        """Release ALSA capture handle and enter CLOSED state."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None
        self._state = ExecutionState.CLOSED

