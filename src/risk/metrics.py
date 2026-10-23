"""Tail-risk forecasts and unconditional/conditional coverage diagnostics.

Returns and forecasts use percentage points, matching the shared dataset.
VaR and ES are lower-tail (negative) return quantiles.
"""
import numpy as np
from scipy import stats


def _check_alpha(alpha):
    if not 0 < float(alpha) < 1:
        raise ValueError("alpha must be a probability strictly between zero and one")


def value_at_risk(mean, sigma, alpha, method="normal", nu=None, scale=None, residuals=None):
    """Return the lower-tail return quantile for a forecast distribution.

    ``sigma`` is the standard deviation in return units. Student-t innovations
    are standardized to unit variance unless an explicit ``scale`` is supplied.
    FHS uses an empirical distribution of standardized historical residuals.
    """
    _check_alpha(alpha)
    mean, sigma = np.asarray(mean, float), np.asarray(sigma, float)
    if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("sigma must contain positive finite values")
    if method == "normal":
        return mean + sigma * stats.norm.ppf(alpha)
    if method == "student_t":
        if nu is None or np.any(~np.isfinite(np.asarray(nu, float))) or np.any(np.asarray(nu, float) <= 2):
            raise ValueError("variance-standardized Student-t requires nu > 2")
        t_scale = np.asarray(scale, float) if scale is not None else sigma * np.sqrt((np.asarray(nu, float) - 2) / np.asarray(nu, float))
        return mean + t_scale * stats.t.ppf(alpha, df=nu)
    if method == "fhs":
        if residuals is None:
            raise ValueError("FHS requires historical standardized residuals")
        z = np.asarray(residuals, float)
        z = z[np.isfinite(z)]
        if z.size < 20:
            raise ValueError("FHS requires at least 20 finite historical residuals")
        return mean + sigma * np.quantile(z, alpha)
    raise ValueError("method must be normal, student_t or fhs")


def expected_shortfall(mean, sigma, alpha, method="normal", nu=None, scale=None, residuals=None):
    """Return expected return conditional on being at/below lower-tail VaR."""
    _check_alpha(alpha)
    mean, sigma = np.asarray(mean, float), np.asarray(sigma, float)
    if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("sigma must contain positive finite values")
    if method == "normal":
        z = stats.norm.ppf(alpha)
        return mean - sigma * stats.norm.pdf(z) / alpha
    if method == "student_t":
        nu_array = np.asarray(nu, float)
        if nu is None or np.any(~np.isfinite(nu_array)) or np.any(nu_array <= 2):
            raise ValueError("variance-standardized Student-t requires nu > 2")
        t_scale = np.asarray(scale, float) if scale is not None else sigma * np.sqrt((nu_array - 2) / nu_array)
        q = stats.t.ppf(alpha, df=nu)
        factor = ((nu_array + q * q) / (nu_array - 1)) * stats.t.pdf(q, df=nu) / alpha
        return mean - t_scale * factor
    if method == "fhs":
        if residuals is None:
            raise ValueError("FHS requires historical standardized residuals")
        z = np.asarray(residuals, float)
        z = z[np.isfinite(z)]
        if z.size < 20:
            raise ValueError("FHS requires at least 20 finite historical residuals")
        cutoff = np.quantile(z, alpha)
        tail = z[z <= cutoff]
        return mean + sigma * tail.mean()
    raise ValueError("method must be normal, student_t or fhs")


def _lr(p, q):
    """Bernoulli log likelihood ratio, with stable 0*log(0) limits."""
    p, q = np.clip(p, 1e-12, 1 - 1e-12), np.clip(q, 1e-12, 1 - 1e-12)
    return 2 * (q * np.log(q / p) + (1 - q) * np.log((1 - q) / (1 - p)))


def kupiec_test(breaches, alpha):
    """Kupiec unconditional coverage test; returns breach count and p-value."""
    _check_alpha(alpha)
    b = np.asarray(breaches, dtype=bool)
    n = b.size
    if n == 0:
        return {"n": 0, "n_breach": 0, "breach_rate": np.nan, "lr": np.nan, "p_value": np.nan}
    k = int(b.sum()); rate = k / n
    # The generalized likelihood ratio includes boundary cases k=0 and k=n.
    lr = float(2 * ((k * np.log(rate / alpha) if k else 0.0) +
                    ((n-k) * np.log((1-rate) / (1-alpha)) if k < n else 0.0)))
    return {"n": n, "n_breach": k, "breach_rate": rate, "lr": lr,
            "p_value": float(stats.chi2.sf(max(lr, 0), 1))}


def christoffersen_test(breaches, alpha=None, dates=None):
    """Independence/conditional coverage with no transitions across missing days.

    For gapped samples, UC uses all observations and independence uses only
    adjacent-day pairs. Chi-square p-values are asymptotic diagnostics.
    Degenerate transition tables return unavailable, rather than a false pass.
    """
    import pandas as pd
    raw = np.asarray(breaches, dtype=float)
    if raw.ndim != 1 or not np.isfinite(raw).all() or not np.isin(raw, [0, 1]).all():
        raise ValueError('Breaches must be a finite one-dimensional 0/1 series')
    b = raw.astype(bool)
    adjacent = np.ones(max(len(b)-1, 0), dtype=bool)
    if dates is not None:
        d = pd.DatetimeIndex(pd.to_datetime(dates, utc=True))
        if len(d) != len(b) or d.hasnans or d.has_duplicates or not d.is_monotonic_increasing:
            raise ValueError('Dates must be aligned, unique and sorted')
        adjacent = (d[1:] - d[:-1]) == pd.Timedelta(days=1)
    old, new = b[:-1][adjacent], b[1:][adjacent]
    n00 = int((~old & ~new).sum()); n01 = int((~old & new).sum())
    n10 = int((old & ~new).sum()); n11 = int((old & new).sum())
    result = dict(n00=n00, n01=n01, n10=n10, n11=n11,
        n_adjacent_pairs=int(adjacent.sum()), n_gaps=int((~adjacent).sum()),
        lr_independence=np.nan, p_independence=np.nan,
        lr_conditional_coverage=np.nan, p_value=np.nan, status='insufficient_transitions')
    if not (n00+n01 and n10+n11 and n01+n11 and n00+n10):
        return result
    def loglik(s, f):
        total=s+f
        return (s*np.log(s/total) if s else 0.) + (f*np.log(f/total) if f else 0.)
    lr_ind=max(0.,float(2*(loglik(n01,n00)+loglik(n11,n10)-loglik(n01+n11,n00+n10))))
    lr_uc=kupiec_test(b,alpha)['lr'] if alpha is not None else np.nan
    lr_cc=lr_ind+lr_uc
    result.update(lr_independence=lr_ind,p_independence=float(stats.chi2.sf(lr_ind,1)),
        lr_conditional_coverage=lr_cc,p_value=float(stats.chi2.sf(lr_cc,2)) if np.isfinite(lr_cc) else np.nan,
        status='asymptotic_gapped_sample' if result['n_gaps'] else 'ok')
    return result


def quantile_loss(realized, var, alpha):
    """Lower-quantile pinball loss, averaged over valid observations."""
    _check_alpha(alpha)
    y, q = np.asarray(realized, float), np.asarray(var, float)
    error = y - q
    return np.maximum(alpha * error, (alpha - 1) * error)
