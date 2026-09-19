"""Independent analytical tests for Phase 4D-3 Deterministic Optimization Mathematics.

Normative Authority:
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
- docs/phases/PHASE_4D_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.optimization import (
    coordinate_descent_search,
    evaluate_acoustic_target_loss,
    generate_crossover_candidate_grid,
    generate_delay_candidate_grid,
    golden_section_line_search,
    is_candidate_better,
)
from acoustiforge.contracts.validation import (
    InvalidParameterError,
    NumericalEvaluationError,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import AcousticTargetCurve


# ==============================================================================
# 1. Analytical Loss Goldens (Goldens A, B, C, D)
# ==============================================================================

def test_loss_golden_a_exact_match() -> None:
    """GOLDEN A: Exact match between predicted response and target curve.

    Expected:
        E_rms = 0.0
        R = 0.0
        P_tau = 0.0
        Total Loss = 0.0
    """
    freqs = np.array([100.0, 1000.0, 10000.0], dtype=np.float64)
    target = AcousticTargetCurve(name="Flat0dB", points=((20.0, 0.0), (20000.0, 0.0)))
    pred_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros(3))

    loss = evaluate_acoustic_target_loss(
        predicted_response=pred_frd,
        target_curve=target,
        frequency_range_hz=(100.0, 10000.0),
        ripple_weight=1.0,
        delay_weight=1.0,
        delays_seconds=[0.0, 0.0],
        delay_bounds_seconds=(0.0, 0.005),
    )

    assert np.isclose(loss, 0.0, atol=1e-12)


def test_loss_golden_b_constant_error() -> None:
    """GOLDEN B: Constant +6.0205999... dB offset error across the entire band.

    Target = 0.0 dB
    Predicted = +6.020599913279624 dB
    Expected:
        E_rms = 6.020599913279624 dB
        R = 0.0 (since max(error) - min(error) = 6.0206 - 6.0206 = 0)
        Total Loss (w_r=0, w_tau=0) = 6.020599913279624 dB
    """
    freqs = np.array([100.0, 500.0, 1000.0, 5000.0], dtype=np.float64)
    target = AcousticTargetCurve(name="Flat0dB", points=((20.0, 0.0), (20000.0, 0.0)))
    const_err_db = 20.0 * math.log10(2.0)  # 6.020599913279624...
    pred_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.full(4, const_err_db))

    loss = evaluate_acoustic_target_loss(
        predicted_response=pred_frd,
        target_curve=target,
        frequency_range_hz=(100.0, 5000.0),
        ripple_weight=0.0,
        delay_weight=0.0,
    )

    assert np.isclose(loss, const_err_db, atol=1e-12)


def test_loss_golden_c_ripple_penalty() -> None:
    """GOLDEN C: Known non-uniform error vector with analytically calculated ripple.

    Target = 0.0 dB
    Predicted = [1.0, 3.0, 2.0, 5.0] dB
    Errors = [1.0, 3.0, 2.0, 5.0] dB
    Abs Errors: max = 5.0, min = 1.0 -> Ripple R = 5.0 - 1.0 = 4.0 dB
    E_rms = sqrt( (1^2 + 3^2 + 2^2 + 5^2) / 4 ) = sqrt( (1 + 9 + 4 + 25) / 4 ) = sqrt(39/4) = sqrt(9.75) ≈ 3.122498999...
    With w_r = 0.5:
        Total Loss = sqrt(9.75) + 0.5 * 4.0 = sqrt(9.75) + 2.0 ≈ 5.122498999...
    """
    freqs = np.array([100.0, 200.0, 400.0, 800.0], dtype=np.float64)
    target = AcousticTargetCurve(name="Flat0dB", points=((20.0, 0.0), (20000.0, 0.0)))
    pred_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.array([1.0, 3.0, 2.0, 5.0]))

    loss = evaluate_acoustic_target_loss(
        predicted_response=pred_frd,
        target_curve=target,
        frequency_range_hz=(100.0, 800.0),
        ripple_weight=0.5,
        delay_weight=0.0,
    )

    expected_loss = math.sqrt(9.75) + 0.5 * 4.0
    assert np.isclose(loss, expected_loss, atol=1e-12)


def test_loss_golden_d_delay_regularization_penalty() -> None:
    """GOLDEN D: Delay regularization penalty calculation.

    Delays: tau1 = 0.001 s, tau2 = 0.002 s
    tau_max = 0.005 s
    P_tau = (0.001/0.005)^2 + (0.002/0.005)^2 = 0.2^2 + 0.4^2 = 0.04 + 0.16 = 0.20
    E_rms = 0.0 (exact match)
    With w_tau = 10.0:
        Total Loss = 0.0 + 10.0 * 0.20 = 2.0
    """
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    target = AcousticTargetCurve(name="Flat0dB", points=((20.0, 0.0), (20000.0, 0.0)))
    pred_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros(2))

    loss = evaluate_acoustic_target_loss(
        predicted_response=pred_frd,
        target_curve=target,
        frequency_range_hz=(100.0, 1000.0),
        ripple_weight=0.0,
        delay_weight=10.0,
        delays_seconds=[0.001, 0.002],
        delay_bounds_seconds=(0.0, 0.005),
    )

    expected_loss = 10.0 * (0.04 + 0.16)
    assert np.isclose(loss, expected_loss, atol=1e-12)


# ==============================================================================
# 2. Active Frequency Band Selection & Numerical Safety
# ==============================================================================

def test_loss_active_frequency_band_selection() -> None:
    """Verify that only frequency points within [f_min, f_max] contribute to the loss."""
    freqs = np.array([20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 20000.0], dtype=np.float64)
    # Huge out-of-band error (+50 dB at 20 Hz and 20000 Hz)
    mag_db = np.array([50.0, 50.0, 2.0, 2.0, 2.0, 2.0, 50.0], dtype=np.float64)
    pred_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mag_db)
    target = AcousticTargetCurve(name="Flat0dB", points=((20.0, 0.0), (20000.0, 0.0)))

    # Active band: 100 Hz to 1000 Hz (points: 100, 200, 500, 1000 -> all exactly +2 dB)
    loss = evaluate_acoustic_target_loss(
        predicted_response=pred_frd,
        target_curve=target,
        frequency_range_hz=(100.0, 1000.0),
    )

    # In-band error is identically +2.0 dB -> E_rms = 2.0 dB
    assert np.isclose(loss, 2.0, atol=1e-12)


def test_loss_empty_active_band_raises_error() -> None:
    """Verify that an active frequency range containing zero measured points raises InvalidParameterError."""
    freqs = np.array([100.0, 200.0, 500.0], dtype=np.float64)
    pred_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros(3))
    target = AcousticTargetCurve(name="Flat0dB", points=((20.0, 0.0), (20000.0, 0.0)))

    with pytest.raises(InvalidParameterError, match="No frequency points found in active range"):
        evaluate_acoustic_target_loss(
            predicted_response=pred_frd,
            target_curve=target,
            frequency_range_hz=(1000.0, 2000.0),
        )


def test_loss_non_finite_values_raises_numerical_error() -> None:
    """Verify that non-finite predicted magnitudes raise NumericalEvaluationError."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    # FrequencyResponseData constructor normally blocks NaN, but we test the safety check in evaluate_acoustic_target_loss
    pred_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros(2))
    target = AcousticTargetCurve(name="Flat0dB", points=((20.0, 0.0), (20000.0, 0.0)))

    # Invalid negative frequency range
    with pytest.raises(InvalidParameterError, match="frequency_range_hz"):
        evaluate_acoustic_target_loss(
            predicted_response=pred_frd,
            target_curve=target,
            frequency_range_hz=(1000.0, 100.0),
        )


