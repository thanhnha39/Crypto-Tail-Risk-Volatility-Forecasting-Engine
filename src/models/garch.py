"""arch Student-t GARCH/GJR fits with causal state updates between calendar refits."""
import hashlib
import json
import warnings
import numpy as np
import pandas as pd
from arch import arch_model
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox,het_arch
from src.evaluation.walkforward import BaseModel,ModelFitError,ModelForecastError
from src.models.config import load_model_config

def variance_path(params,last_variance,last_residual,horizon=7):
    omega=params["omega"];alpha=params["alpha[1]"];beta=params["beta[1]"];gamma=params.get("gamma[1]",0.)
    persistence=alpha+beta+gamma/2
    first=omega+(alpha+gamma*(last_residual<0))*last_residual**2+beta*last_variance
    path=[float(first)]
    for _ in range(1,horizon): path.append(float(omega+persistence*path[-1]))
    if not np.isfinite(path).all() or np.any(np.asarray(path)<=0): raise ModelForecastError("Nonpositive/nonfinite conditional variance")
    return np.asarray(path)

def forecast_filter_state(result):
    """Use the final-parameter backcast used by arch's public forecast method.

    result.conditional_volatility can retain the optimizer's initial backcast.
    That difference need not decay away when beta is close to one.
    """
    residuals=np.asarray(result.resid,dtype=float)
    volatility=result.model.volatility
    parameters=np.asarray([result.params[key] for key in volatility.parameter_names()])
    filtered=np.empty_like(residuals)
    volatility.compute_variance(parameters,residuals,filtered,
        volatility.backcast(residuals),volatility.variance_bounds(residuals,2.0))
    return float(filtered[-1]),float(residuals[-1])

def residual_diagnostics(result,options):
    z=np.asarray(result.std_resid,float);z=z[np.isfinite(z)]
    out={"standardized_residual_mean":float(z.mean()),"standardized_residual_variance":float(z.var(ddof=1))}
    for lag in options["diagnostic_lags"]:
        for values,label in [(z,"z"),(z*z,"z2")]:
            lb=acorr_ljungbox(values,lags=[lag],model_df=0,return_df=True)
            out[f"lb_{label}_{lag}_stat"]=float(lb.iloc[0,0]);out[f"lb_{label}_{lag}_p"]=float(lb.iloc[0,1])
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",message="acorr_lm currently returns",category=FutureWarning)
        lm=het_arch(z,nlags=options["arch_lm_lags"],ddof=len(result.params))
    out["arch_lm_stat"]=float(lm[0]);out["arch_lm_p"]=float(lm[1])
    nu=float(result.params["nu"])
    standardized_t=stats.t(df=nu,scale=np.sqrt((nu-2)/nu))
    out["student_t_ks_stat_descriptive"]=float(stats.kstest(z,standardized_t.cdf).statistic)
    out["fourth_moment_exists"]=nu>4
    return out

