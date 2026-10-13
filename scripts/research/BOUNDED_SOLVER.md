# Bounded solver check

The duration-weight experiment exposed an unbounded inner loop in SciPy's `trust-exact` subproblem. Its outer `maxiter=100` does not bound that loop. This is a numerical issue, not evidence for another statistical term or a different variance power.

## Protocol

Keep the interval mean, objective, penalties, initialization, counts and saved smoothing strengths unchanged. Check all 116 saved final fits (40 unweighted, 40 damped and 36 square-root-duration), then the 36 training-only smoothing/fold combinations from the four Honey Buzzard contexts that previously stalled. Do not review held-out gap accuracy during the numerical batch or use it to select the solver.

Newton-CG has bounded inner iterations in the installed SciPy implementation, but fails the existing high-count Poisson check: maximum gradient 0.0091 versus the unchanged 0.001 acceptance threshold. Reject it as the common implementation.

Test BFGS as one fixed solver, initially with 100 outer iterations and the existing gradient target 1e-5. Its installed line searches are bounded (first search 100 iterations, second search 10 iterations with a 10-iteration zoom); there is no unbounded trust-region subproblem. No model-level retry, optimizer ladder, tolerance relaxation or prediction fallback is added. See the official [BFGS documentation](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-bfgs.html).

Acceptance requires every fit to have maximum analytic gradient below 0.001 and directional derivative error below 0.001. Saved-fit comparisons additionally require relative objective difference below 1e-7 and maximum component-rate relative difference below 1e-5. Report solver status separately: a precision-loss message cannot be hidden by numerical acceptance. A numerical equivalence check compares all component rates, without scoring hidden counts. Record final runtimes and compare the paired saved-fit median against the five-times speed budget. Review only after the complete batch.

The first completed batch reproduces all 116 saved fits, but one of 36 formerly stalled CV fits reaches the 100-iteration cap at gradient 0.001211. Increase the fixed cap to 200 for all BFGS fits and repeat the complete batch. This changes a computational budget, not the acceptance threshold or statistical model; no gap accuracy was reviewed.

## Reproduce

```sh
mkdir -p logs/bounded-solver
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 uv run python scripts/research/check_bounded_solver.py > logs/bounded-solver/run.log 2>&1
```

Outputs are generated under `logs/bounded-solver/`. Production is unchanged.

## Completed results and decision

All 152 fits pass the unchanged numerical gates: 116 saved final fits and 36 training-only CV fits from the four stalled contexts. Saved final fits have median runtime 0.160 seconds, maximum 0.349 seconds; formerly stalled CV fits have median 0.177 seconds and maximum 0.352 seconds. Maximum iteration counts are 102 and 104, respectively, below the common 200 cap. Paired median runtime ratios versus saved exact-solver timings are 1.08 unweighted, 1.05 damped and 1.04 square-root-weighted; timings come from different runs and are approximate.

Maximum analytic gradient is 0.000219; maximum independent directional derivative error is 4.54e-8. Maximum saved objective relative difference is 4.12e-16 and maximum component-rate relative difference is 2.66e-6 (0.00027%). These checks establish numerical equivalence on this panel, not a global optimum guarantee.

SciPy reports success for 66 fits and precision loss for 86 fits; none reaches the new iteration limit. Keep these raw statuses visible. The independent gradient/derivative and saved-objective checks pass despite precision-loss messages; do not relabel them as solver-reported successes or relax tolerances.

Use bounded BFGS as the research fitter default. The archived episode, season and duration experiments explicitly retain their original exact solver for reproduction of their recorded results and coefficient assertions; these legacy commands can still stall and should use their existing process limits. Do not run them as the new development path. Independent Hessian checks explicitly request the old solver to expose the unchanged analytic Hessian.

The model, unweighted criterion and production exports are unchanged. Duration weighting remains rejected; no new gap-accuracy selection was performed here. The next scientific control is separating shared season and clock smoothing on the small model, with training-only selection and the same historical/recent acceptance gates. This is proposed, not implemented.

The existing independent exposure/derivative/high-count checks pass, and the repository suite passes all 104 tests.
