# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Set up environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the application
python main.py

# Run the pipeline debugger demo (standalone, not a test suite)
python main_test.py
```

There is no formal test runner or linter configured.

## Architecture

This is a **PyQt6 desktop app** for multi-channel audio visualisation and Direction-of-Arrival (DOA) estimation. The codebase has two distinct layers that should be kept separate:

### Logic layer (`logic/`) — pure Python, no Qt

Generator-based audio processing pipeline. Each stage takes a generator and yields a new one, enabling lazy streaming with no Qt dependency.

```
Loader.stream() → AudioChunk
    └─ StftProcessor.process() → StftChunk
           └─ DoaProcessor.process() → DoaChunk
                  └─ MedianDoaProcessor.process() → DoaChunk (smoothed)
```

- `loader.py` — `AudioChunk` dataclass + `Loader` ABC. `data` is always `(frames, channels)` float32 in `[-1.0, 1.0]`.
- `wav_loader.py` / `live_loader.py` — concrete `Loader` implementations for files and real-time mic.
- `stft_processor.py` — per-channel STFT; `magnitudes` shape is `(n_channels, n_freqs, n_frames)` complex.
- `doa_processor.py` — NormMUSIC via pyroomacoustics. `nfft` **must** match the value used in `StftProcessor`.
- `median_doa_processor.py` — sliding-window circular median smoother over `DoaChunk` azimuths.

Spatial aliasing notes (relevant when setting `freq_range` in `DoaProcessor`): outer mic ring (48 cm diagonal) ≤ 357 Hz; inner ring (21 cm diagonal): 400–808 Hz.

### UI layer (`tabs/`, `widgets/`, `audio/`)

- `main.py` — `QMainWindow` with a `QTabWidget` (file tab + mic tab) and a `LogWidget` footer.
- `tabs/file_tab.py` — WAV file browser, pyqtgraph waveform plot, playback controls. Partially implemented (browse works; playback wiring is stubbed).
- `tabs/mic_tab.py` — stub, not yet implemented.
- `widgets/log_widget.py` — bridges Python `logging` to a Qt `QTextEdit` via a custom `LogHandler` + `pyqtSignal`. Attaches to the root logger.
- `audio/manager.py` / `audio/mic_manager.py` — `QObject`-based audio managers that drive `sounddevice` streams and emit `levels_updated` / `status_changed` signals. Not yet wired into the current tab UI.
- `components/` — older component stubs, not used by `main.py`.

### Notebooks (`notebooks/`)

Exploratory Jupyter notebooks for filter design, STFT exploration, and DOA tuning. Not part of the app; useful for algorithm prototyping before integrating into `logic/`.
