"""Artifact preparation and evidence parsing only. All EDA calls live in Makefile."""
import argparse, collections, hashlib, json, re, shutil, sys, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
H=ROOT/'pnr_handoff'
TOP='tt_um_tinyml_npu_2x2'
def read(p): return json.loads(p.read_text())
def dump(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2)+'\n')
def files():
    lines=[l.strip() for l in (H/'filelist.f').read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    assert len(lines)==len(set(lines))==5
    ps=[H/l for l in lines]
    assert all(p.is_file() and p.resolve().is_relative_to(H) for p in ps)
    return ps
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare():
    out=ROOT/'evidence/review/final'; out.mkdir(parents=True,exist_ok=True)
    ps=files()
    assert all(p.read_bytes()==(ROOT/'src'/p.name).read_bytes() for p in ps)
    meta=read(H/'config/config.json')
    assert meta['DESIGN_NAME']==TOP and meta['CLOCK_PERIOD']==20
    assert meta['DIE_AREA']==[0,0,419.52,313.74]
    for value in meta['VERILOG_FILES']+[meta['PNR_SDC_FILE']]:
        assert (H/'config'/value.removeprefix('dir::')).resolve().is_file(),value
    dump(out/'run_identity.json',dict(starting_commit='d020f70630e1c9feacf9fd79206d7a9e2874afed',
        resumed_base_commit='c0ef2520c1a76f5730e6c716403ca77bc42194e9',seed=784736294,
        parameters=dict(ROWS=2,COLS=2,DATA_WIDTH=8,ACC_WIDTH=24,SYSTOLIC_MODE=0),
        platform='ihp-sg13g2',tiles='2x2',clock_period_ns=20,
        rtl_sha256={str(p.relative_to(ROOT)):sha(p) for p in ps},
        config_sha256=sha(H/'config/config.json'),sdc_sha256=sha(H/'constraints/design.sdc')))
    # Legacy test source recovered from the immutable original archive.
    legacy=ROOT/'test/legacy'; legacy.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT/'evidence/history/d020f70_original.zip') as z:
        (legacy/'tb.v').write_bytes(z.read('test/tb.v'))
        (legacy/'test_legacy.py').write_text(z.read('test/test.py').decode().replace('units=','unit='))
    prefix='\n'.join('read_verilog '+str(p.relative_to(H)) for p in ps)+'\n'
    (H/'reports/generic.ys').write_text(prefix+f'hierarchy -check -top {TOP}\nproc\nopt\n'
        'write_json reports/elaborated.json\n'+f'synth -top {TOP}\ncheck -assert\n'
        'select -assert-none t:$dlatch t:$_DLATCH_* t:$mem*\nstat\n'
        'write_json reports/generic.json\nwrite_verilog -noattr reports/synth_netlist.v\n')
    lib='config/sg13g2_stdcell_typ_1p20V_25C.lib'
    (H/'reports/mapped.ys').write_text('read_liberty -lib '+lib+'\n'+prefix+
        f'hierarchy -check -top {TOP}\nsynth -top {TOP} -noabc -flatten\n'+
        'dfflibmap -liberty '+lib+'\nabc -liberty '+lib+'\nclean\ncheck -assert\n'+
        'stat -liberty '+lib+'\nwrite_json reports/mapped.json\nwrite_verilog -noattr -noexpr reports/mapped_netlist.v\n')
    (H/'reports/timing.tcl').write_text('# Run from pnr_handoff/reports.\nset here [pwd]\n'
        'read_liberty $here/../config/sg13g2_stdcell_typ_1p20V_25C.lib\n'
        'read_verilog $here/mapped_netlist.v\n'+f'link_design {TOP}\n'
        'read_sdc $here/../constraints/design.sdc\n'
        'report_checks -path_delay max -group_count 5 -format full_clock_expanded -digits 4\n'
        'report_checks -path_delay min -group_count 5 -digits 4\n'
        'report_worst_slack\ncheck_setup -verbose\nexit\n')
