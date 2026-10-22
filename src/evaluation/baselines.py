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

from src.models.har import HARRV

BASELINES={model.name:model for model in [NaiveRW,HistMean,HARRV]}
