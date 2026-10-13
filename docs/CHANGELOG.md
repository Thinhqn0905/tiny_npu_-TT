# Unreleased front-end review

- Correct wrapper ready backpressure and widened rounding addition.
- Add independent arithmetic/protocol tests and preserve negative controls.
- Replace hardcoded PPA output with reproducible generic/mapped synthesis
  and explicit pre-layout STA evidence; retain original packages.
- Update planning allocation to user-approved2x2 and remove ena false path.
- Download/hash a public trained ECG INT8 checkpoint and copy/hash local
  MIT-BIH files; keep software CNN benchmark distinct from trained-MLP RTL E2E.
- Reconcile architecture, interface, benchmark and machine-readable reports.
- Record actual human approvals, measured coverage and complete trained-MLP
  RTL evidence; final human Gate5 is approved.
