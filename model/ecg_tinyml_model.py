"""
ecg_tinyml_model.py
TinyML ECG Arrhythmia Classifier and INT8 Quantization Flow.
Generates synthetic MIT-BIH style ECG signals, computes quantized integer
weights/activations, and outputs bit-exact golden test vectors for NPU verification.
"""

import json
import math
import os


def generate_ecg_beat(beat_type="normal", num_samples=16):
    """
    Generate a normalized synthetic 1-beat ECG wave.
    beat_type:
      'normal' (Class 0): Classic sharp QRS complex
      'pvc'    (Class 1): Wide, inverted ventricular contraction
      'pac'    (Class 2): High-frequency notched P-wave / contraction
    Returns integer values in range [-100, 100].
    """
    samples = []
    for i in range(num_samples):
        t = (i - num_samples / 2) / (num_samples / 4)
        if beat_type == "normal":
            # Sharp positive R peak with slight negative S wave
            val = math.exp(-2.5 * t * t) * 80.0 - math.exp(-4.0 * (t - 0.7) ** 2) * 20.0
        elif beat_type == "pvc":
            # Broad inverted QRS complex
            val = -math.exp(-0.8 * t * t) * 75.0 + math.exp(-1.5 * (t - 1.0) ** 2) * 15.0
        else:  # 'pac'
            # Dual small peaks
            val = (
                math.exp(-3.0 * (t + 0.5) ** 2) * 45.0
                + math.exp(-3.0 * (t - 0.5) ** 2) * 55.0
            )
        samples.append(int(round(max(-128, min(127, val)))))
    return samples


def create_trained_quantized_weights():
    """
    Construct pre-trained INT8 template weights for 16-input -> 4 hidden -> 3 classes.
    """
    # Layer 1: 4 filters / neurons, each 16 weights (signed 8-bit)
    # Filter 0: Matches sharp R peak (Normal)
    # Filter 1: Matches broad negative deflection (PVC)
    # Filter 2: Matches dual notch (PAC)
    # Filter 3: General baseline detector
    w_l1 = []
    for f in range(4):
        weights = []
        for i in range(16):
            t = (i - 8) / 4.0
            if f == 0:
                w = math.exp(-2.5 * t * t) * 60.0 - 10.0
            elif f == 1:
                w = -math.exp(-0.8 * t * t) * 50.0 + 10.0
            elif f == 2:
                w = math.sin(t * 3.14) * 45.0
            else:
                w = 15.0 if (i % 2 == 0) else -15.0
            weights.append(int(round(max(-128, min(127, w)))))
        w_l1.append(weights)

    # Layer 2: 3 output classes, 4 weights each (from 4 hidden activations)
    w_l2 = [
        [60, -40, -20, 10],  # Class 0 (Normal): Strong weight on filter 0
        [-50, 70, -30, -10],  # Class 1 (PVC): Strong weight on filter 1
        [-20, -30, 65, 15],  # Class 2 (PAC): Strong weight on filter 2
    ]

    return w_l1, w_l2


def simulate_npu_inference(samples, w_l1, w_l2, l1_shift=6, l2_shift=6):
    """
    Bit-exact software model matching the NPU hardware datapath.
    """
    # Layer 1: 16 inputs -> 4 hidden activations with ReLU & arithmetic right shift
    hidden_acts = []
    for f in range(4):
        acc = 0
        for i in range(16):
            acc += samples[i] * w_l1[f][i]
        # Rounding + shift
        round_offset = 1 << (l1_shift - 1) if l1_shift > 0 else 0
        shifted = (acc + round_offset) >> l1_shift
        # ReLU + 8-bit saturation [0, 255]
        relu_val = max(0, min(255, shifted))
        hidden_acts.append(relu_val)

    # Layer 2: 4 hidden inputs -> 3 classes
    class_scores = []
    for c in range(3):
        acc = 0
        for h in range(4):
            acc += hidden_acts[h] * w_l2[c][h]
        class_scores.append(acc)

    # ArgMax
    best_class = 0
    best_score = class_scores[0]
    for c in range(1, 3):
        if class_scores[c] > best_score:
            best_score = class_scores[c]
            best_class = c

    return hidden_acts, class_scores, best_class


def export_test_vectors(output_path="test/golden_ecg_test.json"):
    w_l1, w_l2 = create_trained_quantized_weights()

    test_cases = []
    for beat_name, expected_class in [
        ("normal", 0),
        ("pvc", 1),
        ("pac", 2),
    ]:
        samples = generate_ecg_beat(beat_name, num_samples=16)
        hidden_acts, class_scores, pred_class = simulate_npu_inference(
            samples, w_l1, w_l2
        )
        assert (
            pred_class == expected_class
        ), f"Mismatch for {beat_name}: pred {pred_class} vs exp {expected_class}"

        test_cases.append(
            {
                "beat_type": beat_name,
                "input_samples": samples,
                "expected_class": expected_class,
                "hidden_acts": hidden_acts,
                "class_scores": class_scores,
            }
        )

    export_data = {
        "model_architecture": "16 -> 4 (ReLU) -> 3 (ArgMax)",
        "l1_shift": 6,
        "l2_shift": 6,
        "weights_layer1": w_l1,
        "weights_layer2": w_l2,
        "test_cases": test_cases,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2)
    print(f"Exported golden test vectors to {output_path}")


if __name__ == "__main__":
    export_test_vectors()
