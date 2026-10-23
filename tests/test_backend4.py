"""Unit tests for Backend 4: VaR/ES metrics and backtest statistics.

Tests use simulated data with analytically known violation rates so that
the correct answers are unambiguous. All tests import only from the public
``src.risk`` package surface.

Convention (enforced by tests below):
  - ``var`` and ``es`` are negative numbers (lower-tail quantiles in %).
  - ``breach = 1`` when ``return < var``.
"""

import unittest
import numpy as np

from src.risk.metrics import (
    christoffersen_test,
    expected_shortfall,
    kupiec_test,
    quantile_loss,
    value_at_risk,
)


RNG = np.random.default_rng(42)
N_LARGE = 250_000          # large enough for 0.5 %-point tolerance on breach rate
N_MEDIUM = 10_000


# ---------------------------------------------------------------------------
# 1. Sign and ordering: VaR and ES must be negative; ES <= VaR
# ---------------------------------------------------------------------------

class TestSignAndOrdering(unittest.TestCase):

    def _check(self, method, **kwargs):
        mean, sigma, alpha = 0.0, 1.0, 0.05
        var = value_at_risk(mean, sigma, alpha, method=method, **kwargs)
        es  = expected_shortfall(mean, sigma, alpha, method=method, **kwargs)
        self.assertLess(var, 0.0, f"{method}: VaR must be negative")
        self.assertLess(es,  0.0, f"{method}: ES must be negative")
        self.assertLessEqual(es, var + 1e-12, f"{method}: ES must be <= VaR")

    def test_normal_sign(self):
        self._check("normal")

    def test_student_t_sign(self):
        self._check("student_t", nu=5.0)

    def test_fhs_sign(self):
        z = RNG.standard_normal(500)
        self._check("fhs", residuals=z)

    def test_sign_at_alpha_01(self):
        """Same checks at the 1 % level."""
        for method, kw in [("normal", {}), ("student_t", {"nu": 7.0})]:
            var = value_at_risk(0, 1, 0.01, method=method, **kw)
            es  = expected_shortfall(0, 1, 0.01, method=method, **kw)
            self.assertLess(var, 0.0)
            self.assertLess(es, 0.0)
            self.assertLessEqual(es, var + 1e-12)


# ---------------------------------------------------------------------------
# 2. Normal VaR/ES: empirical breach rate matches alpha
# ---------------------------------------------------------------------------

class TestNormalBreachRate(unittest.TestCase):

    def _empirical_breach_rate(self, alpha, mean=0.0, sigma=1.0):
        returns = RNG.normal(mean, sigma, N_LARGE)
        var = value_at_risk(mean, sigma, alpha, method="normal")
        return np.mean(returns < var)

    def test_95pct_breach_rate(self):
        rate = self._empirical_breach_rate(0.05)
        self.assertAlmostEqual(rate, 0.05, delta=0.005)

    def test_99pct_breach_rate(self):
        rate = self._empirical_breach_rate(0.01)
        self.assertAlmostEqual(rate, 0.01, delta=0.005)

    def test_nonzero_mean_breach_rate(self):
        rate = self._empirical_breach_rate(0.05, mean=0.1, sigma=2.0)
        self.assertAlmostEqual(rate, 0.05, delta=0.005)


# ---------------------------------------------------------------------------
# 3. Student-t VaR/ES: empirical breach rate matches alpha (fat tails)
# ---------------------------------------------------------------------------

class TestStudentTBreachRate(unittest.TestCase):

    def _simulate_t_returns(self, nu, n):
        # standardized t(nu) has std = 1 when nu > 2
        t_std = np.sqrt((nu - 2) / nu)
        z = RNG.standard_t(nu, size=n) * t_std   # unit-variance Student-t
        return z

    def test_95pct_breach_rate_t5(self):
        nu = 5.0; sigma = 1.0; mean = 0.0
        returns = self._simulate_t_returns(nu, N_LARGE)
        var = value_at_risk(mean, sigma, 0.05, method="student_t", nu=nu)
        rate = np.mean(returns < var)
        self.assertAlmostEqual(rate, 0.05, delta=0.005)

    def test_99pct_breach_rate_t7(self):
        nu = 7.0; sigma = 1.0; mean = 0.0
        returns = self._simulate_t_returns(nu, N_LARGE)
        var = value_at_risk(mean, sigma, 0.01, method="student_t", nu=nu)
        rate = np.mean(returns < var)
        self.assertAlmostEqual(rate, 0.01, delta=0.005)

    def test_invalid_nu_raises(self):
        with self.assertRaises((ValueError, Exception)):
            value_at_risk(0, 1, 0.05, method="student_t", nu=1.5)


