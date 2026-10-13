"""Central configuration for CardioEdgeAI.

Fixed task/data decisions for version 1, following the research plan:
MIT-BIH Arrhythmia Database, MLII lead, native 360 Hz (no resampling),
R-peak-centered windows (0.4 s before / 0.6 s after), AAMI N/S/V beat
groups. F and Q beats are excluded from v1 training and evaluation and
are reported as out of scope.
"""

# --- Signal ---
SAMPLING_RATE_HZ = 360
WINDOW_BEFORE_S = 0.4
WINDOW_AFTER_S = 0.6
# Window length in samples: 0.4 + 0.6 = 1.0 s -> 360 samples per beat
WINDOW_SAMPLES = int((WINDOW_BEFORE_S + WINDOW_AFTER_S) * SAMPLING_RATE_HZ)

# --- Bandpass filter (used by the preprocessing pipeline) ---
FILTER_LOW_HZ = 0.5   # remove baseline wander
FILTER_HIGH_HZ = 40.0 # keep QRS content, attenuate muscle/EMG noise
FILTER_ORDER = 4

# --- MIT-BIH Arrhythmia Database ---
# https://physionet.org/content/mitdb/1.0.0/
MITDB_RECORDS = (
    "100", "101", "102", "103", "104", "105", "106", "107", "108", "109",
    "111", "112", "113", "114", "115", "116", "117", "118", "119", "121",
    "122", "123", "124", "200", "201", "202", "203", "205", "207", "208",
    "209", "210", "212", "213", "214", "215", "217", "219", "220", "221",
    "222", "223", "228", "230", "231", "232", "233", "234",
)

# Standard inter-patient split (de Chazal & Camps-style). No record's
# patient appears in both sets.
MITDB_DS1 = ("101", "106", "108", "109", "112", "114", "115", "116",
             "118", "119", "122", "124", "201", "203", "205", "207",
             "208", "209", "215", "220", "223", "230")
MITDB_DS2 = ("100", "103", "105", "111", "113", "117", "121", "123",
             "200", "202", "210", "212", "213", "214", "219", "221",
             "222", "228", "231", "232", "233", "234")

# --- AAMI beat grouping (MIT-BIH annotation symbols) ---
# v1 targets N / S / V only; F and Q are excluded.
AAMI_N = ("N", "L", "R", "e", "j")
AAMI_S = ("A", "a", "J", "S")
AAMI_V = ("V", "E")
AAMI_F = ("F",)           # excluded in v1
AAMI_Q = ("/", "f", "Q")  # excluded in v1

CLASSES = ("N", "S", "V")

# --- Paths (relative to the repository root) ---
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_RAW_DIR = REPO_ROOT / "data" / "raw" / "mitdb"
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MODELS_DIR = REPO_ROOT / "models"

# Random seed for every experiment, so results are reproducible.
SEED = 42
