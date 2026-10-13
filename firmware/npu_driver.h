/**
 * npu_driver.h
 * Microcontroller C Driver for Scalable 1x1 TinyML NPU (Tiny Tapeout)
 * Target: RP2040 / RP2350, STM32, ESP32, or any microcontroller GPIO
 */

#ifndef NPU_DRIVER_H
#define NPU_DRIVER_H

#include <stdint.h>
#include <stdbool.h>

// Pin mapping definitions on host MCU
typedef struct {
    uint8_t pin_data_in[8];   // Connected to ASIC ui_in[7:0]
    uint8_t pin_data_out[8];  // Connected to ASIC uo_out[7:0]
    uint8_t pin_host_valid;   // Connected to ASIC uio[0]
    uint8_t pin_npu_ready;    // Connected to ASIC uio[1]
    uint8_t pin_cmd_mode;     // Connected to ASIC uio[2]
    uint8_t pin_weight_str;   // Connected to ASIC uio[3]
    uint8_t pin_out_sel;      // Connected to ASIC uio[4]
    uint8_t pin_out_valid;    // Connected to ASIC uio[5]
    uint8_t pin_layer_done;   // Connected to ASIC uio[6]
    uint8_t pin_npu_busy;     // Connected to ASIC uio[7]
} npu_pins_t;

// Opcodes
#define NPU_CMD_SET_LEN(len)       ((uint8_t)(((0x00) | (((len) - 1) & 0x3F))))
#define NPU_CMD_SET_POST(shift, act) ((uint8_t)((0x40 | (((act) & 0x03) << 4) | ((shift) & 0x0F))))
#define NPU_CMD_ACC_CLEAR          (0x81)
#define NPU_CMD_ARGMAX_CLEAR       (0x82)
#define NPU_CMD_ARGMAX_CMP(cls)    ((uint8_t)(0x84 | (((cls) & 0x03) << 4)))

// Activation Modes
#define NPU_ACT_LINEAR             (0)
#define NPU_ACT_RELU               (1)
#define NPU_ACT_CLIP_SIGNED        (2)
#define NPU_ACT_CLIP_UNSIGNED      (3)

#endif // NPU_DRIVER_H