# ---------------------------------------------------------------------------
# 4. FHS VaR/ES: uses empirical quantile of provided residuals
# ---------------------------------------------------------------------------

class TestFHSBreachRate(unittest.TestCase):

    def test_empirical_quantile_consistency(self):
        """FHS VaR should match numpy empirical quantile of residuals."""
        rng = np.random.default_rng(0)
        z = rng.standard_normal(1000)
        mean, sigma, alpha = 0.0, 2.0, 0.05
        var = value_at_risk(mean, sigma, alpha, method="fhs", residuals=z)
        expected = mean + sigma * np.quantile(z, alpha)
        self.assertAlmostEqual(var, expected, places=10)

    def test_fhs_breach_rate_normal_residuals(self):
        """If residuals are N(0,1) and we predict N(0,1) returns, breach ≈ alpha."""
        rng = np.random.default_rng(1)
        z_train = rng.standard_normal(5000)     # training residuals
        returns  = rng.standard_normal(N_MEDIUM)
        mean, sigma = 0.0, 1.0
        var = value_at_risk(mean, sigma, 0.05, method="fhs", residuals=z_train)
        rate = np.mean(returns < var)
        self.assertAlmostEqual(rate, 0.05, delta=0.01)

    def test_fhs_raises_without_residuals(self):
        with self.assertRaises((ValueError, Exception)):
            value_at_risk(0, 1, 0.05, method="fhs")

    def test_fhs_raises_too_few_residuals(self):
        with self.assertRaises((ValueError, Exception)):
            value_at_risk(0, 1, 0.05, method="fhs", residuals=np.ones(5))


# ---------------------------------------------------------------------------
# 5 & 6. Kupiec test: accept correct rate, reject wrong rate
# ---------------------------------------------------------------------------

class TestKupiecTest(unittest.TestCase):

    @staticmethod
    def _make_breaches(n, k):
        b = np.zeros(n, dtype=bool)
        b[:k] = True
        return b

    def test_accepts_correct_rate(self):
        """50 breaches out of 1000 at alpha=0.05 → should NOT reject (high p-value)."""
        b = self._make_breaches(1000, 50)
        result = kupiec_test(b, 0.05)
        self.assertGreater(result["p_value"], 0.05,
                           "Kupiec should accept the correct violation rate")
        self.assertEqual(result["n_breach"], 50)

    def test_rejects_wrong_rate(self):
        """100 breaches out of 1000 at alpha=0.05 → should reject (low p-value)."""
        b = self._make_breaches(1000, 100)
        result = kupiec_test(b, 0.05)
        self.assertLess(result["p_value"], 0.05,
                        "Kupiec should reject when breach rate is double the expected")

    def test_rejects_zero_breaches_at_large_n(self):
        """0 breaches out of 500 at alpha=0.05 → strongly reject."""
        b = np.zeros(500, dtype=bool)
        result = kupiec_test(b, 0.05)
        self.assertLess(result["p_value"], 0.01)

    def test_empty_series_returns_nan(self):
        result = kupiec_test(np.array([]), 0.05)
        self.assertTrue(np.isnan(result["p_value"]))

    def test_breach_rate_matches_input(self):
        b = self._make_breaches(200, 10)
        result = kupiec_test(b, 0.05)
        self.assertAlmostEqual(result["breach_rate"], 10 / 200)


# ---------------------------------------------------------------------------
# 7 & 8. Christoffersen test: accept i.i.d., reject clustered breaches
# ---------------------------------------------------------------------------

