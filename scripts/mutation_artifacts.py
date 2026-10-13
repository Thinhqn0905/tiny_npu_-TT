"""Prepare isolated compiled RTL mutants and parse detection evidence; no EDA calls."""
import hashlib,json,shutil,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/mutation'
EVIDENCE=ROOT/'evidence/review/mutation'
definitions=[
 ('M01','001','unit','exhaustive_products_and_overflow','npu_pe.v','data_a_in * data_b_in','$unsigned(data_a_in) * $unsigned(data_b_in)'),
 ('M02','001','unit','exhaustive_products_and_overflow','npu_pe.v','{(ACC_WIDTH-16){prod[15]}}','{(ACC_WIDTH-16){1\'b0}}'),
 ('M03','001','unit','exhaustive_products_and_overflow','npu_pe.v','acc_reg + prod_sext','acc_reg - prod_sext'),
 ('M04','002','unit','systolic_and_broadcast','npu_array.v','assign pe_a_in = data_a_in_vec[r*DATA_WIDTH +: DATA_WIDTH];','assign pe_a_in = data_a_in_vec[0 +: DATA_WIDTH];'),
 ('M05','002','unit','systolic_and_broadcast','npu_array.v','assign pe_b_in = data_b_in_vec[c*DATA_WIDTH +: DATA_WIDTH];','assign pe_b_in = data_b_in_vec[0 +: DATA_WIDTH];'),
 ('M06','002','unit','systolic_and_broadcast','npu_pe.v','data_a_out <= data_a_in;','data_a_out <= {DATA_WIDTH{1\'b0}};'),
 ('M07','003','release','ready_back_to_back','tt_um_tinyml_npu_2x2.v','assign npu_ready = rst_n && ena && (state == S_IDLE);','assign npu_ready = 1\'b1;'),
 ('M08','003','release','ready_back_to_back','tt_um_tinyml_npu_2x2.v','cfg_vector_len <= {2\'b00, ui_in[5:0]} + 8\'d1;','cfg_vector_len <= {2\'b00, ui_in[5:0]} + 8\'d2;'),
 ('M09','003','release','ready_back_to_back','tt_um_tinyml_npu_2x2.v','>= cfg_vector_len','> cfg_vector_len'),
 ('M10','004','unit','rounding_boundaries','npu_activation.v','ONE <<< (shift_val - 4\'d1)','ZERO <<< (shift_val - 4\'d1)'),
 ('M11','004','unit','rounding_boundaries','npu_activation.v','acc_rounded >>> shift_val','acc_rounded >> shift_val'),
 ('M12','004','unit','rounding_boundaries','npu_activation.v',"? 8'sd127 :","? 8'sd126 :"),
 ('M13','005','network','none','npu_pe.v','acc_reg + prod_sext','acc_reg'),
 ('M14','005','network','none','npu_top_2x2.v','.act_type(act_type)',".act_type(2'b00)"),
 ('M15','005','network','none','npu_top_2x2.v','mux_act = pe01_act; mux_acc = pe01_acc','mux_act = pe00_act; mux_acc = pe00_acc'),
 ('M16','006','network','none','tt_um_tinyml_npu_2x2.v',"assign uio_oe = 8'b11100010;","assign uio_oe = 8'b11100011;"),
 ('M17','006','network','none','tt_um_tinyml_npu_2x2.v',"assign uio_out[4] = 1'b0;","assign uio_out[4] = 1'b1;"),
 ('M18','006','network','none','tt_um_tinyml_npu_2x2.v',"npu_busy       <= 1'b0;","npu_busy       <= 1'b1;"),
]
def prepare():
    WORK.mkdir(parents=True,exist_ok=True); EVIDENCE.mkdir(parents=True,exist_ok=True)
    metadata=[]; manifest=[]
    for mid,req,kind,tc,name,old,new in definitions:
        folder=WORK/mid; folder.mkdir(exist_ok=True)
        for p in (ROOT/'pnr_handoff/rtl').glob('*.v'): shutil.copyfile(p,folder/p.name)
        target=folder/name; source=target.read_text(); occurrences=source.count(old)
        assert occurrences==(4 if mid=='M14' else 1),(mid,occurrences)
        target.write_text(source.replace(old,new))
        evidence=EVIDENCE/mid; evidence.mkdir(exist_ok=True)
        item=dict(id=mid,req_id='REQ-NPU-'+req,kind=kind,test_case=tc,source=name,
                  old=old,new=new,mutated_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        (evidence/'definition.json').write_text(json.dumps(item,indent=2)+'\n')
        metadata.append(item); manifest.append(f'{mid} {kind} {tc}')
    (WORK/'manifest.txt').write_text('\n'.join(manifest)+'\n')
    (EVIDENCE/'definitions.json').write_text(json.dumps(metadata,indent=2)+'\n')
def collect():
    rows=[]; per={}; invalid=0
    for definition in json.loads((EVIDENCE/'definitions.json').read_text()):
        p=EVIDENCE/definition['id']; result={**definition}
        compile_rc=int((p/'compile_rc.txt').read_text()); run_rc=int((p/'run_rc.txt').read_text())
        log=(p/'run.log').read_text() if (p/'run.log').exists() else ''
        compiled=compile_rc==0; caught=False
        if compiled and definition['kind']=='network':
            caught=run_rc!=0 and ('TC-TRAINED-E2E' in log or 'PROP-' in log) and 'FATAL:' in log
        elif compiled and (p/'results.xml').exists():
            cases=ET.parse(p/'results.xml').findall('.//testcase')
            # Cocotb may return zero even when its result XML records a failed test.
            caught=bool(cases) and any(c.find('failure') is not None for c in cases)
        result.update(compiled=compiled,compile_rc=compile_rc,run_rc=run_rc,detected=caught,
                      status='PASS' if compiled and caught else 'FAIL',evidence=str(p.relative_to(ROOT)))
        rows.append(result); invalid+=not compiled
        per.setdefault(result['req_id'],[0,0]); per[result['req_id']][0]+=caught; per[result['req_id']][1]+=compiled
    summary=dict(status='PASS' if not invalid and all(r['detected'] for r in rows) else 'FAIL',
        mutations=rows,invalid_mutants=invalid,
        per_requirement={r:dict(detected=n,compiled=d,score=n/d if d else None) for r,(n,d) in per.items()},
        limitation='18 sampled plausible faults only; not an exhaustive correctness or formal-equivalence claim')
    (EVIDENCE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='mutations'},indent=2))
    if summary['status']!='PASS': raise SystemExit(1)
if __name__=='__main__': prepare() if sys.argv[1]=='prepare' else collect()
