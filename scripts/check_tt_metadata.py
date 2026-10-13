"""Fail-closed TinyTapeout metadata/docs check using pinned official tools."""
import argparse,json,sys
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument('--tools',type=Path,required=True); a=ap.parse_args()
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.tools))
import yaml
from project_checks import check_project_docs
from project_info import ProjectInfo
from front_end_reports import files
meta=yaml.safe_load((root/'info.yaml').read_text())
tiles=yaml.safe_load((a.tools/'tech/ihp-sg13g2/tile_sizes.yaml').read_text())
ProjectInfo(meta,tiles,require_pinout=True) # unlike wrapper helper, arbitrary exceptions cannot pass
assert meta['project']['top_module']=='tt_um_tinyml_npu_2x2'
assert meta['project']['clock_hz']==50000000 and meta['project']['tiles']=='2x2'
assert meta['project']['source_files']==[p.name for p in files()]
assert all(p.read_bytes()==(root/'src'/p.name).read_bytes() for p in files())
check_project_docs(str(root),'ihp-sg13g2')
head=(a.tools/'.git/HEAD').read_text().strip()
if head.startswith('ref:'):
    ref=a.tools/'.git'/head.split(': ',1)[1]
    if ref.exists(): head=ref.read_text().strip()
print('Official support tools HEAD:',head)
print('PASS: top/source ordering/clock/tiles/pinout match; full physical integration NOT VERIFIED')