def synth_report():
    data=read(H/'reports/generic.json')
    def count(m):
        result=collections.Counter()
        for c in data['modules'][m]['cells'].values():
            result.update(count(c['type']) if c['type'] in data['modules'] else {c['type']:1})
        return result
    cells=count(TOP); seq=sum(n for t,n in cells.items() if 'DFF' in t.upper())
    assert all(t.startswith('$_') and 'LATCH' not in t.upper() and 'MEM' not in t.upper() for t in cells)
    md=read(H/'reports/mapped.json'); mc=collections.Counter(c['type'] for c in md['modules'][TOP]['cells'].values())
    assert all(t.startswith('sg13g2_') and 'sdf' not in t for t in mc)
    log=(H/'reports/yosys_mapped.log').read_text()
    glog=(H/'reports/yosys_synth.log').read_text()
    assert 'found and reported 0 problems.' in log.lower() and 'found and reported 0 problems.' in glog.lower()
    warnings=sorted(set(l for l in log.splitlines() if l.startswith('Warning:')))
    assert all("unsupported expression 'SCE*SCD+!SCE*D'" in l for l in warnings),warnings
    seqmapped=sum(n for t,n in mc.items() if 'dfr' in t or 'dff' in t)
    summary=dict(tool='Yosys 0.9 (git sha1 1979e0b)',top=TOP,status='PASS',
        generic_primitives=sum(cells.values()),sequential_bits=seq,
        combinational_primitives=sum(cells.values())-seq,generic_cell_types=dict(sorted(cells.items())),
        mapped_standard_cells=sum(mc.values()),mapped_sequential_cells=seqmapped,
        mapped_combinational_cells=sum(mc.values())-seqmapped,mapped_cell_types=dict(sorted(mc.items())),
        mapped_cell_area_um2=float(re.findall(r'Chip area for module.*?:\s*([0-9.]+)',log)[-1]),
        memories=0,latches=0,unresolved_modules=0,unmapped_generic_cells=0,
        warnings=[l for l in glog.splitlines() if l.startswith('Warning:')],mapped_warnings=warnings,
        mapped_warning_review='Unsupported scan functions belong to unused library cells; no scan-cell instances.',
        library_sha256=sha(H/'config/sg13g2_stdcell_typ_1p20V_25C.lib'),nand2_equivalents=None)
    dump(H/'reports/summary.json',summary); dump(H/'reports/synth_stat.rpt',summary)
    (H/'reports/cell_count.rpt').write_text('\n'.join(f'{t}: {n}' for t,n in sorted(cells.items()))+'\n')
    (H/'reports/sequential_dff.rpt').write_text('\n'.join(f'{m}: '+str(dict(collections.Counter(c['type'] for c in v['cells'].values() if 'DFF' in c['type'].upper()))) for m,v in data['modules'].items())+f'\nRecursive DFF bits: {seq}\n')
    (H/'reports/latch_check.rpt').write_text('PASS: structural JSON scans and Yosys check -assert; zero latch/memory/unresolved cells.\n')
    ps=data['modules'][TOP]['ports']
    expected={'ui_in':('input',8),'uo_out':('output',8),'uio_in':('input',8),'uio_out':('output',8),
              'uio_oe':('output',8),'clk':('input',1),'rst_n':('input',1),'ena':('input',1)}
    assert set(ps)==set(expected)
    assert all((ps[n]['direction'],len(ps[n]['bits']))==v for n,v in expected.items())
    assert ps['uio_oe']['bits']==list('01000111')
    assert all(ps['uio_out']['bits'][i]=='0' for i in [0,2,3,4])
    dump(ROOT/'evidence/review/final/structural_integration.json',dict(status='PASS',ports=expected,uio_oe='0xE2',
        limits='Structural metadata/port boundary only; official hardening/precheck NOT VERIFIED'))
