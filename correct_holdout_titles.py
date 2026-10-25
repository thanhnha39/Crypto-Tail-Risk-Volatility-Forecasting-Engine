"""Audited, presentation-only correction after the completed frozen experiment.

Preserve the exact original plan/source and stage hashes. Change only a hardcoded
figure title, regenerate figures from saved forecasts, then verify all numerical
artifacts unchanged. Never fit, tune or restart the holdout experiment.
"""
import json
from pathlib import Path
import subprocess
import sys
from src.final_holdout import ROOT, PLAN, RUN, sha, save, now, check_frozen

def numerical_hashes():
    dirs=['forecasts_holdout','volatility_holdout','diagnostics_holdout','ablation_holdout',
          'holdout_tables','risk_holdout']
    return {p.relative_to(ROOT).as_posix():sha(p) for folder in dirs
            for p in sorted((ROOT/'outputs'/folder).rglob('*')) if p.is_file()}

def main():
    state=json.loads(RUN.read_text(encoding='utf-8'))
    if state['state']!='completed':raise ValueError('Only after the entire experiment has completed')
    original=ROOT/'outputs/holdout_plan_original.json'
    if original.exists():raise ValueError('Presentation amendment already recorded; do not replace its evidence')
    plan=json.loads(PLAN.read_text(encoding='utf-8'));check_frozen(plan['frozen_sha256'])
    before=numerical_hashes();old_plan_sha=sha(PLAN)
    original.write_bytes(PLAN.read_bytes())
    rel='src/evaluation/aggregate.py';source=ROOT/rel;old=source.read_text(encoding='utf-8')
    needle='axes[0].set_title(f"{symbol} | {scheme} | {h}-day variance | evaluation 2021–2025")'
    replacement='axes[0].set_title(f"{symbol} | {scheme} | {h}-day variance | {actual.index.min():%Y-%m-%d} to {actual.index.max():%Y-%m-%d}")'
    assert old.count(needle)==1
    archive=ROOT/'outputs/holdout_source_original/aggregate.py'
    archive.parent.mkdir(parents=True,exist_ok=True);archive.write_bytes(source.read_bytes())
    source.write_bytes(old.replace(needle,replacement).encode('utf-8'))
    amendment=dict(kind='presentation_only_after_completed_scoring',recorded_at=now(),
        reason='Replace hardcoded evaluation 2021–2025 figure title with actual saved target-date range',
        original_plan='outputs/holdout_plan_original.json',original_plan_sha256=old_plan_sha,
        source=rel,original_source_sha256=sha(archive),corrected_source_sha256=sha(source),
        archived_source='outputs/holdout_source_original/aggregate.py',
        model_forecasts_refitted=False,hyperparameters_changed=False)
    plan['post_run_amendments']=[amendment];plan['frozen_sha256'][rel]=sha(source);save(PLAN,plan)
    # Rendering only; no aggregate main/locks/model runner is invoked.
    from src.evaluation.aggregate import load_all_forecasts, build_eval_frame, make_figures
    from src.utils.config import load_config
    import pandas as pd
    cfg=load_config();ds=pd.read_parquet(ROOT/'data/processed/dataset.parquet')
    fc=load_all_forecasts(ROOT/'outputs/forecasts_holdout',ds,cfg,sha(ROOT/'data/processed/dataset.parquet'))
    ev,_=build_eval_frame(fc,ds,'holdout');make_figures(ev,cfg,ROOT/'outputs/holdout_figures')
    for module in ('src.evaluation.verify_holdout','src.reporting.holdout_report'):
        subprocess.run([sys.executable,'-B','-u','-X','utf8','-m',module],cwd=ROOT,check=True)
    assert before==numerical_hashes(), 'Presentation correction changed a numerical artifact'
    amendment['numerical_artifacts_unchanged']=True
    amendment['numerical_sha256']=before
    amendment['corrected_outputs_sha256']={p.relative_to(ROOT).as_posix():sha(p)
        for p in (ROOT/'outputs/holdout_figures').rglob('*') if p.is_file()}
    for p in [ROOT/'outputs/holdout_verification.json',ROOT/'outputs/holdout_report_manifest.json',ROOT/'docs/HOLDOUT_RESULTS.md']:
        amendment['corrected_outputs_sha256'][p.relative_to(ROOT).as_posix()]=sha(p)
    # Plan already contains the methodological amendment; completion evidence is
    # separate so verification/report plan hashes do not become circular.
    save(ROOT/'outputs/holdout_presentation_amendment.json',amendment)
    state['original_execution_plan_sha256']=state['plan_sha256'];state['plan_sha256']=sha(PLAN)
    state['post_run_presentation_amendment']='outputs/holdout_presentation_amendment.json'
    state['final_deliverable_sha256']=amendment['corrected_outputs_sha256']
    state['note']='Stage output hashes are historical snapshots; corrected figure/verification hashes are recorded separately.'
    save(RUN,state)
    print('Corrected date titles; original plan/source preserved; all numerical artifacts unchanged.',flush=True)

if __name__=='__main__':main()
