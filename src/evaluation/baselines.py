"""Naive checks plus a transparent OLS HAR reference; no GARCH/XGBoost stand-ins."""
import numpy as np
from src.evaluation.walkforward import BaseModel
from src.features.schema import HAR_COLS,HAR_LOG_COLS

class NaiveRW(BaseModel):
    name="naive_rw";features=["rv_d"]
    def fit(self,train,task): return self
    def predict(self,test,task,history=None): return test["rv_d"].to_numpy()*task.horizon

class HistMean(BaseModel):
    name="hist_mean";features=[]
    def fit(self,train,task): self.mean=float(train[task.y_col].mean());return self
    def predict(self,test,task,history=None): return np.full(len(test),self.mean)

class HARRV(BaseModel):
    name="har_rv";features=HAR_COLS
    def fit(self,train,task):
        x=np.column_stack([np.ones(len(train)),train[self.features].to_numpy()])
        self.beta=np.linalg.lstsq(x,train[task.y_col].to_numpy(),rcond=None)[0]
        self.floor=1e-10
        return self
    def predict(self,test,task,history=None):
        x=np.column_stack([np.ones(len(test)),test[self.features].to_numpy()])
        return np.maximum(x@self.beta,self.floor)

BASELINES={model.name:model for model in [NaiveRW,HistMean,HARRV]}