def timing_report():
    log=(H/'reports/timing_est.rpt').read_text()
    assert not re.search(r'(^|\n)Error:',log)
    assert 'slack (VIOLATED)' not in log
    warnings=[l for l in log.splitlines() if l.startswith('Warning:')]
    assert warnings==['Warning: There are 12 unconstrained endpoints.'],warnings
    endpoints=log.split('Warning: There are 12 unconstrained endpoints.')[1].split()
    expected=[f'uio_oe[{i}]' for i in range(8)]+[f'uio_out[{i}]' for i in [0,2,3,4]]
    assert set(endpoints)==set(expected)
    # Exact displayed precision from limiting functional max path, not a guessed delay.
    maxlog=log.split('Path Type: min')[0]
    slack=min(float(x) for x in re.findall(r'\n\s*([0-9.]+)\s+slack \(MET\)',maxlog))
    budget=20-slack
    arrivals=[float(x) for x in re.findall(r'\n\s*([0-9.]+)\s+data arrival time',maxlog)]
    dump(H/'reports/timing_summary.json',dict(status='PASS',tool='OpenSTA 2.0.17',
        boundary='PRE-LAYOUT / SYNTHESIS ESTIMATE; typ_1p20V_25C, ideal clock, Liberty wire-load model, no extracted RC',
        clock_period_ns=20,setup_uncertainty_ns=.5,worst_setup_slack_ns=slack,
        worst_reported_data_arrival_ns=max(arrivals),period_minus_slack_ns=budget,
        naive_period_minus_slack_fmax_mhz=1000/budget,unconstrained_constant_endpoints=expected,
        warning_review='All 12 untimed endpoints independently verified as constant netlist outputs.',
        caution='The period-minus-slack budget includes IO delay and uncertainty; it is not the cell data delay or routed Fmax.'))
def collect():
    out=ROOT/'evidence/review/final'; results=[]
    for name in ['arithmetic','release','existing','legacy']:
        cases=ET.parse(out/(name+'.xml')).findall('.//testcase')
        failed=sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
        assert cases and not failed,(name,failed)
        results.append(dict(test=name,count=len(cases),passed=len(cases),failed=failed,status='PASS',evidence=f'evidence/review/final/{name}.log'))
    for name in ['tb_npu_standalone','tb_npu_2x2_standalone','tb_tt_um_2x2']:
        s=(out/(name+'.log')).read_text(); passed=len(re.findall(r'\[PASS\]',s))
        assert passed and '[FAIL]' not in s,name
        results.append(dict(test=name,count=passed,passed=passed,failed=0,status='PASS',evidence=f'evidence/review/final/{name}.log'))
    assert not (out/'verilator.log').read_text().strip(),'lint warnings'
    results.append(dict(test='Verilator lint',count=1,passed=1,failed=0,status='PASS',evidence='evidence/review/final/verilator.log'))
    network=(out/'trained_network.log').read_text()
    assert 'NETWORK_RESULT samples=6 batches=3 logical_macs=1104 total_cycles=1585' in network
    assert network.count('PASS')==3 and 'FAIL' not in network and 'FATAL' not in network
    dump(out/'rtl_e2e.json',dict(status='PASS',samples=6,batches=3,logical_macs=1104,
        total_cycles=1585,compared_values=66,model='models/tiny_ecg_qat/network.json',
        scope='Complete 20->8 ReLU->3 trained INT8 network; actual RTL hidden outputs feed RTL next layer',
        input_boundary='Offline annotated-beat 20-feature INT8 tensor; no raw streaming or clinical claim',
        evidence='evidence/review/final/trained_network.log'))
    results.append(dict(test='TC-TRAINED-E2E',count=6,passed=6,failed=0,status='PASS',evidence='evidence/review/final/trained_network.log'))
    identity=read(out/'run_identity.json')
    assert identity['rtl_sha256']=={str(p.relative_to(ROOT)):sha(p) for p in files()},'RTL changed during regression'
    dump(out/'verification.json',results)
    print(json.dumps(results,indent=2))
