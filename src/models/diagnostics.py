"""Numerical diagnostic tables and plots, not academic report/chapter generation."""
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from src.data.download import save_json,sha256
from src.evaluation.validate import validate_forecasts
from src.models.config import model_config_hash,load_model_config
from src.utils.config import ROOT,load_config,protocol_hash

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--final-holdout",action="store_true")
    args=parser.parse_args(argv);config=load_config();options=load_model_config()
    directory=ROOT/("outputs/diagnostics_holdout" if args.final_holdout else "outputs/diagnostics")
    forecast_folder=ROOT/("outputs/forecasts_holdout" if args.final_holdout else "outputs/forecasts")
    figures=ROOT/("outputs/holdout_figures" if args.final_holdout else "outputs/figures")
    figures.mkdir(parents=True,exist_ok=True)
    fits=pd.read_csv(directory/"garch_fit_diagnostics.csv",parse_dates=["refit_origin"])
    residuals=pd.read_parquet(directory/"oos_standardized_residuals.parquet")
    successful=fits.loc[fits.fit_status.eq("ok")].copy()
    summaries=[]
    for (symbol,model,window),group in fits.groupby(["symbol","model","window"]):
        good=group.loc[group.fit_status.eq("ok")]
        summaries.append({"symbol":symbol,"model":model,"window":window,"refits_attempted":len(group),
            "refits_successful":len(good),"refits_failed":len(group)-len(good),
            "near_integrated_fits":int(good["near_integrated"].sum()),"nu_le_4_fits":int(good["nu"].le(4).sum()),
            "min_nu":float(good["nu"].min()),"max_persistence":float(good["persistence"].max()),
            "max_arch_forecast_difference":float(good["max_arch_forecast_difference"].max()),
            "nonfinite_covariances":int((~good["covariance_finite"].astype(bool)).sum()),
            "arch_lm_p_below_05":int(good["arch_lm_p"].lt(.05).sum()),
            "diagnostic_pvalues":"approximate; parameter estimation and heavy tails affect interpretation"})
    pd.DataFrame(summaries).to_csv(directory/"garch_diagnostic_summary.csv",index=False)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9})
    for (symbol,window),group in successful.groupby(["symbol","window"]):
        fig,axes=plt.subplots(3,2,figsize=(11,8),sharex=True,layout="constrained")
        for ax,parameter in zip(axes.flat,["omega","alpha[1]","beta[1]","gamma[1]","nu","persistence"]):
            for model,part in group.groupby("model"):
                part=part.sort_values("refit_origin")
                if parameter in part and part[parameter].notna().any():ax.plot(part.refit_origin,part[parameter],label=model,lw=.8)
            if parameter=="persistence":ax.axhline(1,color="red",lw=.7,ls="--")
            ax.set_title(parameter);ax.legend(fontsize=8);ax.grid(alpha=.15)
        fig.suptitle(f"{symbol} | {window} | Student-t GARCH parameter stability")
        fig.savefig(figures/f"backend2_{symbol}_{window}_parameters.png",dpi=130);plt.close(fig)
        resid=residuals.loc[residuals.symbol.eq(symbol)&residuals.window.eq(window)&residuals.model.isin(["garch","gjr_garch"])].copy()
        fig,axes=plt.subplots(2,2,figsize=(11,7),layout="constrained")
        for model,part in resid.groupby("model"):
            part=part.loc[np.isfinite(part.standardized_residual)&part.nu.gt(2)].sort_values("target_date")
            z=part.standardized_residual.to_numpy();nu=part.nu.to_numpy()
            axes[0,0].plot(part.target_date,z,lw=.6,label=model)
            axes[0,1].hist(z,bins=45,density=True,histtype="step",label=model)
            pit=stats.t.cdf(z/np.sqrt((nu-2)/nu),df=nu)
            axes[1,0].hist(pit,bins=np.linspace(0,1,21),density=True,histtype="step",label=model)
            transformed=np.sort(stats.norm.ppf(np.clip(pit,1e-10,1-1e-10)))
            theoretical=stats.norm.ppf((np.arange(len(transformed))+.5)/len(transformed))
            axes[1,1].plot(theoretical,transformed,lw=.8,label=model)
        axes[0,0].set_title("One-step out-of-sample standardized return residuals")
        axes[0,1].set_title("Standardized residual density (Student-t, not normal)")
        axes[1,0].axhline(1,color="black",lw=.7,ls="--");axes[1,0].set_title("PIT under fitted standardized Student-t")
        axes[1,1].plot([-4,4],[-4,4],color="black",ls="--",lw=.7);axes[1,1].set_title("Normal-score PIT Q-Q (descriptive)")
        for ax in axes.flat:ax.legend(fontsize=8);ax.grid(alpha=.15)
        fig.suptitle(f"{symbol} | {window} | OOS diagnostics")
        fig.savefig(figures/f"backend2_{symbol}_{window}_residuals.png",dpi=130);plt.close(fig)
    dataset=pd.read_parquet(ROOT/"data/processed/dataset.parquet")
    meta=json.loads((ROOT/"data/processed/dataset_meta.json").read_text())
    result_checks=[]
    for symbol in config["data"]["symbols"]:
        for model in ["har_rv","garch","gjr_garch",options["combination"]["model_name"]]:
            path=forecast_folder/f"{symbol}_{model}.parquet";forecast=pd.read_parquet(path)
            errors=validate_forecasts(forecast,dataset,config,meta["dataset_sha256"],model)
            if errors:raise ValueError(errors)
            if not forecast["model_config_sha256"].eq(model_config_hash()).all():raise ValueError("Stale model configuration in forecast: "+str(path))
            vol=pd.read_parquet(ROOT/("outputs/volatility_holdout" if args.final_holdout else "outputs/volatility")/f"{symbol}_{model}.parquet")
            ok=vol["status"].eq("ok")
            np.testing.assert_allclose(vol.loc[ok,"sigma_pct"]**2,vol.loc[ok,"variance_pct2"],rtol=1e-10)
            if not vol.loc[vol.horizon_days.eq(7),"student_t_scale_pct"].isna().all():raise ValueError("Do not label aggregate h7 return as exact Student-t")
            result_checks.append({"symbol":symbol,"model":model,"rows":len(forecast),
                "successful":int(forecast.status.eq("ok").sum()),"forecast_sha256":sha256(path)})
    result={"status":"passed","protocol_sha256":protocol_hash(config),"dataset_sha256":meta["dataset_sha256"],
        "model_config_sha256":model_config_hash(),"checks":result_checks,"garch_unique_fits":len(fits),
        "garch_failed_fits":int(fits.fit_status.ne("ok").sum()),"max_library_recursion_difference":float(successful.max_arch_forecast_difference.max()),
        "sigma_handoff_verified":True,"combined_variances_not_sigmas":True,"holdout_scored":args.final_holdout,
        "external_independent_review":"pending_team_review"}
    save_json(directory/"backend2_validation.json",result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":main()
