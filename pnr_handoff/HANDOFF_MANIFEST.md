# PnR handoff manifest

Status: READY FOR PNR; see docs/FRONTEND_SIGNOFF_REVIEW.md.
Top tt_um_tinyml_npu_2x2; IHP planning2x2; target20ns. Author: Thinh Pham.
Initial commit d020f70630e1c9feacf9fd79206d7a9e2874afed; resumed editor base c0ef2520c1a76f5730e6c716403ca77bc42194e9.
Hashes identify the reviewed package bytes; Git records the release commit identity.
This manifest excludes itself to avoid circular self-hashing. All other package files are included.

| Relative path | Bytes | SHA-256 |
|---|---:|---|
| `config/README.md` | 836 | `164fdda0f7ed2b7be3b9b0d210e1a8418ba94451912cdab6ea28b3bf9e71e40d` |
| `config/config.json` | 474 | `fb394038387929e9011bf6ef5ecedeb103d401caa8e02b23521fd28bac183b89` |
| `config/info.yaml` | 1653 | `db615083cca8829b41a4be1328ea555d770512a0ba2145f4ac4e7365f3c90383` |
| `config/library_provenance.json` | 283 | `db056534da2603ad19e7be216e7a5cc39b1662c823b02f2000bbb5fca8482858` |
| `config/sg13g2_stdcell_typ_1p20V_25C.lib` | 1720231 | `7677a8918689f452e80405ad16a83e744709342574f2aedcc507c2758986b396` |
| `constraints/design.sdc` | 3370 | `cf9db0b9863e91a9ff235711a5782c1f67e1cb4d663434a7d33406da3160f015` |
| `docs/FRONTEND_SIGNOFF_REVIEW.md` | 15031 | `dd55bbf052aaf3d7341027d723419ab6a27de5282ce53cf91b1ded78c71ec11b` |
| `docs/FRONTEND_SPEC.md` | 3047 | `9cfe27f5f07b462b0314d83513389ae83f5bed2b9c8b2234773fa869c87c3ff3` |
| `docs/LICENSE` | 11558 | `1eb85fc97224598dad1852b5d6483bbcf0aa8608790dcc657a5a2a761ae9c8c6` |
| `docs/PNR_INTERFACE.md` | 2584 | `c892d630a9bc4133225fd720982a8c1d13a95ca458b458edc9adb0cac80c0364` |
| `docs/RTL_FREEZE.md` | 3612 | `34c3edf4bcc84f2f7670a4823fece2a49e25659402ee8dc7c5a3ea4cfeb43274` |
| `filelist.f` | 218 | `cfe2b49306ed8a92d3197981ea171d18523555348c06741b72780ac707b06533` |
| `reports/cell_count.rpt` | 207 | `a10317a492d69b06b5990406b7e31427598ed30b1957fa611a6682b52f326c47` |
| `reports/elaborated.json` | 210477 | `57ecc2dcf55a274e244f9e5c0e25051cc9bc0da42c0a2822d62ee2d04b99dd24` |
| `reports/generic.json` | 1390162 | `c6df5c11616702a39c24f49b6bf58d6747c72214db84bc1c7369c161ae96891b` |
| `reports/generic.ys` | 427 | `b181252748a9864436711f410763b7d9d3e4b765450d67b12bdb30bd8ae0c00d` |
| `reports/latch_check.rpt` | 89 | `2065ccb806532e1a5c71fe80f2968ab97c885e685374ede37fea28f6853f8dfa` |
| `reports/mapped.json` | 2653342 | `8a40e87b7c949759ab3ddb3845c28b16f7d63bd6db468bb7b9bff0eae3c13287` |
| `reports/mapped.ys` | 581 | `ba70c6b30c876cc6562f4a85c13ee5f0a960820227339ee0df859c793899dbe0` |
| `reports/mapped_netlist.v` | 487389 | `a694142502aef32776a310b3e1ab383fde3deea6c92b5010801e911a1bb6a29a` |
| `reports/sequential_dff.rpt` | 313 | `f5233a0d4c9454045ffc41f2e4c103c592e568e67cb0f1ed9fe9db12686ca8c0` |
| `reports/summary.json` | 2196 | `adbe208adde71a94a4a7f8be237522e99f90f93d3cbffc6995384d4b50323a45` |
| `reports/synth_netlist.v` | 153039 | `f707eb6fdc4a2957b6666b75dfda38c7b84b81f3b1cc52196db2cbd4cfb98749` |
| `reports/synth_stat.rpt` | 2196 | `adbe208adde71a94a4a7f8be237522e99f90f93d3cbffc6995384d4b50323a45` |
| `reports/timing.tcl` | 402 | `fe828f71a69f9b27694911c77c5ca98cf942336b9d87cb820828216745ae88eb` |
| `reports/timing_est.rpt` | 29946 | `005b0a572cf886ce52fd8287d1810fef5bc201db3874d31f75921946b0e5a381` |
| `reports/timing_summary.json` | 878 | `d53f2e8f78a3b20a9acf237c487755e69bec6d37c05f30eae32b0ddbcc637ae3` |
| `reports/yosys_mapped.log` | 115918 | `20f001e67d1c43f4d76d9eed0475149cbe425b23cda52716d6d2f42dc3a1f3c0` |
| `reports/yosys_synth.log` | 101795 | `e7d0b4a6c58673277158657a75fdda1b3dd8dad990f027cf7764dc907d17c36f` |
| `rtl/npu_activation.v` | 3470 | `8395b1f24cbbc30f5d6f711aa1250a0af62af08dc41c6e65af967a0e79fa1f46` |
| `rtl/npu_array.v` | 4990 | `a2b517285ccdbd3dfe68d95ab035ec67d51a1099e3db6dd73f1cd3ece43e7eb6` |
| `rtl/npu_pe.v` | 3166 | `cc50d98c113715a54a14c8bb4377e6a49b7e4524f9143e6e9f1d512d7e8b431d` |
| `rtl/npu_top_2x2.v` | 5644 | `30ec1c2a42d013d073dcfa043f3785a1ceca8f313235e4346f448c1a17f43aef` |
| `rtl/tt_um_tinyml_npu_2x2.v` | 10142 | `c6c0f1ece572aad545b298d74ccee3ae7d0734c98fa002483f9194754f3e1fd2` |
