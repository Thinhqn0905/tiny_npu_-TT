/**
 * main_ecg_infer.c
 * Example Embedded C Application for Real-Time ECG Arrhythmia Inference.
 * Streams pre-trained INT8 weights and ECG sample windows to the 1x1 NPU.
 */

#include "npu_driver.h"
#include <stdio.h>

// Simulated low-level GPIO write/read functions
void npu_write_byte(uint8_t val);
uint8_t npu_read_byte(void);
void npu_set_ctrl(bool valid, bool cmd, bool weight, bool out_sel);
bool npu_wait_ready(void);

void npu_send_command(uint8_t cmd) {
    npu_wait_ready();
    npu_write_byte(cmd);
    npu_set_ctrl(true, true, false, false); // valid=1, cmd=1
    npu_set_ctrl(false, false, false, false);
}

void npu_send_pair(int8_t weight, int8_t activation) {
    npu_wait_ready();
    // Send Weight
    npu_write_byte((uint8_t)weight);
    npu_set_ctrl(true, false, true, false); // valid=1, cmd=0, weight=1
    // Send Activation
    npu_write_byte((uint8_t)activation);
    npu_set_ctrl(true, false, false, false); // valid=1, cmd=0, weight=0
    npu_set_ctrl(false, false, false, false);
}

/**
 * Classify a 16-sample ECG window:
 * Returns: 0 = Normal, 1 = PVC (Ventricular), 2 = PAC (Atrial)
 */
uint8_t npu_classify_ecg_heartbeat(const int8_t ecg_samples[16],
                                   const int8_t weights_l1[4][16],
                                   const int8_t weights_l2[3][4]) {
    uint8_t hidden_activations[4];

    // Configure Layer 1: Vector Length = 16, Shift = 6, ReLU Activation
    npu_send_command(NPU_CMD_SET_LEN(16));
    npu_send_command(NPU_CMD_SET_POST(6, NPU_ACT_RELU));

    // Run Layer 1: 4 Hidden Neurons
    for (int h = 0; h < 4; h++) {
        npu_send_command(NPU_CMD_ACC_CLEAR);
        for (int i = 0; i < 16; i++) {
            npu_send_pair(weights_l1[h][i], ecg_samples[i]);
        }
        // Read out ReLU activated byte
        npu_set_ctrl(false, false, false, false); // out_sel = 0 (Data)
        hidden_activations[h] = npu_read_byte();
    }

    // Configure Layer 2: Vector Length = 4, Shift = 6, Linear
    npu_send_command(NPU_CMD_ARGMAX_CLEAR);
    npu_send_command(NPU_CMD_SET_LEN(4));
    npu_send_command(NPU_CMD_SET_POST(6, NPU_ACT_LINEAR));

    // Run Layer 2: 3 Output Classes
    for (int c = 0; c < 3; c++) {
        npu_send_command(NPU_CMD_ACC_CLEAR);
        for (int h = 0; h < 4; h++) {
            npu_send_pair(weights_l2[c][h], (int8_t)hidden_activations[h]);
        }
        // Compare ArgMax for class c
        npu_send_command(NPU_CMD_ARGMAX_CMP(c));
    }

    // Read Winner-Take-All ArgMax Class
    npu_set_ctrl(false, false, false, true); // out_sel = 1 (ArgMax / Status)
    uint8_t status = npu_read_byte();
    uint8_t winning_class = status & 0x0F;

    return winning_class;
}