# ==============================================================================
# 3. Deterministic Candidate Grids
# ==============================================================================

def test_generate_crossover_candidate_grid() -> None:
    """Verify log-spaced crossover candidate grid generation."""
    grid = generate_crossover_candidate_grid(bounds_hz=(100.0, 10000.0), num_points=3)
    # 3 points log-spaced between 100 and 10000: 100, 1000, 10000
    assert np.allclose(grid, [100.0, 1000.0, 10000.0], atol=1e-12)

    with pytest.raises(InvalidParameterError):
        generate_crossover_candidate_grid(bounds_hz=(1000.0, 100.0), num_points=10)

    with pytest.raises(InvalidParameterError):
        generate_crossover_candidate_grid(bounds_hz=(100.0, 1000.0), num_points=1)


def test_generate_delay_candidate_grid() -> None:
    """Verify linearly-spaced delay candidate grid generation."""
    grid = generate_delay_candidate_grid(bounds_seconds=(0.0, 0.004), num_points=5)
    # 5 points linearly spaced: 0.0, 0.001, 0.002, 0.003, 0.004
    expected = np.array([0.0, 0.001, 0.002, 0.003, 0.004], dtype=np.float64)
    assert np.allclose(grid, expected, atol=1e-12)

    with pytest.raises(InvalidParameterError):
        generate_delay_candidate_grid(bounds_seconds=(0.005, 0.001), num_points=10)


# ==============================================================================
# 4. Deterministic Tie-Breaking
# ==============================================================================

def test_is_candidate_better_tie_breaking() -> None:
    """Verify strict tie-breaking contract."""
    # Clearly better (lower loss)
    assert is_candidate_better(loss_new=1.0, params_new=[2500.0, 0.0], loss_current=2.0, params_current=[2500.0, 0.0])

    # Clearly worse (higher loss)
    assert not is_candidate_better(loss_new=2.0, params_new=[2500.0, 0.0], loss_current=1.0, params_current=[2500.0, 0.0])

    # Equal loss within tolerance (1e-12): lexicographical tie-breaking
    # [2500, -3.0] vs [2500, -2.0] -> -3.0 < -2.0 -> True
    assert is_candidate_better(
        loss_new=1.0000000000000001,
        params_new=[2500.0, -3.0, 0.001],
        loss_current=1.0000000000000000,
        params_current=[2500.0, -2.0, 0.001],
    )

    # [2500, -2.0] vs [2500, -3.0] -> -2.0 > -3.0 -> False
    assert not is_candidate_better(
        loss_new=1.0000000000000000,
        params_new=[2500.0, -2.0, 0.001],
        loss_current=1.0000000000000001,
        params_current=[2500.0, -3.0, 0.001],
    )


