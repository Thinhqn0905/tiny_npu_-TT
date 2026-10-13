# Configuration boundary

`config.json` is a design overlay for the TinyTapeout IHP flow, with paths
relative to this directory. Invoke the official flow with PDK `ihp-sg13g2`
and its `sg13g2_stdcell` profile. The flow must supply official power nets,
pin placement, PDN and shuttle defaults. This overlay has not been hardened.

The user approved planning allocation `2x2` on 2026-10-13. The bounding box
is 419.52 x 313.74 um in the pinned official support-tools profile
01d5d2814fa9dd61e9d211e0b235a4a592a9316a. This is not a routed fit claim.

The Liberty file is from IHP Open PDK, with its Apache 2.0 notices intact.
`library_provenance.json` records the upstream revision and URL. It is used
for a reproducible typical-corner front-end synthesis/STA diagnostic, not
as a replacement for the shuttle's pinned signoff PDK/corners.
