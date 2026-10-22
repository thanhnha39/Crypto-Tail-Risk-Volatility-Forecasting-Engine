"""HAR-RV OLS on the shared calendar; direct sum-variance forecasts at h=1 and h=7."""
import numpy as np
from src.evaluation.walkforward import BaseModel,ModelFitError
from src.features.schema import HAR_COLS

class HARRV(BaseModel):
    name="har_rv";features=HAR_COLS
    def __init__(self,diagnostics=None,floor=1e-10):
        self.diagnostics=diagnostics;self.floor=floor
    def fit(self,train,task):
        x=np.column_stack([np.ones(len(train)),train[self.features].to_numpy()]);y=train[task.y_col].to_numpy()
        self.beta,_,rank,_=np.linalg.lstsq(x,y,rcond=None)
        if rank<x.shape[1]: raise ModelFitError("Rank-deficient HAR design")
        if self.diagnostics is not None:
            row={k:self.context[k] for k in ["symbol","window","horizon_days","refit_origin","train_start","train_end"]}
            row.update(model=self.name,n_train=len(train),rank=int(rank),condition_number=float(np.linalg.cond(x)),
                intercept=float(self.beta[0]),rv_d_coef=float(self.beta[1]),rv_w_coef=float(self.beta[2]),rv_m_coef=float(self.beta[3]),
                residual_rmse=float(np.sqrt(np.mean((y-x@self.beta)**2))),variance_floor=self.floor)
            self.diagnostics.append(row)
        return self
    def predict(self,test,task,history=None):
        x=np.column_stack([np.ones(len(test)),test[self.features].to_numpy()])
        return np.maximum(x@self.beta,self.floor)
    def forecast_metadata(self,task):
        return {"mean_forecast_pct":0.0,"nu":np.nan,"innovation_distribution":"FHS_required",
            "student_t_scale_pct":np.nan,"variance_is_sum":True,"mean_convention":"zero_for_FHS_handoff"}
