# Audio Processing Pipeline

This document explains the signal processing pipeline used for multi-channel audio analysis and Direction-of-Arrival (DOA) estimation. It covers the theory behind each stage, why each step is necessary, and how the stages connect in code.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Theory: Why Each Step Exists](#2-theory-why-each-step-exists)
   - [DC Offset Removal](#21-dc-offset-removal)
   - [Resampling](#22-resampling)
   - [Bandpass Filtering](#23-bandpass-filtering)
   - [Windowing and Overlap](#24-windowing-and-overlap)
   - [STFT and Cross-Chunk Buffering](#25-stft-and-cross-chunk-buffering)
   - [Spectral Slicing](#26-spectral-slicing)
   - [DOA Estimation](#27-doa-estimation)
   - [DOA Smoothing](#28-doa-smoothing)
3. [Configuration for 7-Inch Drone Detection (100 Hz–1 kHz)](#3-configuration-for-7-inch-drone-detection-100-hz1-khz)
4. [Wiring the Pipeline in Code](#4-wiring-the-pipeline-in-code)
5. [Parameter Constraints and Gotchas](#5-parameter-constraints-and-gotchas)
6. [Sources](#6-sources)

---

## 1. Architecture Overview

The pipeline is a **chain of Python generators**. Each stage takes an upstream generator and yields a downstream one. No stage pulls more data than it needs; processing is lazy and memory-efficient.

```
Loader.stream()
  │  AudioChunk  (frames, channels)  float32  [-1, 1]
  ▼
DcOffsetFilter.process()
  │  AudioChunk  — DC spike removed
  ▼
ResampleProcessor.process()
  │  AudioChunk  — at target sample rate
  ▼
BandpassFilter.process()              ← or HighPassFilter / PeakingFilter
  │  AudioChunk  — out-of-band energy removed
  ▼
StftProcessor.process()               ← maintains cross-chunk overlap buffer
  │  StftChunk  (n_channels, n_freqs, n_frames)  complex
  ├──────────────────────────────────────────────────────────┐
  │  [DOA branch — raw complex, full spectrum]               │
  ▼                                                          ▼
DoaProcessor.process()             StftSliceProcessor.process()
  │  DoaChunk                        │  StftChunk  — sub-band only
  ▼                                  ▼
MedianDoaProcessor.process()      LogScaleProcessor.process()
  │  DoaChunk  — smoothed            │  StftChunk  — real dB values
  ▼                                  ▼
[UI / downstream]                 [Spectrogram display]
```

**Important branch rule:** `DoaProcessor` must receive the **unsliced, complex** `StftChunk`. NormMUSIC requires complex cross-spectral data across the full frequency range. The `StftSliceProcessor` and `LogScaleProcessor` outputs are for visualisation only — never feed them into `DoaProcessor`.

All logic-layer classes live in `logic/` and have zero Qt dependency.

---

## 2. Theory: Why Each Step Exists

### 2.1 DC Offset Removal

**File:** `logic/filters/dc_offset_filter.py`

A DC offset is a non-zero mean in the audio signal — the waveform sits above or below zero. In the frequency domain, this appears as a large artificial spike at 0 Hz (the first FFT bin). This spike can dominate the low-frequency portion of the spectrogram and distort DOA cross-spectral calculations.

**Fix:** subtract the per-channel mean of each chunk.

```python
data -= data.mean(axis=0)
```

This is applied before resampling so it operates on the original sample rate, removing any ADC bias introduced by the microphone hardware.

### 2.2 Resampling

**File:** `logic/resample_processor.py`

The raw microphone stream arrives at 44.1 kHz or 48 kHz. For drone detection in the 100 Hz–1 kHz band, most of that bandwidth is wasted. Downsampling to 8 kHz:

- Sets the Nyquist frequency to 4 kHz, which comfortably covers the full drone harmonic range.
- Packs FFT bins tightly into the low-frequency region, giving better frequency resolution per bin for the same FFT size.
- Reduces the data volume fed into the STFT and DOA stages by ~5×.

Resampling uses `scipy.signal.resample_poly`, which applies an anti-aliasing filter before downsampling (polyphase filtering). The up/down ratio is derived from `math.gcd` so it remains exact with no floating-point drift.

### 2.3 Bandpass Filtering

**File:** `logic/filters/bandpass_filter.py`

After resampling, a 4th-order Butterworth bandpass filter (80 Hz–1200 Hz) removes:

- **Wind rumble and handling noise** (below ~80 Hz) — these low-frequency components have very high energy and would dominate the spectrogram if left in.
- **Higher harmonics and environmental clutter** (above ~1200 Hz) — bird calls, insect chirps, and electronic noise outside the drone's harmonic series.

The filter is **stateful**: it stores the internal filter state (`_zi`) across chunks so there are no discontinuities at chunk boundaries. This is the same pattern used by `HighPassFilter` and `PeakingFilter`.

#### Why 80 Hz lower cutoff (not 100 Hz)?

The drone's fundamental motor frequency sits around 83–150 Hz depending on throttle. Using 80 Hz instead of 100 Hz gives the filter's roll-off region room to settle before the fundamental, avoiding attenuation of the target signal.

### 2.4 Windowing and Overlap

**Why windowing is necessary**

The STFT splits the signal into short time blocks and runs an FFT on each. If you feed a raw block of audio directly into an FFT, the sharp discontinuities at the edges of the block cause **spectral leakage** — energy from one frequency spills into adjacent bins. This makes narrowband tonal components (like drone motor harmonics) appear blurred across many bins.

A **window function** tapers the block to zero at both edges before the FFT, eliminating the discontinuity. The most common window for audio analysis is the **Hann window** (also called Hanning). It transitions smoothly from 0 at the start to 1.0 at the midpoint and back to 0 at the end.

**The cost: data loss at the edges**

The Hann window zeroes out the beginning and end of each time block. If blocks are processed back-to-back with no overlap, the parts of the signal near each block boundary are silenced and excluded from every FFT calculation. For a signal with transient events (like a drone at varying throttle), this means potentially missing real spectral content.

**The fix: overlapping blocks**

Overlap the time blocks so that the zero-weighted edges of one window fall on the midpoint (high-weight region) of the neighbouring window. At **50% overlap**, the Hann windows of adjacent blocks perfectly complement each other — every sample of the original signal contributes to at least one FFT calculation with non-negligible weight.

At **87.5% overlap** (`hop_length = nperseg / 8`), each sample contributes to many FFT calculations. This is useful when:

- The signal changes quickly (fast throttle sweeps on the drone).
- You need fine temporal resolution in the spectrogram output.
- You want more DOA estimates per second for a smoother tracking result.

The overlap percentage and the number of output frames per second are directly related:

```
frames_per_second = sample_rate / hop_length
```

For 8 kHz and 87.5% overlap with `nperseg=2048`: `hop_length = 256`, giving `8000 / 256 = 31.25 frames/second`.

**Visual example of 0% vs 50% overlap:**

```
0% overlap:
  [===block 1===]
                 [===block 2===]
                                [===block 3===]
  Gaps at edges of each block are zeroed out and never captured.

50% overlap:
  [===block 1===]
         [===block 2===]
                [===block 3===]
  Every sample is covered by at least one window's high-weight region.
```

*Source: "What is Overlap?" — Simcenter Testlab (Siemens), referenced in [§6](#6-sources)*

### 2.5 STFT and Cross-Chunk Buffering

**File:** `logic/stft_processor.py`

`scipy.signal.stft` is **stateless** — each call processes only the array it receives. It has no memory of previous calls. This means if audio arrives in chunks and you call `stft()` on each chunk independently, the overlap between consecutive chunks is zero at the chunk boundary, even if you specified `noverlap`.

`StftProcessor` solves this by maintaining an internal buffer:

1. On each incoming chunk, prepend the last `noverlap` samples from the previous chunk.
2. Run the STFT on the combined (buffered + current) data.
3. Save the last `noverlap` samples of the combined data as the buffer for the next chunk.

```
Chunk N-1:  [.........................................|tail_buffer]
Chunk N:                            [tail_buffer|...........................]
                                     ↑ prepended
Combined:   [tail_buffer|...........................]
STFT runs on the full combined array → overlap is continuous across boundary
```

Call `stft_processor.reset()` when starting a new audio file or session to discard the stale buffer.

**`scipy.signal.stft` is marked legacy** in recent scipy versions. The recommended replacement is `scipy.signal.ShortTimeFFT`. Migration is out of scope for now; `stft` works correctly with the buffering approach above.

### 2.6 Spectral Slicing

**File:** `logic/stft_slice_processor.py`

After the STFT, the output has `nperseg // 2 + 1 = 1025` frequency bins (0 Hz to 4 kHz for an 8 kHz sample rate). For spectrogram display, only the bins in the target band (100 Hz–1 kHz) are relevant — that's 231 bins out of 1025. Slicing reduces:

- Memory passed to the UI layer by ~78%.
- Render cost for the spectrogram widget.

The slice is computed using a boolean mask on the `freqs` array:

```python
mask = (freqs >= freq_min_hz) & (freqs <= freq_max_hz)
```

**Do not slice before DOA.** NormMUSIC selects its own frequency bins internally via the `freq_range` parameter and needs the full spectrum to construct the cross-spectral matrix.

### 2.7 DOA Estimation

**File:** `logic/doa_processor.py`

Direction-of-Arrival estimation uses the **NormMUSIC** algorithm from `pyroomacoustics`. It estimates the azimuth of a sound source from the phase relationships between microphone channels.

NormMUSIC expects input shaped `(n_mics, n_freqs, n_frames)` of **complex** STFT values — exactly the shape of `StftChunk.magnitudes`. The algorithm:

1. Computes the cross-spectral matrix between all microphone pairs at each frequency bin.
2. Decomposes it with an eigendecomposition (signal vs noise subspaces).
3. Sweeps candidate azimuths and scores each using the MUSIC pseudo-spectrum.
4. Normalises the pseudo-spectrum across frequency bins (the "Norm" in NormMUSIC) before averaging — this prevents strong low-frequency bins from drowning out high-frequency information.

**Critical parameter:** `nfft` in `DoaProcessor` must exactly match `nperseg` in `StftProcessor`. If they differ, the frequency-bin-to-Hz mapping is inconsistent and DOA results will be wrong.

**Spatial aliasing limit:** The microphone array has a maximum frequency beyond which it cannot correctly resolve the DOA (spatial aliasing). For this system:

| Ring | Diagonal | Aliasing limit |
|------|----------|----------------|
| Outer | 48 cm | ≤ 357 Hz |
| Inner | 21 cm | 400–808 Hz |

Set `freq_range` to a band that stays below the aliasing limit for the ring you are using.

### 2.8 DOA Smoothing

**File:** `logic/median_doa_processor.py`

Raw NormMUSIC output can jump by tens of degrees between frames when the signal-to-noise ratio is low. `MedianDoaProcessor` applies a **circular median** over a sliding window of recent azimuth estimates.

A circular (not linear) median is required because azimuth wraps at 360°: the median of [350°, 10°] should be 0°, not 180°. The implementation minimises the sum of circular arc distances to candidate angles.

---

## 3. Configuration for 7-Inch Drone Detection (100 Hz–1 kHz)

A 7-inch FPV drone (motors ~1300–1500 KV, 6S battery) at cruise/hover:

| Component | Frequency |
|-----------|-----------|
| Fundamental motor frequency | 83–150 Hz |
| Blade-pass frequency (3-blade prop × f₀) | 250–450 Hz |
| 1st harmonic | 500–900 Hz |
| 2nd harmonic | ~1 kHz |

These are narrowband tonal tracks that move as RPM changes. Maximum **frequency resolution** is needed to separate them from broadband background noise (wind, traffic).

### Recommended parameters

```python
# Preprocessing
ResampleProcessor(target_rate=8000)          # Nyquist = 4 kHz; tight bins in target band
DcOffsetFilter()                              # Remove ADC bias
BandpassFilter(80, 1200, sampling_rate=8000) # Kill wind rumble and out-of-band clutter

# STFT
StftProcessor(
    nperseg=2048,    # Δf = 8000/2048 ≈ 3.9 Hz — resolves individual motor tracks
    noverlap=1792,   # 87.5% overlap — smooth temporal tracking, continuity across chunks
    window='hann',   # Standard leakage suppression
)

# Visualisation branch
StftSliceProcessor(freq_min_hz=100, freq_max_hz=1000)  # 231 bins for display
LogScaleProcessor()                                      # dB scale for contrast

# DOA branch (receives unsliced StftChunk)
DoaProcessor(
    mic_locs=...,
    sampling_rate=8000,
    nfft=2048,                  # must match StftProcessor.nperseg
    freq_range=[100, 357],      # outer mic ring aliasing limit; use [400, 808] for inner ring
)
MedianDoaProcessor(window=5)
```

### Frequency resolution check

```
Δf = sample_rate / nperseg = 8000 / 2048 ≈ 3.9 Hz per bin
```

At 3.9 Hz resolution, the RPM micro-fluctuations between the front and rear motors as the drone pitches or turns are clearly resolved as separate spectral lines.

### Chunk size constraint

The source chunk size (in samples at the **original** sample rate) must be large enough that after resampling, the resulting chunk still exceeds `nperseg`:

```
chunk_size_orig ≥ nperseg × (orig_rate / target_rate)
chunk_size_orig ≥ 2048 × (44100 / 8000) ≈ 11 290
```

Use `chunk_size=32768` for comfortable headroom.

---

## 4. Wiring the Pipeline in Code

```python
import numpy as np
from logic.wav_loader import WavLoader
from logic.filters.dc_offset_filter import DcOffsetFilter
from logic.filters.bandpass_filter import BandpassFilter
from logic.resample_processor import ResampleProcessor
from logic.stft_processor import StftProcessor
from logic.stft_slice_processor import StftSliceProcessor
from logic.log_scale_processor import LogScaleProcessor
from logic.doa_processor import DoaProcessor
from logic.median_doa_processor import MedianDoaProcessor

MIC_LOCS = np.array([...])  # shape (3, n_mics) in metres

loader = WavLoader("recording.wav", chunk_size=32768)

audio = loader.stream()
audio = DcOffsetFilter().process(audio)
audio = ResampleProcessor(target_rate=8000).process(audio)
audio = BandpassFilter(80, 1200, sampling_rate=8000).process(audio)

stft_proc = StftProcessor(nperseg=2048, noverlap=1792, window='hann')
stft_chunks = stft_proc.process(audio)

# --- visualisation branch ---
display_chunks = StftSliceProcessor(100, 1000).process(stft_chunks)
display_chunks = LogScaleProcessor().process(display_chunks)

# --- DOA branch (must use unsliced stft_chunks) ---
doa_raw = DoaProcessor(
    mic_locs=MIC_LOCS,
    sampling_rate=8000,
    nfft=2048,
    freq_range=[100, 357],
).process(stft_chunks)
doa_smooth = MedianDoaProcessor(window=5).process(doa_raw)
```

> **Note:** In practice the two branches (`display_chunks` and `doa_raw`) both consume `stft_chunks`. Because Python generators are single-pass, you cannot iterate `stft_chunks` from two places simultaneously. Use `itertools.tee(stft_chunks, 2)` to split it, or drive a single loop that processes one `StftChunk` at a time and passes it to both branches manually.

---

## 5. Parameter Constraints and Gotchas

| Constraint | Detail |
|---|---|
| `DoaProcessor.nfft` == `StftProcessor.nperseg` | If they differ, frequency-bin-to-Hz mapping is wrong and DOA results are garbage. |
| `DoaProcessor.sampling_rate` must match post-resample rate | If resampling to 8 kHz, pass `sampling_rate=8000` to `DoaProcessor`. |
| DOA receives complex, full-spectrum `StftChunk` | Never pass sliced or dB-scaled chunks to `DoaProcessor`. |
| `chunk_size` must exceed `nperseg` after resampling | See formula in §3. Use `chunk_size=32768` at 44.1 kHz → 8 kHz. |
| Call `stft_proc.reset()` between sessions | Stale buffer from a previous file/stream will corrupt the first chunk of the next one. |
| `freq_range` bounded by array aliasing limit | Outer ring ≤ 357 Hz, inner ring 400–808 Hz. Setting a higher `freq_range` will produce incorrect azimuths. |
| `scipy.signal.stft` is marked legacy | Future refactor: migrate `StftProcessor` to `scipy.signal.ShortTimeFFT`. |

---

## 6. Sources

- **"What is Overlap?" — Simcenter Testlab (Siemens)**
  Explains overlap definition, Hanning window interaction, why 50% is the minimum for complete signal coverage, and the effect of overlap on stationary vs. tracked spectral analysis.
  Covers: spectral leakage, observation time, window functions, overlap percentage effects on averaged spectra.

- **AI consultation: "Best STFT pipeline for 7-inch drone detection (100–1 kHz)"**
  Derived the concrete parameter set for this use case: 8 kHz target rate, `nperseg=2048` for 3.9 Hz resolution, 87.5% overlap, Hann window, bandpass 80–1200 Hz, spectral slice 100–1000 Hz.
  Also motivated DC offset removal, pre-emphasis vs. bandpass choice for low-frequency targets, and dB log scaling for visualisation.

- **`scipy.signal.stft` documentation**
  [https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.stft.html](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.stft.html)
  Key notes: function is stateless (no cross-call buffering), legacy status, NOLA constraint for inversion, boundary extension behaviour.

- **pyroomacoustics NormMUSIC source**
  [https://github.com/LCAV/pyroomacoustics/blob/master/pyroomacoustics/doa/normmusic.py](https://github.com/LCAV/pyroomacoustics/blob/master/pyroomacoustics/doa/normmusic.py)
  Input shape: `(n_mics, n_freqs, n_frames)` complex. `freq_range` selects bins internally. `frequency_normalization=True` (default) averages pseudo-spectra across frequency before peak search.