def historical():
    results=[]
    for archive in sorted((ROOT/'evidence/history').glob('*_*.zip')):
        with zipfile.ZipFile(archive) as z:
            manifest=z.read('pnr_handoff/HANDOFF_MANIFEST.md').decode()
            rows=[]
            for l in manifest.splitlines():
                m=re.match(r'\| `([^`]+)` \| ([\d,]+) \| `([0-9A-Fa-f]+)`',l)
                if not m: continue
                path,size,claimed=m.groups(); blob=z.read('pnr_handoff/'+path)
                rows.append(dict(path=path,claimed_sha256=claimed,hex_length=len(claimed),
                    actual_sha256=hashlib.sha256(blob).hexdigest(),claimed_size=int(size.replace(',','')),
                    actual_size=len(blob),valid_sha256=len(claimed)==64,
                    matches=claimed.lower()==hashlib.sha256(blob).hexdigest()))
            assert rows
            results.append(dict(archive=str(archive.relative_to(ROOT)),files=rows))
    dump(ROOT/'evidence/review/baseline/manifest_audit.json',results)
def manifest(check=False):
    target=H/'HANDOFF_MANIFEST.md'
    ps=sorted(p for p in H.rglob('*') if p.is_file() and p!=target)
    expected={p.relative_to(H).as_posix():(p.stat().st_size,sha(p)) for p in ps}
    if not check:
        approvals=json.loads((ROOT/'schemas/review_approvals.json').read_text(encoding='utf-8-sig'))
        ready=approvals.get('gate_5',{}).get('approved',False) and read(ROOT/'schemas/verification_report.json')['gate_status']=='PASS'
        status='READY FOR PNR' if ready else 'NOT READY FOR PNR'
        text=f'# PnR handoff manifest\n\nStatus: {status}; see docs/FRONTEND_SIGNOFF_REVIEW.md.\n'
        text+='Top tt_um_tinyml_npu_2x2; IHP planning2x2; target20ns. Author: Thinh Pham.\n'
        text+='Initial commit d020f70630e1c9feacf9fd79206d7a9e2874afed; resumed editor base c0ef2520c1a76f5730e6c716403ca77bc42194e9.\n'
        text+='Hashes identify the reviewed package bytes; Git records the release commit identity.\n'
        text+='This manifest excludes itself to avoid circular self-hashing. All other package files are included.\n\n'
        text+='| Relative path | Bytes | SHA-256 |\n|---|---:|---|\n'
        text+='\n'.join(f'| `{p}` | {s} | `{h}` |' for p,(s,h) in expected.items())+'\n'
        target.write_text(text)
    parsed={}
    for l in target.read_text().splitlines():
        m=re.match(r'\| `([^`]+)` \| (\d+) \| `([0-9a-fA-F]+)` \|$',l)
        if m:
            p,s,h=m.groups(); assert p not in parsed and len(h)==64
            parsed[p]=(int(s),h.lower())
    assert parsed==expected,'manifest inventory/hash mismatch'
    print(f'PASS: {len(parsed)} paths, sizes and 64-hex SHA-256 values; no duplicate/missing artifacts')
    if check: dump(ROOT/'evidence/review/final/python_manifest_check.json',dict(status='PASS',files=len(parsed),manifest_sha256=sha(target)))

if __name__=='__main__':
    action=sys.argv[1]
    if action=='filelist': print(' '.join(str(p.relative_to(ROOT)) for p in files()))
    elif action=='prepare': prepare()
    elif action=='synth-report': synth_report()
    elif action=='timing-report': timing_report()
    elif action=='collect': collect()
    elif action=='historical-manifests': historical()
    elif action=='manifest': manifest()
    elif action=='manifest-check': manifest(True)
    else: raise SystemExit('Unknown report action: '+action)
