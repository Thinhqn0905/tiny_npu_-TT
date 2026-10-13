#!/usr/bin/env python3
"""Acquire a pinned public trained INT8 ECG artifact; independently evaluate DS2.

This is a SOFTWARE benchmark. It never calls the RTL and cannot qualify ASIC
inference. Source code, license, raw sample identifiers and hashes are retained.
"""
import argparse, collections, csv, hashlib, json, platform, re, shutil, time
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
REV='ec36bbc5f96ea42a93274c499a51e3678742ffcf'
BASE='https://raw.githubusercontent.com/md-rejoyan-islam/CardioEdgeAI/'+REV+'/'
DS2='100 103 105 111 113 117 121 123 200 202 210 212 213 214 219 221 222 228 231 232 233 234'.split()

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-dataset',type=Path,default=Path(r'E:\ResearchOnWork\data\ecg\mitdb_1.0.0'))
    ap.add_argument('--prepare-only',action='store_true')
    args=ap.parse_args()
    data=ROOT/'dataset/mitbih'; data.mkdir(parents=True,exist_ok=True)
    out=ROOT/'evidence/ecg'; out.mkdir(parents=True,exist_ok=True)
    model=ROOT/'models/CardioEdgeAI'; model.mkdir(parents=True,exist_ok=True)
    records=[]
    for p in sorted(args.source_dataset.iterdir()):
        if p.suffix not in ('.dat','.hea','.atr'): continue
        q=data/p.name
        if not q.exists(): shutil.copy2(p,q)
        source_hash=digest(p)
        assert digest(q)==source_hash,p
        records.append(dict(path=p.name,size=p.stat().st_size,sha256=source_hash))
    assert len(records)==144,'expected 48 records, each .hea/.dat/.atr'
    (out/'dataset_manifest.json').write_text(json.dumps(dict(source=str(args.source_dataset),
        destination=str(data),files=records,sha256_verification='PASS'),indent=2)+'\n')
    files=['deploy/esp32/CardioEdgeAI/model.h','LICENSE','README.md','CITATION.cff',
           'src/config.py','src/data/preprocess.py','src/models/cnn.py',
           'src/models/quantize.py','deploy/tflite/export_model_header.py','docs/results.json']
    for rel in files:
        q=model/'upstream'/rel; q.parent.mkdir(parents=True,exist_ok=True)
        if not q.exists(): q.write_bytes(urlopen(BASE+rel).read())
    header=model/'upstream'/files[0]
    array=header.read_text().split('{',1)[1].split('}',1)[0]
    blob=bytes(int(h,16) for h in re.findall(r'0x([0-9a-fA-F]{2})',array))
    assert blob[4:8]==b'TFL3','not a TensorFlow Lite FlatBuffer'
    artifact=model/'ecg_int8.tflite'; artifact.write_bytes(blob)
    (model/'PROVENANCE.json').write_text(json.dumps(dict(
        repository='https://github.com/md-rejoyan-islam/CardioEdgeAI',commit=REV,
        source_header=files[0],source_url=BASE+files[0],trained_status='upstream reports trained; local training not rerun',
        license='MIT; upstream/LICENSE retained',size=len(blob),sha256=digest(artifact),
        upstream_files={rel:digest(model/'upstream'/rel) for rel in files}),indent=2)+'\n')
    import numpy as np
    try:
        from tflite_runtime.interpreter import Interpreter
        import tflite_runtime
        backend='tflite-runtime '+tflite_runtime.__version__
    except ImportError:
        import tensorflow as tf
        Interpreter=tf.lite.Interpreter
        backend='tensorflow '+tf.__version__
    import scipy.signal as sig
    import scipy
    import wfdb
    interpreter=Interpreter(model_path=str(artifact),num_threads=1,
        experimental_preserve_all_tensors=True)
    interpreter.allocate_tensors()
    details={t['index']:t for t in interpreter.get_tensor_details()}
    ops=interpreter._get_ops_details()
    inputs=interpreter.get_input_details(); output=interpreter.get_output_details()[0]
    macs=0
    for op in ops:
        if op['op_name'] in ('CONV_2D','FULLY_CONNECTED'):
            w=details[int(op['inputs'][1])]['shape']
            y=details[int(op['outputs'][0])]['shape']
            macs+=int(np.prod(y[1:])*np.prod(w[1:]))
    inventory=dict(artifact_sha256=digest(artifact),bytes=len(blob),logical_macs_per_inference=macs,
        inputs=[dict(name=t['name'],shape=t['shape'].tolist(),dtype=str(t['dtype']),quantization=list(t['quantization'])) for t in inputs],
        output=dict(name=output['name'],shape=output['shape'].tolist(),quantization=list(output['quantization'])),
        operators=[dict(name=o['op_name'],inputs=o['inputs'].tolist(),outputs=o['outputs'].tolist()) for o in ops],
        hardware_mapping='NOT VERIFIED: model uses bias, per-channel affine scaling, pooling, mean and softmax absent from the frozen wrapper',
        versions=dict(python=platform.python_version(),numpy=np.__version__,runtime=backend,wfdb=wfdb.__version__,scipy=scipy.__version__))
    (out/'model_inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print('Model',len(blob),'bytes, logical MACs',macs,'inputs',inventory['inputs'],flush=True)
    if args.prepare_only: return
    cm=np.zeros((3,3),dtype=np.int64); timings=[]; all_samples=[]
    groups={c:i for i,s in enumerate(['NLRej','AaJS','VE']) for c in s}
    signal_input=next(t for t in inputs if np.prod(t['shape'])==360)
    rr_input=next(t for t in inputs if np.prod(t['shape'])==4)
    sos=sig.butter(4,[0.5,40],btype='bandpass',fs=360,output='sos')
    def quantize(value,desc):
        scale,zero=desc['quantization']
        return np.clip(np.rint(value/(scale+1e-12))+zero,-128,127).astype(np.int8).reshape(desc['shape'])
    with (out/'predictions.csv').open('w',newline='') as f:
        writer=csv.writer(f); writer.writerow(['record','r_sample','symbol','label','prediction','q0','q1','q2','invoke_ns'])
        for record in DS2:
            wf=wfdb.rdrecord(str(data/record)); ann=wfdb.rdann(str(data/record),'atr')
            assert wf.fs==360
            filtered=sig.sosfiltfilt(sos,wf.p_signal[:,0].astype(np.float64))
            normalized=(filtered-filtered.mean())/(filtered.std()+1e-9)
            beats=[(int(r),s,groups[s]) for r,s in zip(ann.sample,ann.symbol)
                   if s in groups and 144<=r<=len(filtered)-216]
            r=np.array([x[0] for x in beats]); rr=np.diff(r)/360
            for k,(peak,symbol,label) in enumerate(beats):
                pre=rr[k-1] if k else (rr[0] if len(rr) else .8)
                post=rr[k] if k<len(rr) else pre
                local=np.mean(rr[max(0,k-5):k]) if k else pre
                features=np.array([(pre-.8)/.3,(post-.8)/.3,(local-.8)/.3,
                                   (pre/local-1)/.3 if local>0 else 0],dtype=np.float32)
                beat=normalized[peak-144:peak+216].astype(np.float32)
                interpreter.set_tensor(signal_input['index'],quantize(beat,signal_input))
                interpreter.set_tensor(rr_input['index'],quantize(features,rr_input))
                start=time.perf_counter_ns(); interpreter.invoke(); elapsed=time.perf_counter_ns()-start
                q=interpreter.get_tensor(output['index']).ravel(); pred=int(np.argmax(q))
                cm[label,pred]+=1; timings.append(elapsed)
                writer.writerow([record,peak,symbol,label,pred,*q.tolist(),elapsed])
                if len(all_samples)<8:
                    all_samples.append(dict(record=record,r_sample=peak,symbol=symbol,
                        input_int8=quantize(beat,signal_input).ravel().tolist(),
                        rr_int8=quantize(features,rr_input).ravel().tolist(),output_int8=q.tolist()))
            print(record,'beats',len(beats),'cumulative',int(cm.sum()),flush=True)
    tp=np.diag(cm); precision=tp/np.maximum(cm.sum(axis=0),1); recall=tp/np.maximum(cm.sum(axis=1),1)
    f1=2*precision*recall/np.maximum(precision+recall,1e-12)
    summary=dict(status='PASS',boundary='SOFTWARE ONLY; annotated-beat evaluation; no RTL/ASIC inference',
        model_sha256=digest(artifact),records=DS2,count=int(cm.sum()),classes=['N','S','V'],
        confusion_matrix=cm.tolist(),accuracy=float(tp.sum()/cm.sum()),macro_f1=float(f1.mean()),
        per_class_f1=f1.tolist(),invoke_median_us=float(np.median(timings)/1000),
        invoke_p95_us=float(np.percentile(timings,95)/1000),threads=1,
        logical_macs_per_inference=macs,
        preprocessing='channel 0; 4th-order 0.5-40Hz zero-phase Butterworth; full-record z-score; expert-annotation centered 144+216 samples; N/S/V only; RR from retained N/S/V peaks',
        limitations=['Not raw-signal E2E: gold annotation peaks supplied',
            'Full-record normalization uses future samples; post-RR needs the next beat',
            'Split follows upstream record lists; independence of patient identities not certified',
            'Downloaded training provenance not independently reproduced',
            'No RTL network mapping; hardware coverage remains arithmetic/protocol tests'],
        sample_vectors=all_samples)
    (out/'benchmark.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='sample_vectors'},indent=2),flush=True)

if __name__=='__main__': main()
