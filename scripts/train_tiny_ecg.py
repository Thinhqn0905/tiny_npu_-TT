"""Train a small real-data, bias-free 20->8->3 ECG MLP for the frozen MAC API.

Uses QAT with the hardware's dyadic scaling and rounding. It is an additional
locally trained model, not the downloaded CardioEdgeAI CNN or a distillation.
No RTL is imported. Expert-segmented offline feature tensors are the boundary.
"""
import argparse,hashlib,json,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DS1='101 106 108 109 112 114 115 116 118 119 122 124 201 203 205 207 208 209 215 220 223 230'.split()
DS2='100 103 105 111 113 117 121 123 200 202 210 212 213 214 219 221 222 228 231 232 233 234'.split()
VAL=['215','220','223','230']
SEED=784736294

def features():
    import numpy as np,scipy.signal as sig,wfdb
    xs=[]; ys=[]; recs=[]; peaks=[]
    groups={c:i for i,s in enumerate(['NLRej','AaJS','VE']) for c in s}
    sos=sig.butter(4,[.5,40],btype='bandpass',fs=360,output='sos')
    for rec in sorted(DS1+DS2):
        wave=wfdb.rdrecord(str(ROOT/'dataset/mitbih'/rec))
        ann=wfdb.rdann(str(ROOT/'dataset/mitbih'/rec),'atr')
        z=sig.sosfiltfilt(sos,wave.p_signal[:,0].astype('float64'))
        z=(z-z.mean())/(z.std()+1e-9)
        beats=[(int(r),groups[s]) for r,s in zip(ann.sample,ann.symbol) if s in groups and 144<=r<=len(z)-216]
        r=np.array([p[0] for p in beats]); rr=np.diff(r)/360
        for k,(p,y) in enumerate(beats):
            pre=rr[k-1] if k else rr[0]
            post=rr[k] if k<len(rr) else pre
            local=np.mean(rr[max(0,k-5):k]) if k else pre
            morphology=np.interp(np.linspace(0,359,16),np.arange(360),z[p-144:p+216])
            timing=np.array([(pre-.8)/.3,(post-.8)/.3,(local-.8)/.3,(pre/local-1)/.3 if local>0 else 0])
            x=np.clip(np.floor(np.concatenate([morphology,timing])*16+.5),-128,127).astype(np.int8)
            xs.append(x); ys.append(y); recs.append(rec); peaks.append(p)
        print('Features',rec,len(beats),flush=True)
    out=ROOT/'dataset/tiny_ecg_features.npz'
    np.savez_compressed(out,X=np.array(xs),y=np.array(ys),record=np.array(recs),r=np.array(peaks))
    print('Feature tensors',out,flush=True)

