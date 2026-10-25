"""Freeze, run once, resume completed stages, and verify the final 2026 experiment."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from src.utils.config import ROOT, load_config, protocol_hash

PLAN=ROOT/'outputs/holdout_plan.json'
RUN=ROOT/'outputs/final_holdout_pipeline.json'
STAGES=[('baselines','src.evaluation.run_baselines'),('econometric','src.models.run'),
        ('ml','src.models.run_ml'),('comparison','src.evaluation.aggregate'),
        ('econometric_diagnostics','src.models.diagnostics'),('ml_analysis','src.models.ml_analysis'),
        ('risk','src.backend4'),('verification','src.evaluation.verify_holdout'),
        ('report','src.reporting.holdout_report')]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(p)

def frozen_files(root=ROOT):
    paths=[]
    for folder in ('src','tests','config'):
        paths += [p for p in (root/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.toml')]
    paths += [root/'requirements.txt',root/'data/processed/dataset.parquet',
              root/'data/processed/dataset_meta.json',root/'data/processed/forecast_schedule.parquet',
              root/'outputs/model_selection/backend3_locked.json',root/'docs/GROUP_PROTOCOL.md',root/'docs/HOLDOUT_PROTOCOL.md']
    for folder in ('forecasts','volatility','tables','risk','diagnostics','sensitivity','reporting','figures'):
        paths += [p for p in (root/'outputs'/folder).rglob('*') if p.is_file()]
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(set(paths))}

def check_frozen(expected,root=ROOT):
    for rel,digest in expected.items():
        p=root/rel
        if not p.is_file() or sha(p)!=digest:raise ValueError('Frozen input changed: '+rel)

def prepare():
    if PLAN.exists() or RUN.exists() or list((ROOT/'outputs').glob('final_holdout_*.json')):
        raise ValueError('A final holdout plan/run already exists; inspect it instead of replacing it')
    if any((ROOT/'outputs'/n).exists() for n in ('forecasts_holdout','risk_holdout','holdout_tables')):
        raise ValueError('Holdout outputs already exist; reconcile provenance before preparing')
    cfg=load_config()
    end=min(cfg['data']['end'],cfg['data']['holdout_end'])
    if end<cfg['data']['holdout_start']:raise ValueError('No holdout observations available')
    versions={name:importlib.metadata.version(name) for name in
              ('numpy','pandas','scipy','arch','statsmodels','scikit-learn','xgboost','pyarrow')}
    save(PLAN,dict(schema_version=1,prepared_at=now(),start=cfg['data']['holdout_start'],end=end,
        protocol_sha256=protocol_hash(cfg),python=sys.version,package_versions=versions,
        primary='rolling h1; QLIKE; HAR-RV benchmark; common valid dates across all nine models',
        secondary='expanding and h7; matched volume ablation; origin-known regimes',
        risk='h1 VaR/ES 95%/99%; FHS seeded by prior own-model OOS residuals',
        retuning=False,refit_every_days=5,refit_anchor=cfg['study']['refit_anchor_origin_date'],
        caveats=['2026 data previously inspected for QA/descriptive statistics, not model scoring',
                 'Partial-year sample, 99% breach tests have few expected exceptions',
                 'Primary rolling h1 QLIKE DM family uses Holm across both coins; secondary p-values nominal',
                 'No dedicated ES calibration test; no new event windows chosen from holdout'],
        stages=STAGES,frozen_sha256=frozen_files()))
    print('Frozen final holdout plan:',PLAN,flush=True)

def run(resume=False):
    if not PLAN.exists():raise ValueError('Run --prepare after tests, before opening holdout results')
    plan=json.loads(PLAN.read_text(encoding='utf-8'));check_frozen(plan['frozen_sha256'])
    if RUN.exists():
        state=json.loads(RUN.read_text(encoding='utf-8'))
        if not resume or state['state']=='completed':raise ValueError('Final run already exists; inspect it or resume pending stages')
        if state['plan_sha256']!=sha(PLAN):raise ValueError('Plan changed after the experiment started')
        if any(s['state'] in ('started','failed') for s in state['stages'].values()):
            raise ValueError('Interrupted/failed stage needs an audited recovery; never delete locks to retry')
        latest={}
        for stage in state['stages'].values():latest.update(stage.get('output_sha256',{}))
        check_frozen(latest)
    else:
        if resume:raise ValueError('No existing run to resume')
        state=dict(state='started',started_at=now(),plan_sha256=sha(PLAN),stages={})
        save(RUN,state)
    for name,module in STAGES:
        if state['stages'].get(name,{}).get('state')=='completed':continue
        state['stages'][name]=dict(state='started',started_at=now());save(RUN,state)
        args=[sys.executable,'-B','-u','-X','utf8','-m',module]
        if name not in ('verification','report'):args+=['--final-holdout']
        print('\nFINAL HOLDOUT STAGE:',name,flush=True)
        try:
            subprocess.run(args,cwd=ROOT,check=True)
            check_frozen(plan['frozen_sha256'])
        except Exception as exc:
            state['state']='failed';state['stages'][name].update(state='failed',error=str(exc));save(RUN,state);raise
        # Hash each stage's immutable deliverables; later stages never overwrite them.
        folders={'baselines':['outputs/forecasts_holdout'],
                 'econometric':['outputs/forecasts_holdout','outputs/volatility_holdout','outputs/diagnostics_holdout'],
                 'ml':['outputs/forecasts_holdout','outputs/volatility_holdout','outputs/ablation_holdout','outputs/diagnostics_holdout/backend3'],
                 'comparison':['outputs/holdout_tables','outputs/holdout_figures'],
                 'econometric_diagnostics':['outputs/diagnostics_holdout','outputs/holdout_figures'],
                 'ml_analysis':['outputs/diagnostics_holdout/backend3','outputs/holdout_tables','outputs/holdout_figures'],
                 'risk':['outputs/risk_holdout','outputs/holdout_figures/risk'],
                 'verification':['outputs/holdout_verification.json'],
                 'report':['docs/HOLDOUT_RESULTS.md','outputs/holdout_tables/evaluation_vs_holdout.csv']}
        outputs={}
        for rel in folders[name]:
            p=ROOT/rel
            for f in ([p] if p.is_file() else p.rglob('*')):
                if f.is_file():outputs[f.relative_to(ROOT).as_posix()]=sha(f)
        state['stages'][name].update(state='completed',completed_at=now(),output_sha256=outputs)
        save(RUN,state)
    state.update(state='completed',completed_at=now());save(RUN,state)
    print('Final holdout completed; results in docs/HOLDOUT_RESULTS.md',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',action='store_true');g.add_argument('--run',action='store_true');g.add_argument('--resume',action='store_true')
    a=p.parse_args()
    if a.prepare:prepare()
    else:run(a.resume)

if __name__=='__main__':main()