class TestChristoffersenTest(unittest.TestCase):

    def test_accepts_independent_breaches(self):
        """i.i.d. Bernoulli(0.05) sequence should NOT reject independence."""
        rng = np.random.default_rng(7)
        b = rng.random(2000) < 0.05
        result = christoffersen_test(b, alpha=0.05)
        self.assertGreater(result["p_independence"], 0.05)

    def test_rejects_clustered_breaches(self):
        """A highly autocorrelated breach sequence should reject independence."""
        rng = np.random.default_rng(99)
        # Markov chain: once in breach state stay for ~10 days
        b = np.zeros(3000, dtype=bool)
        state = False
        for i in range(len(b)):
            if state:
                b[i] = True
                state = (rng.random() < 0.90)   # 90% chance to stay breaching
            else:
                state = (rng.random() < 0.005)  # rare entry
        result = christoffersen_test(b, alpha=0.05)
        self.assertLess(result["p_independence"], 0.05,
                        "Christoffersen should detect clustered breaches")

    def test_returns_all_expected_keys(self):
        b = np.array([True, False, False, True, True, False])
        result = christoffersen_test(b, alpha=0.05)
        for key in ("lr_independence", "p_independence", "p_value", "n00", "n01", "n10", "n11"):
            self.assertIn(key, result)

    def test_empty_sequence_returns_nan(self):
        result = christoffersen_test(np.array([]), alpha=0.05)
        self.assertTrue(np.isnan(result["p_value"]))


# ---------------------------------------------------------------------------
# 9. Breach convention: breach = 1 iff return < var
# ---------------------------------------------------------------------------

class TestBreachConvention(unittest.TestCase):

    def test_breach_is_one_when_return_below_var(self):
        """Exact threshold: return strictly less than var counts as breach."""
        var = -2.0   # negative as required
        returns = np.array([-3.0, -2.1, -2.0, -1.9, 0.5])
        expected = np.array([1, 1, 0, 0, 0], dtype=int)  # return < var (strict)
        computed = (returns < var).astype(int)
        np.testing.assert_array_equal(computed, expected)

    def test_breach_rate_equals_alpha_for_normal(self):
        """Aggregate breach rate on a large simulated dataset should equal alpha."""
        rng = np.random.default_rng(55)
        returns = rng.normal(0, 1, N_LARGE)
        var = value_at_risk(0.0, 1.0, 0.05, method="normal")
        self.assertLess(var, 0.0, "VaR must be negative")
        breach = (returns < var).astype(int)
        rate = breach.mean()
        self.assertAlmostEqual(rate, 0.05, delta=0.005)


# ---------------------------------------------------------------------------
# 10. FHS causal constraint: only past residuals must be used
# ---------------------------------------------------------------------------

class TestFHSPoolSensitivity(unittest.TestCase):

    def test_changing_input_pool_changes_quantile(self):
        """Pure-function sensitivity only. Actual causal filtering is tested in
        test_backend4_pipeline.TestPointInTimePipeline using _risk_rows.
        """
        rng = np.random.default_rng(123)
        past   = rng.standard_normal(300)        # normal past residuals
        future = np.full(100, -10.0)             # extreme future residuals
        mean, sigma, alpha = 0.0, 1.0, 0.05

        var_past_only  = value_at_risk(mean, sigma, alpha, method="fhs", residuals=past)
        var_past_future = value_at_risk(mean, sigma, alpha, method="fhs",
                                        residuals=np.concatenate([past, future]))
        # Including extreme future residuals should make VaR more negative
        self.assertLess(var_past_future, var_past_only,
                        "Adding extreme residuals should lower (make more negative) the FHS VaR")


# ---------------------------------------------------------------------------
# 11. Quantile loss: loss is non-negative and zero only at exact quantile
# ---------------------------------------------------------------------------

class TestQuantileLoss(unittest.TestCase):

    def test_loss_is_non_negative(self):
        rng = np.random.default_rng(0)
        returns = rng.normal(0, 1, 1000)
        var = np.full(1000, -1.645)
        loss = quantile_loss(returns, var, 0.05)
        self.assertTrue(np.all(loss >= 0), "Quantile loss must be non-negative")

    def test_loss_decreases_toward_correct_quantile(self):
        """Average loss is minimized when var = true alpha-quantile."""
        rng = np.random.default_rng(11)
        returns = rng.normal(0, 1, N_LARGE)
        var_true  = np.quantile(returns, 0.05)
        var_wrong = var_true + 0.5    # shifted up (underestimates tail)
        loss_true  = quantile_loss(returns, np.full(N_LARGE, var_true),  0.05).mean()
        loss_wrong = quantile_loss(returns, np.full(N_LARGE, var_wrong), 0.05).mean()
        self.assertLess(loss_true, loss_wrong)


if __name__ == "__main__":
    unittest.main(verbosity=2)
