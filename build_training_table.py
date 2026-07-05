from __future__ import annotations
import argparse, csv, math, os
import pandas as pd
from ewt.io.walkforward import iter_as_of
from ewt.analyze import analyze_nested
from ewt.signal.scenario import build_scenarios
from ewt.weigh.features import FLAT_COLUMNS, flat_features

def parse_ids(spec):
    out=[]
    for part in spec.split(","):
        if "-" in part: a,b=part.split("-"); out+=list(range(int(a),int(b)+1))
        else: out.append(int(part))
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--stocks",default="1-30")
    ap.add_argument("--start",default="1975-01-01"); ap.add_argument("--step",default="6M")
    ap.add_argument("--horizon",type=int,default=252); ap.add_argument("--pivot-scale",type=float,default=1.0)
    ap.add_argument("--pivot-mode",default="log",choices=["log","atr"]); ap.add_argument("--atr-k",type=float,default=4.0)
    ap.add_argument("--out",default="records/train_table.csv"); a=ap.parse_args()
    ids=parse_ids(a.stocks); df=pd.read_csv(a.csv)
    os.makedirs(os.path.dirname(a.out) or ".",exist_ok=True); n=0
    with open(a.out,"w",newline="") as fh:
        w=csv.writer(fh); w.writerow(["stock","issued","y"]+FLAT_COLUMNS)
        for sid in ids:
            sdf=df[df["stock_id"]==sid][["date","open","high","low","close","volume"]].sort_values("date")
            if len(sdf)<300: continue
            full=sdf.copy(); full.index=pd.to_datetime(full["date"]); full=full.sort_index()
            close=full["close"].astype(float)
            for b in iter_as_of(sdf,start=a.start,step=a.step):
                if a.pivot_mode=="atr": an,nested=analyze_nested(b,pivot_mode="atr",atr_k=a.atr_k)
                else: an,nested=analyze_nested(b,pivot_scale=a.pivot_scale)
                lp=an["D"].bars.last_price
                pos=close.index.get_indexer([b.as_of],method="pad")[0]
                if pos<0 or pos+a.horizon>=len(close): continue
                fwd=math.copysign(1,close.iloc[pos+a.horizon]-close.iloc[pos])
                for s in build_scenarios(an["D"].counts,last_price=lp):
                    if s.is_residual or s.primary_count is None: continue
                    flat=flat_features(s.primary_count, s.primary_count.legs[-1].end.price)
                    y=1 if s.direction==fwd else 0
                    w.writerow([sid,str(b.as_of.date()),y]+[flat.get(c,0.0) for c in FLAT_COLUMNS]); n+=1
    print({"rows":n,"out":a.out})

if __name__=="__main__": main()
