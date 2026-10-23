"""Deterministic simulation smoke check for tail probabilities and coverage tests."""
import numpy as np
from scipy import stats
from src.risk.metrics import christoffersen_test, expected_shortfall, kupiec_test, value_at_risk


def check_simulation(n=250_000, seed=4104, tolerance=0.0025):
    rng=np.random.default_rng(seed)
    normal=rng.standard_normal(n)
    results=[]
    for alpha in (0.05, 0.01):
        q=float(value_at_risk(0.,1.,alpha,"normal"))
        es=float(expected_shortfall(0.,1.,alpha,"normal"))
        observed=float(np.mean(normal < q))
        if abs(observed-alpha)>tolerance: raise AssertionError(f"Normal breach rate {observed} differs from {alpha}")
        ntest=normal<q
        results.append({"distribution":"normal","alpha":alpha,"known_rate":alpha,"observed_rate":observed,"var":q,"es":es,
                        "kupiec_p":kupiec_test(ntest,alpha)["p_value"],
                        "christoffersen_p":christoffersen_test(ntest,alpha)["p_value"]})
        nu=7.; t_draw=rng.standard_t(nu,size=n)*np.sqrt((nu-2)/nu)
        tq=float(value_at_risk(0.,1.,alpha,"student_t",nu=nu))
        tes=float(expected_shortfall(0.,1.,alpha,"student_t",nu=nu))
        tobs=float(np.mean(t_draw<tq))
        if abs(tobs-alpha)>tolerance: raise AssertionError(f"Student-t breach rate {tobs} differs from {alpha}")
        ttest=t_draw<tq
        results.append({"distribution":"student_t","alpha":alpha,"known_rate":alpha,"observed_rate":tobs,"var":tq,"es":tes,
                        "kupiec_p":kupiec_test(ttest,alpha)["p_value"],
                        "christoffersen_p":christoffersen_test(ttest,alpha)["p_value"]})
        train=rng.standard_normal(300_000); holdout=rng.standard_normal(250_000)
        fq=float(value_at_risk(0.,1.,alpha,"fhs",residuals=train))
        fes=float(expected_shortfall(0.,1.,alpha,"fhs",residuals=train))
        fobs=float(np.mean(holdout<fq))
        if abs(fobs-alpha)>tolerance: raise AssertionError(f"FHS breach rate {fobs} differs from {alpha}")
        ftest=holdout<fq
        results.append({"distribution":"fhs_normal_innovations","alpha":alpha,"known_rate":alpha,
                        "observed_rate":fobs,"var":fq,"es":fes,"kupiec_p":kupiec_test(ftest,alpha)["p_value"],
                        "christoffersen_p":christoffersen_test(ftest,alpha)["p_value"]})
    return results


if __name__=="__main__":
    for record in check_simulation(): print(record)
