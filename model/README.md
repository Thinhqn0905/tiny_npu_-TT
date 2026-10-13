# Historical model utility

`ecg_tinyml_model.py` constructs analytic synthetic templates; it does not
load trained weights. Its original unsigned hidden values are incompatible
with the production signed-output contract. It is retained as historical
reference only. Real downloaded and locally trained model artifacts are
kept under models/, with source/training provenance and distinct benchmarks.
