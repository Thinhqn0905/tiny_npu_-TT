"""Preprocessing pipeline: filter -> R-peak -> beat segmentation -> dataset.

Produces `data/processed/mitbih_nsv.npz` with beat windows (N/S/V only),
their labels, record IDs and R-peak sample positions, split into the
inter-patient DS1 / DS2 sets defined in src.config.

Design decisions (documented in docs/PHASE2.md):
- Training data is segmented on the database's expert annotation R-peaks.
  Pan-Tompkins detection quality is measured separately (inference-time
  detector), never mixed into the gold-standard labels.
- Normalization is per-record z-score on the filtered signal, computed
  from the full record (not per beat), applied before windowing.
- Beats whose window crosses a record boundary are dropped.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import scipy.signal as sps
import wfdb

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.config import (AAMI_F, AAMI_N, AAMI_Q, AAMI_S, AAMI_V,  # noqa: E402
                        DATA_PROCESSED_DIR, DATA_RAW_DIR, FILTER_HIGH_HZ,
                        FILTER_LOW_HZ, FILTER_ORDER, MITDB_DS1,
                        MITDB_RECORDS, SAMPLING_RATE_HZ, WINDOW_AFTER_S,
                        WINDOW_BEFORE_S)

SYMBOL_TO_GROUP = {s: g for g, symbols in
                   (("N", AAMI_N), ("S", AAMI_S), ("V", AAMI_V),
                    ("F", AAMI_F), ("Q", AAMI_Q)) for s in symbols}

BEFORE = int(WINDOW_BEFORE_S * SAMPLING_RATE_HZ)   # 144 samples
AFTER = int(WINDOW_AFTER_S * SAMPLING_RATE_HZ)     # 216 samples


def bandpass(signal: np.ndarray, fs: int = SAMPLING_RATE_HZ) -> np.ndarray:
    """Zero-phase Butterworth bandpass: baseline removal + EMG/line noise."""
    sos = sps.butter(FILTER_ORDER, [FILTER_LOW_HZ, FILTER_HIGH_HZ],
                     btype="bandpass", fs=fs, output="sos")
    return sps.sosfiltfilt(sos, signal)


def load_record(record_id: str):
    """Return (filtered MLII signal, annotation samples, annotation symbols)."""
    rec = wfdb.rdrecord(str(DATA_RAW_DIR / record_id))
    ann = wfdb.rdann(str(DATA_RAW_DIR / record_id), "atr")
    # MLII is channel 0 on all MIT-BIH records that have it; records without
    # MLII fall back to channel 0 of whatever lead pair is present.
    signal = rec.p_signal[:, 0].astype(np.float64)
    return bandpass(signal), ann.sample, ann.symbol


def segment_beats(signal, ann_samples, ann_symbols, record_id):
    """Yield (beat_window, group, r_sample) triples for N/S/V beats.

    Per-record z-score normalization is applied here, using the full-record
    mean/std of the filtered signal.
    """
    mean, std = signal.mean(), signal.std()
    norm = (signal - mean) / (std + 1e-9)
    beats, groups, r_samples = [], [], []
    for r, sym in zip(ann_samples, ann_symbols):
        group = SYMBOL_TO_GROUP.get(sym)
        if group is None or group in ("F", "Q"):
            continue
        start, end = r - BEFORE, r + AFTER
        if start < 0 or end > len(norm):
            continue  # window crosses record boundary
        beats.append(norm[start:end])
        groups.append(group)
        r_samples.append(r)
    return beats, groups, r_samples, [record_id] * len(beats)


def build_dataset() -> Path:
    all_beats, all_groups, all_r, all_rec = [], [], [], []
    counts = {"N": 0, "S": 0, "V": 0}
    for record_id in MITDB_RECORDS:
        signal, samples, symbols = load_record(record_id)
        beats, groups, r_samples, recs = segment_beats(
            signal, samples, symbols, record_id)
        all_beats.extend(beats)
        all_groups.extend(groups)
        all_r.extend(r_samples)
        all_rec.extend(recs)
        for g in groups:
            counts[g] += 1

    X = np.asarray(all_beats, dtype=np.float32)
    y = np.asarray(all_groups)
    r = np.asarray(all_r, dtype=np.int64)
    rec = np.asarray(all_rec)

    ds1 = np.isin(rec, list(MITDB_DS1))
    out = DATA_PROCESSED_DIR / "mitbih_nsv.npz"
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out, X=X, y=y, r=r, record=rec,
        train_mask=ds1, test_mask=~ds1,
        classes=np.array(["N", "S", "V"]),
    )
    print(f"beats: {len(X)} | shape per beat: {X.shape[1]}")
    print(f"class counts: {counts}")
    print(f"DS1 (train): {int(ds1.sum())} beats | DS2 (test): {int((~ds1).sum())}")
    print(f"saved -> {out}")
    return out


def detect_r_peaks(signal: np.ndarray, fs: int = SAMPLING_RATE_HZ):
    """Inference-time R-peak detector (Pan-Tompkins via NeuroKit2).

    Used only for live/demo pipelines, not for building the gold-standard
    training set.
    """
    import neurokit2 as nk
    _, info = nk.ecg_peaks(signal, sampling_rate=fs, method="neurokit")
    return info["ECG_R_Peaks"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true",
                        help="rebuild the processed dataset (default action)")
    build_dataset()