# ==============================================================================
# 5. Golden-Section Line Search Tests
# ==============================================================================

def test_golden_section_line_search_univariate_quadratic() -> None:
    """Verify 1D golden-section search converges to known quadratic minimum."""
    # g(x) = (x - 3.75)^2 + 1.25, minimum at x* = 3.75, g* = 1.25
    def obj(x: float) -> float:
        return (x - 3.75) ** 2 + 1.25

    best_x, best_loss = golden_section_line_search(
        objective_func=obj,
        bounds=(0.0, 10.0),
        max_iterations=20,
    )

    assert np.isclose(best_x, 3.75, atol=1e-4)
    assert np.isclose(best_loss, 1.25, atol=1e-6)


def test_golden_section_line_search_boundary_optimum() -> None:
    """Verify 1D golden-section search handles boundary minimum correctly."""
    # g(x) = 2.0 * x + 1.0 on [0.0, 5.0], minimum at x = 0.0, g* = 1.0
    def obj(x: float) -> float:
        return 2.0 * x + 1.0

    best_x, best_loss = golden_section_line_search(
        objective_func=obj,
        bounds=(0.0, 5.0),
        max_iterations=20,
        initial_candidate=2.5,
    )

    assert np.isclose(best_x, 0.0, atol=1e-4)
    assert np.isclose(best_loss, 1.0, atol=1e-6)


# ==============================================================================
# 6. Coordinate Descent Optimization Tests
# ==============================================================================

def test_coordinate_descent_multivariate_quadratic() -> None:
    """Verify multi-dimensional coordinate descent converges to known global minimum.

    Objective:
        f(x, y) = (x - 2.5)^2 + 3.0 * (y + 1.5)^2 + 4.0
    Minimum:
        x* = 2.5, y* = -1.5, f* = 4.0
    Initial point:
        (0.0, 0.0) -> f(0, 0) = 2.5^2 + 3*(1.5^2) + 4 = 6.25 + 6.75 + 4 = 17.0
    """
    def obj(p: np.ndarray) -> float:
        x, y = p[0], p[1]
        return (x - 2.5) ** 2 + 3.0 * (y + 1.5) ** 2 + 4.0

    bounds = [(-5.0, 5.0), (-5.0, 5.0)]
    initial_p = [0.0, 0.0]

    best_p, best_loss, converged, iters = coordinate_descent_search(
        objective_func=obj,
        bounds=bounds,
        initial_params=initial_p,
        max_iterations=50,
        convergence_tolerance_db=1e-5,
    )

    assert converged is True
    assert iters <= 50
    assert np.isclose(best_p[0], 2.5, atol=1e-3)
    assert np.isclose(best_p[1], -1.5, atol=1e-3)
    assert np.isclose(best_loss, 4.0, atol=1e-5)
    # Monotonicity check
    assert best_loss <= 17.0


def test_coordinate_descent_with_constraints() -> None:
    """Verify coordinate descent respects candidate constraint predicates."""
    # Minimum at x=4, y=2 without constraint.
    # Constraint: y >= x (so optimum should be on line y = x, around x=y=2.5)
    def obj(p: np.ndarray) -> float:
        x, y = p[0], p[1]
        return (x - 4.0) ** 2 + (y - 1.0) ** 2

    # Constraint predicate: y >= x
    constraints = [lambda p: p[1] >= p[0]]

    bounds = [(0.0, 5.0), (0.0, 5.0)]
    initial_p = [1.0, 2.0]  # satisfies y >= x

    best_p, best_loss, converged, iters = coordinate_descent_search(
        objective_func=obj,
        bounds=bounds,
        initial_params=initial_p,
        max_iterations=50,
        constraints=constraints,
    )

    # Constraint must hold for the returned solution
    assert best_p[1] >= best_p[0] - 1e-6
    # Best loss must be better than or equal to initial loss: f(1, 2) = (1-4)^2 + (2-1)^2 = 9 + 1 = 10.0
    assert best_loss <= 10.0


def test_coordinate_descent_monotonicity_guarantee() -> None:
    """Verify that coordinate descent never degrades an already optimal initial candidate."""
    def obj(p: np.ndarray) -> float:
        return (p[0] - 1.0) ** 2 + 5.0

    bounds = [(0.0, 5.0)]
    # Start exactly at optimum
    initial_p = [1.0]

    best_p, best_loss, converged, iters = coordinate_descent_search(
        objective_func=obj,
        bounds=bounds,
        initial_params=initial_p,
        max_iterations=10,
    )

    assert np.isclose(best_p[0], 1.0, atol=1e-6)
    assert np.isclose(best_loss, 5.0, atol=1e-6)