class StudentTGARCH(BaseModel):
    name="garch";asymmetry=0;features=["ret_d"];requires_target=False
    def __init__(self,cache=None,diagnostics=None,parameters=None,options=None):
        self.cache=cache if cache is not None else {};self.diagnostics=diagnostics;self.parameters=parameters
        self.options=options or load_model_config()["garch"]
    def fit(self,train,task):
        dates=pd.DatetimeIndex(train["origin_date"]);values=train["ret_d"].to_numpy(dtype=float)
        context=getattr(self,"context",{})
        signature=hashlib.sha256(values.tobytes()+dates.asi8.tobytes()+json.dumps(self.options,sort_keys=True).encode()+self.name.encode()).hexdigest()
        cache_key=(self.name,signature)
        record=self.cache.get(cache_key)
        if record is not None and "error" in record:raise ModelFitError(record["error"])
        if record is None:
            result=None;messages=[]
            try:
                if not np.isfinite(values).all() or not dates.to_series().diff().dropna().eq(pd.Timedelta(days=1)).all():
                    raise ModelFitError("GARCH needs consecutive observed daily returns; calendar gaps are not compressed")
                model=arch_model(pd.Series(values,index=dates),mean="Constant",vol="GARCH",p=1,o=self.asymmetry,q=1,
                    power=2.0,dist="t",rescale=False)
                attempts=0
                for limit in [self.options["max_iterations"],self.options["retry_max_iterations"]]:
                    attempts+=1
                    # Deterministic feasible restart using training observations only.
                    # Reusing a failed boundary solution often repeats line-search failure.
                    restart=[float(values.mean()),float(values.var()*.05),.05]
                    if self.asymmetry:restart.append(.05)
                    restart.extend([.85,8.])
                    with warnings.catch_warnings(record=True) as caught:
                        result=model.fit(update_freq=0,disp="off",show_warning=False,cov_type="robust",
                            starting_values=None if attempts==1 else np.asarray(restart),
                            options={"maxiter":limit,"ftol":self.options["optimizer_tolerance"]})
                    messages.extend(str(item.message) for item in caught)
                    if result.convergence_flag==0: break
                if result.convergence_flag!=0: raise ModelFitError(f"Optimizer did not converge: {result.optimization_result.message}")
                params={key:float(value) for key,value in result.params.items()}
                gamma=params.get("gamma[1]",0.);persistence=params["alpha[1]"]+params["beta[1]"]+gamma/2
                tol=1e-7
                admissible=(params["omega"]>0 and params["alpha[1]"]>=-tol and params["beta[1]"]>=-tol
                    and params["alpha[1]"]+gamma>=-tol and persistence<=1+tol and params["nu"]>2)
                if not admissible: raise ModelFitError("Estimated parameters violate variance constraints")
                last_variance,last_residual=forecast_filter_state(result)
                forecast=variance_path(params,last_variance,last_residual,7)
                reference=result.forecast(horizon=7,method="analytic",reindex=False).variance.to_numpy()[-1]
                if self.options["verify_arch_analytic"] and not np.allclose(forecast,reference,rtol=1e-8,atol=1e-8):
                    raise ModelFitError("Recursion differs from arch analytical forecast")
                diagnostic={"symbol":context.get("symbol",str(train["symbol"].iloc[0])),"model":self.name,
                    "window":context.get("window","unspecified"),"refit_origin":context.get("refit_origin",dates[-1]),
                    "train_start":context.get("train_start",dates[0]),"train_end":dates[-1],"n_train":len(values),
                    "convergence_flag":int(result.convergence_flag),"fit_status":"ok","attempts":attempts,
                    "optimizer_message":str(result.optimization_result.message),"loglikelihood":float(result.loglikelihood),
                    "aic":float(result.aic),"bic":float(result.bic),"persistence":persistence,
                    "finite_unconditional_variance":persistence<1,
                    "near_integrated":persistence>=1-self.options["stationarity_warning_tolerance"],
                    "return_scale":"percent_log_return","arch_rescale":float(result.scale),
                    "state_initialization":"final_parameter_backcast_as_arch_forecast",
                    "fitted_vs_forecast_filter_last_variance_difference":float(last_variance-np.asarray(result.conditional_volatility)[-1]**2),
                    "max_arch_forecast_difference":float(np.max(np.abs(forecast-reference))),"warnings":" | ".join(messages),
                    **params,**residual_diagnostics(result,self.options)}
                covariance=result.param_cov.to_numpy()
                diagnostic["covariance_finite"]=bool(np.isfinite(covariance).all())
                if self.parameters is not None:
                    for parameter,value in params.items():
                        self.parameters.append({key:diagnostic[key] for key in ["symbol","model","window","refit_origin"]}|{
                            "parameter":parameter,"estimate":value,"robust_std_error":float(result.std_err[parameter]),
                            "t_value":float(result.tvalues[parameter]),"p_value":float(result.pvalues[parameter])})
                record={"params":params,"last_variance":last_variance,"last_residual":last_residual,
                    "last_date":dates[-1],"signature":signature,"diagnostic":diagnostic}
                self.cache[cache_key]=record
                if self.diagnostics is not None:self.diagnostics.append(diagnostic)
            except (ValueError,FloatingPointError,np.linalg.LinAlgError,ModelFitError) as error:
                self.cache[cache_key]={"error":str(error)}
                if self.diagnostics is not None:self.diagnostics.append({"symbol":context.get("symbol",""),"model":self.name,
                    "window":context.get("window",""),"refit_origin":context.get("refit_origin",dates[-1]),
                    "n_train":len(values),"fit_status":"failed","optimizer_message":str(error)})
                raise ModelFitError(str(error)) from error
        self.params=record["params"].copy();self.state_variance=record["last_variance"]
        self.state_residual=record["last_residual"];self.state_date=record["last_date"]
        self.fit_signature=record["signature"];self.fit_record=record
        return self
    def predict(self,test,task,history=None):
        if history is None:raise ModelForecastError("Known daily history is required for conditional-state updates")
        outputs=[]
        for _,row in test.iterrows():
            origin=row["origin_date"]
            if origin<self.state_date:raise ModelForecastError("Cannot rewind a conditional state")
            updates=history.loc[history["origin_date"].gt(self.state_date)&history["origin_date"].le(origin)].sort_values("origin_date")
            for _,update in updates.iterrows():
                if update["origin_date"]!=self.state_date+pd.Timedelta(days=1) or not np.isfinite(update["ret_d"]):
                    raise ModelForecastError("Missing return in conditional-state history")
                self.state_variance=float(variance_path(self.params,self.state_variance,self.state_residual,1)[0])
                self.state_residual=float(update["ret_d"]-self.params["mu"]);self.state_date=update["origin_date"]
            if self.state_date!=origin:raise ModelForecastError("Conditional state has not reached the origin")
            self.path=variance_path(self.params,self.state_variance,self.state_residual,7)
            outputs.append(float(self.path[:task.horizon].sum()))
        return np.asarray(outputs)
    def forecast_metadata(self,task):
        sigma=float(np.sqrt(self.path[:task.horizon].sum()));nu=self.params["nu"]
        return {"mean_forecast_pct":task.horizon*self.params["mu"],"nu":nu,
            "innovation_distribution":"standardized_student_t" if task.horizon==1 else "aggregate_not_exact_student_t",
            "student_t_scale_pct":sigma*np.sqrt((nu-2)/nu) if task.horizon==1 else np.nan,
            "variance_path_pct2":self.path[:task.horizon].tolist(),"fit_signature":self.fit_signature,
            "variance_is_sum":True,"mean_convention":"constant_daily_mean_times_horizon"}

class StudentTGJR(StudentTGARCH):
    name="gjr_garch";asymmetry=1