def train():
    import numpy as np,torch
    torch.set_num_threads(2); torch.manual_seed(SEED); np.random.seed(SEED)
    torch.use_deterministic_algorithms(True)
    arrays=np.load(ROOT/'dataset/tiny_ecg_features.npz',allow_pickle=False)
    xx,yy,rec,rr=[arrays[n] for n in ['X','y','record','r']]
    fit=np.isin(rec,[r for r in DS1 if r not in VAL]); val=np.isin(rec,VAL)
    test=np.isin(rec,[r for r in DS2 if r!='202'])
    # 201/202 are one subject: exclude 202 rather than claim false independence.
    assert not set(rec[fit]) & set(rec[test])
    X=torch.tensor(xx[fit],dtype=torch.float32); y=torch.tensor(yy[fit],dtype=torch.long)
    vx=torch.tensor(xx[val],dtype=torch.float32); vy=torch.tensor(yy[val],dtype=torch.long)
    w1=torch.nn.Parameter(torch.randn(8,20)*.1); w2=torch.nn.Parameter(torch.randn(3,8)*.1)
    def ste(v): return v+(torch.floor(v+.5)-v).detach()
    def forward(x):
        a=ste(w1*64).clamp(-128,127); b=ste(w2*64).clamp(-128,127)
        h=ste((x@a.T)/64).clamp(0,127)
        return ste((h@b.T)/64).clamp(-128,127)/16
    counts=np.bincount(yy[fit],minlength=3)
    classweight=torch.tensor(len(y)/(3*counts),dtype=torch.float32)
    opt=torch.optim.Adam([w1,w2],lr=.01)
    loss_fn=torch.nn.CrossEntropyLoss(weight=classweight)
    rng=torch.Generator().manual_seed(SEED)
    history=[]; best=None; best_f1=-1
    def metrics(actual,pred):
        cm=np.zeros((3,3),dtype=np.int64); np.add.at(cm,(actual,pred),1)
        tp=np.diag(cm); p=tp/np.maximum(cm.sum(0),1); r=tp/np.maximum(cm.sum(1),1)
        f=2*p*r/np.maximum(p+r,1e-12)
        return dict(count=int(cm.sum()),accuracy=float(tp.sum()/cm.sum()),macro_f1=float(f.mean()),
                    per_class_f1=f.tolist(),confusion_matrix=cm.tolist())
    for epoch in range(40):
        order=torch.randperm(len(y),generator=rng); total=0.
        for ids in order.split(1024):
            opt.zero_grad(); loss=loss_fn(forward(X[ids]),y[ids]); loss.backward(); opt.step()
            total+=float(loss.detach())*len(ids)
        with torch.no_grad(): pred=forward(vx).argmax(1).numpy()
        met=metrics(yy[val],pred)
        row=dict(epoch=epoch+1,loss=total/len(y),validation=met); history.append(row)
        if met['macro_f1']>best_f1:
            best_f1=met['macro_f1']; best=[w1.detach().clone(),w2.detach().clone()]
        print('Epoch',epoch+1,'loss',row['loss'],'validation macroF1',met['macro_f1'],flush=True)
    qa,qb=[np.clip(np.floor(w.numpy()*64+.5),-128,127).astype(np.int64) for w in best]
    def integer(x):
        a=x.astype(np.int64)@qa.T
        h=np.clip((a+32)//64,0,127)
        b=h@qb.T; out=np.clip((b+32)//64,-128,127)
        assert np.max(np.abs(a))<2**23 and np.max(np.abs(b))<2**23
        return h,out
    hidden,outputs=integer(xx[test]); met=metrics(yy[test],outputs.argmax(1))
    trainmet=metrics(yy[fit],integer(xx[fit])[1].argmax(1))
    samples=[]
    ids=np.flatnonzero(test)
    for cls in range(3):
        for i in ids[yy[test]==cls][:2]:
            h,o=integer(xx[i:i+1]); samples.append(dict(record=str(rec[i]),r_sample=int(rr[i]),label=int(yy[i]),
                input=xx[i].tolist(),hidden=h[0].tolist(),output=o[0].tolist()))
    artifact=dict(kind='locally trained QAT MLP; not the downloaded CardioEdgeAI CNN',
        seed=SEED,architecture=[20,8,3],bias=False,shift=[6,6],activation=[1,0],
        weights=[qa.tolist(),qb.tolist()],logical_macs_per_sample=184,
        input_contract='16 uniformly interpolated values from expert-centered360-sample normalized beat +4RR; scale16, ties toward +infinity, signed INT8 clamp',
        dataset_manifest_sha256=hashlib.sha256((ROOT/'evidence/ecg/dataset_manifest.json').read_bytes()).hexdigest(),
        train_records=[r for r in DS1 if r not in VAL],validation_records=VAL,
        test_records=[r for r in DS2 if r!='202'],excluded_record='202: same subject as training201',
        training=dict(optimizer='Adam',learning_rate=.01,epochs=40,batch=1024,weighted_cross_entropy=True,
            selection='best validation macro-F1 only; test set not used for selection',torch_version=torch.__version__),
        training_metrics=trainmet,test_metrics=met,samples=samples,
        boundary='offline annotated feature-tensor classification; preprocessing/RR/argmax on host; all network dense/ReLU stages mapped to NPU',
        limitations=['No raw-signal R detector','Full-record normalization is offline','post-RR needs next beat',
            'Small proof-of-integration model; no clinical qualification'])
    out=ROOT/'models/tiny_ecg_qat'; out.mkdir(parents=True,exist_ok=True)
    (out/'network.json').write_text(json.dumps(artifact,indent=2)+'\n')
    (out/'training_history.json').write_text(json.dumps(history,indent=2)+'\n')
    print('Test metrics',json.dumps(met),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('phase',choices=['features','train']); a=ap.parse_args()
    features() if a.phase=='features' else train()
