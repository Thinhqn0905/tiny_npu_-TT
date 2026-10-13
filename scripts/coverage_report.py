"""Parse actual Verilator coverage points; never exclude a DUT point silently."""
import json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/coverage/baseline'
out=ROOT/'evidence/review/coverage'
files={(ROOT/'pnr_handoff'/line.strip()).relative_to(ROOT).as_posix() for line in
       (ROOT/'pnr_handoff/filelist.f').read_text().splitlines() if line.strip() and not line.startswith('#')}
points=[]
for line in (work/'merged.dat').read_text().splitlines():
    match=re.fullmatch(r"C '(.*)' (\d+)",line)
    if not match: continue
    fields=dict(part.split('\x02',1) for part in match[1].split('\x01') if '\x02' in part)
    if fields.get('f') not in files: continue
    points.append(dict(fields,count=int(match[2])))
metrics={}
for metric in sorted({p['page'].split('/')[0] for p in points}):
    selected=[p for p in points if p['page'].split('/')[0]==metric]
    covered=sum(p['count']>0 for p in selected)
    metrics[metric]=dict(covered=covered,coverable=len(selected),percent=100*covered/len(selected),
                         uncovered=[p for p in selected if p['count']==0])
assert metrics and 'PASS TC-COVERAGE-BASE' in (out/'run.log').read_text()
ledger=json.loads((ROOT/'schemas/review_approvals.json').read_text(encoding='utf-8-sig'))
reviewed=ledger.get('coverage_exclusions',{}).get('approved',False)
eligible={}
if reviewed:
    # Match exactly the reviewed points, not every point with a zero count.
    expected_line={('tt_um_tinyml_npu_2x2.v','139','case'),('tt_um_tinyml_npu_2x2.v','163','case'),('tt_um_tinyml_npu_2x2.v','187','case')}
    expected_toggle={('npu_activation.v','30',f'round_offset[{b}]') for b in range(15,25)}
    expected_toggle.add(('npu_top_2x2.v','42','out_acc_sel'))
    expected_toggle|={('tt_um_tinyml_npu_2x2.v',line,f'{name}[{bit}]') for line,name,bits in
        [('18','uio_out',[0,2,3,4]),('19','uio_oe',[0,2,3,4]),('70','cfg_vector_len',[7]),('71','mac_count',[6,7])] for bit in bits}
    for metric,expected in [('v_line',expected_line),('v_toggle',expected_toggle),('v_branch',set())]:
        actual={(Path(p['f']).name,p['l'],p['o']) for p in metrics[metric]['uncovered']}
        assert actual==expected,(metric,actual^expected)
        eligible[metric]=dict(covered=metrics[metric]['covered'],coverable=metrics[metric]['coverable']-len(expected),percent=100.0,excluded=len(expected))
report=dict(status='target_met' if all(v['percent']==100 for v in metrics.values()) else 'target_unmet',
    tool='Verilator 4.038',scope=sorted(files),aggregation='Verilator merged hierarchical points (h field retained)',
    exclusions=['testbench','SVA'],dut_exclusions=[],target_percent=100,metrics=metrics,
    branch_metric='v_branch: native Verilator branch points; denominator retained separately from v_line and v_toggle',
    functional_checks='PASS TC-COVERAGE-BASE; public-pin integer oracle',
    raw_database='evidence/review/coverage/merged.dat')
if reviewed:
    report.update(status='target_met',eligible_metrics=eligible,
        dut_exclusions='25 exact points approved by user; docs/COVERAGE_REVIEW.md and schemas/review_approvals.json')
for name in ['coverage.dat','merged.dat','coverage.info']: shutil.copyfile(work/name,out/name)
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:{a:b for a,b in v.items() if a!='uncovered'} for k,v in metrics.items()},indent=2))
