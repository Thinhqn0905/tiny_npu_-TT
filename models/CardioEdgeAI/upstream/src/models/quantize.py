"""Phase 5 — lightweight optimization: full-integer INT8 quantization.

Takes the Phase 4 two-branch CNN (signal + RR inputs) and produces:
1. `models/phase5_cnn_float.tflite` — float32 TFLite (conversion baseline)
2. `models/phase5_cnn_int8.tflite`  — full-integer INT8 (weights + activations)

Both are evaluated on DS2 with the TFLite interpreter so the accuracy cost
of quantization is measured with on-device-format inference, not a Keras
approximation. Size / accuracy deltas are appended to docs/results.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.config import MODELS_DIR  # noqa: E402
from src.evaluation.evaluate import evaluate, load_processed_dataset  # noqa: E402
from src.models.cnn import rr_feature_matrix  # noqa: E402

REPRESENTATIVE_BEATS = 2000


def representative_dataset(Xtr, RRtr, ytr_int=None):
    """Stratified (signal, rr) calibration pairs, all classes covered.

    A random subset is ~99 % N beats; calibrating on it leaves S/V
    activation ranges unmeasured, which measurably damaged the INT8
    accuracy of the oversampled v2 model (86 % before, see docs).
    """
    rng = np.random.default_rng(42)
    if ytr_int is None:
        idx = rng.choice(len(Xtr), REPRESENTATIVE_BEATS, replace=False)
    else:  # minority beats capped at 25% of the calibration set ...
        min_idx = np.where(ytr_int != 0)[0]
        cap = int(0.25 * REPRESENTATIVE_BEATS)
        if len(min_idx) > cap:
            min_idx = rng.choice(min_idx, cap, replace=False)
        idx = list(min_idx)
        idx.extend(rng.choice(np.where(ytr_int == 0)[0],
                              REPRESENTATIVE_BEATS - len(idx),
                              replace=False).tolist())
        idx = np.array(idx)
        rng.shuffle(idx)
    for i in idx:
        yield [Xtr[i:i + 1].astype(np.float32), RRtr[i:i + 1]]


def convert(model, Xtr, RRtr, ytr_int=None):
    # float32 TFLite
    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    float_tflite = conv.convert()

    # full-integer INT8 with int8 input/output tensors (edge-friendly)
    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = lambda: representative_dataset(
        Xtr, RRtr, ytr_int)
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    # legacy quantizer: the new one fails calibrating Conv1D graphs
    # (conv.cc "input->dims->size != 4"); the legacy path handles them.
    conv.experimental_new_quantizer = False
    int8_tflite = conv.convert()
    return float_tflite, int8_tflite


def tflite_predict(tflite_bytes: bytes, Xte, RRte) -> np.ndarray:
    """Run the interpreter over all test beats; handles int8 quantized IO."""
    interpreter = tf.lite.Interpreter(model_content=tflite_bytes,
                                      num_threads=2)
    interpreter.allocate_tensors()
    sig_in = interpreter.get_input_details()[0]
    rr_in = interpreter.get_input_details()[1]
    out = interpreter.get_output_details()[0]

    def q(details, value):
        # round-to-nearest, matching the firmware's lroundf path exactly
        if details["dtype"] == np.int8:
            scale, zero = details["quantization"]
            return (np.clip(np.round(value / (scale + 1e-12)) + zero,
                            -128, 127)).astype(np.int8)
        return value.astype(np.float32)

    preds = np.empty(len(Xte), dtype=np.int64)
    for i in range(len(Xte)):
        interpreter.set_tensor(
            sig_in["index"], q(sig_in, Xte[i:i + 1, :, None]))
        interpreter.set_tensor(rr_in["index"], q(rr_in, RRte[i:i + 1]))
        interpreter.invoke()
        preds[i] = np.argmax(interpreter.get_tensor(out["index"])[0])
    return preds


MODEL_KERAS = MODELS_DIR / "phase4_cnn.keras"  # production (v2 oversampled model is not PTQ-robust, see docs)
EVAL_TAG = "TFLite INT8 (quantized)"


def main() -> None:
    X, y, r, record, train_mask, test_mask = load_processed_dataset()
    classes = np.array(["N", "S", "V"])
    RR = rr_feature_matrix(r, record)
    Xtr, RRtr = X[train_mask], RR[train_mask]
    Xte, RRte = X[test_mask], RR[test_mask]

    model = tf.keras.models.load_model(MODEL_KERAS)
    print("converting ...")
    ytr_int = np.searchsorted(classes, y[train_mask])
    float_tflite, int8_tflite = convert(model, Xtr.astype(np.float32), RRtr,
                                        ytr_int)

    MODELS_DIR.mkdir(exist_ok=True)
    (MODELS_DIR / "phase5_cnn_float.tflite").write_bytes(float_tflite)
    (MODELS_DIR / "phase5_cnn_int8.tflite").write_bytes(int8_tflite)
    keras_kb = MODEL_KERAS.stat().st_size / 1024
    float_kb = len(float_tflite) / 1024
    int8_kb = len(int8_tflite) / 1024
    print(f"keras float32 : {keras_kb:8.1f} KB")
    print(f"tflite float32: {float_kb:8.1f} KB")
    print(f"tflite int8   : {int8_kb:8.1f} KB")

    results_path = Path(__file__).resolve().parents[2] / "docs" / "results.json"
    for name, blob in (("TFLite float32 (converted)", float_tflite),
                       ("TFLite INT8 (quantized)", int8_tflite)):
        pred = classes[tflite_predict(
            blob, Xte.astype(np.float32), RRte)]
        metrics = evaluate(name, y[test_mask], pred)

    results = json.loads(results_path.read_text(encoding="utf-8"))
    results["TFLite float32 (converted)"]["model_size_kb"] = round(float_kb)
    results["TFLite INT8 (quantized)"]["model_size_kb"] = round(int8_kb)
    results["TFLite INT8 (quantized)"]["compression_vs_keras"] = round(
        keras_kb / int8_kb, 1)
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("saved results ->", results_path)


if __name__ == "__main__":
    main()
