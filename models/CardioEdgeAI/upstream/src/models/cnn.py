"""Phase 4 — 1D CNN baseline: morphology branch + RR-timing branch.

Pure-morphology CNNs cannot separate S from N inter-patient (verified in
a first tuning round: S recall <= 0.31 with morphology only) because
supraventricular ectopy is defined by *premature timing*, not shape.
This model therefore takes two inputs:

  1. beat window (360, 1)  -> 3 conv blocks -> GAP
  2. 4 RR-timing scalars   ------------------^  -> concat -> dense head

RR features are normalized with fixed physiological constants
(mean RR 0.8 s, std 0.3 s) instead of dataset statistics, so the exact
same features can be computed on an ESP32 at inference time.

Input features (all computed the same way in deploy/esp32 firmware):
  pre_rr, post_rr, local_rr (mean of 5 preceding), pre_rr / local_rr
  post-RR needs the next beat -> one-beat latency (documented in thesis).
"""
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.config import MODELS_DIR, SAMPLING_RATE_HZ, SEED  # noqa: E402
from src.evaluation.evaluate import evaluate, load_processed_dataset  # noqa: E402

# Records held out of training for early stopping (patient-separated).
VAL_RECORDS = ("215", "220", "223", "230")
EPOCHS = 25
PATIENCE = 8
BATCH = 256
RR_MEAN_S, RR_STD_S = 0.8, 0.3  # fixed physiological normalization


def rr_feature_matrix(r: np.ndarray, record: np.ndarray) -> np.ndarray:
    """(n_beats, 4) RR features with fixed normalization; per record."""
    n = len(r)
    feats = np.zeros((n, 4), dtype=np.float32)
    for rec in np.unique(record):
        idx = np.where(record == rec)[0]
        rr = np.diff(r[idx]) / SAMPLING_RATE_HZ  # RR in seconds
        for k, i in enumerate(idx):
            pre = rr[k - 1] if k >= 1 else (rr[0] if len(rr) else RR_MEAN_S)
            post = rr[k] if k < len(rr) else pre
            local = (np.mean(rr[max(0, k - 5):k]) if k >= 1 else pre)
            feats[i] = [(pre - RR_MEAN_S) / RR_STD_S,
                        (post - RR_MEAN_S) / RR_STD_S,
                        (local - RR_MEAN_S) / RR_STD_S,
                        (pre / local - 1.0) / RR_STD_S if local > 0 else 0.0]
    return feats


def build_cnn(n_classes: int = 3) -> tf.keras.Model:
    """~13k-parameter two-branch CNN (morphology + RR timing).

    The morphology branch uses Conv2D with (1, k) kernels on a
    (batch, 1, time, 1) tensor instead of Conv1D: mathematically
    identical, but TFLite's full-integer quantizer can only calibrate
    CONV_2D from a 4D input tensor (Phase 5), so the graph is built
    quantization-friendly from the start.
    """
    sig_in = tf.keras.Input(shape=(360, 1))
    x = tf.keras.layers.Reshape((1, 360, 1))(sig_in)
    x = tf.keras.layers.Conv2D(16, (1, 7), padding="same",
                               use_bias=False)(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.ReLU()(x)
    x = tf.keras.layers.MaxPooling2D((1, 2))(x)
    x = tf.keras.layers.Conv2D(32, (1, 5), padding="same",
                               use_bias=False)(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.ReLU()(x)
    x = tf.keras.layers.MaxPooling2D((1, 2))(x)
    x = tf.keras.layers.Conv2D(64, (1, 3), padding="same",
                               use_bias=False)(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.ReLU()(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)

    rr_in = tf.keras.Input(shape=(4,))
    h = tf.keras.layers.Concatenate()([x, rr_in])
    h = tf.keras.layers.Dense(32, activation="relu")(h)
    h = tf.keras.layers.Dropout(0.3)(h)
    out = tf.keras.layers.Dense(n_classes, activation="softmax")(h)

    model = tf.keras.Model([sig_in, rr_in], out)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main() -> None:
    tf.keras.utils.set_random_seed(SEED)
    X, y, r, record, train_mask, test_mask = load_processed_dataset()
    classes = np.array(["N", "S", "V"])
    y_int = np.searchsorted(classes, y)
    RR = rr_feature_matrix(r, record)

    val_mask = train_mask & np.isin(record, VAL_RECORDS)
    fit_mask = train_mask & ~np.isin(record, VAL_RECORDS)
    split = lambda m: (X[m, :, None], RR[m])
    Xtr, ytr = split(fit_mask), y_int[fit_mask]
    Xva, yva = split(val_mask), y_int[val_mask]
    Xte, yte = split(test_mask), y_int[test_mask]
    print(f"train {len(ytr)} | val {len(yva)} | test {len(yte)} beats")

    # Tuned on DS1 validation over three rounds: full 'balanced' weights
    # collapse N precision, sqrt weights under-emphasize S. This hand-tuned
    # compromise maximized validation macro-F1.
    cw = {0: 0.6, 1: 8.0, 2: 2.0}

    model = build_cnn()
    model.summary()
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy", patience=PATIENCE,
            restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=4),
    ]
    model.fit(list(Xtr), ytr, validation_data=(list(Xva), yva),
              epochs=EPOCHS, batch_size=BATCH, class_weight=cw,
              callbacks=callbacks, verbose=2)

    MODELS_DIR.mkdir(exist_ok=True)
    model.save(MODELS_DIR / "phase4_cnn.keras")
    n_params = model.count_params()
    size_kb = (MODELS_DIR / "phase4_cnn.keras").stat().st_size / 1024
    print(f"parameters: {n_params} | keras file: {size_kb:.0f} KB")

    pred = classes[np.argmax(model.predict(list(Xte), verbose=0), axis=1)]
    metrics = evaluate("1D CNN + RR (14k params)", y[test_mask], pred)
    metrics.update({"parameters": n_params, "model_size_kb": round(size_kb)})
    import json
    results_path = Path(__file__).resolve().parents[2] / "docs" / "results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    results["1D CNN + RR (14k params)"] = metrics
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
