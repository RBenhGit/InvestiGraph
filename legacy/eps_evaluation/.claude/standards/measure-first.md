# Measure First — the performance investigation standard

> **Provenance.** Distilled from the CodeFundation wiki pages `agent-friendly-architecture`
> (restrained complexity: "optimize only against measured budgets") and `verification-loops`
> (evidence over assertion) — upstream: `maintainable-agentic-codebase`,
> `claude-docs-best-practices`, `karpathy-skills-claude-md`.
> The measurement procedure below is convention, not sourced fact.

## Contents

1. The rule
2. The four questions, in order
3. Measuring without lying to yourself
4. Choosing the one change
5. Reporting
6. Refusal cases

---

## 1. The rule

**No optimization without a measurement and a budget.** Premature optimization is one of the three
prematures the architecture standard names: structure distorted by speculation about cost. An
optimization that isn't measured is a complexity increase with a story attached.

A budget is a number with a unit and a source: *"p95 checkout latency ≤ 300 ms (SLO)"*,
*"CI test suite ≤ 6 min (it is 11 now and blocking the loop)"*, *"import of this module ≤ 50 ms
(startup budget)"*. "Faster" is not a budget. If the requester didn't give you one, derive a
candidate and get it confirmed before changing anything.

## 2. The four questions, in order

Answer each with evidence before moving to the next. Stopping early is a valid outcome — most
performance requests die at question 2, and that is a successful investigation.

1. **What is the budget, and by how much is it missed?** No budget → no work. Record the target,
   the current value, and the gap.
2. **Is it reproducible?** Build the smallest repeatable measurement: a benchmark, a load script,
   a timed command, a profiler run. Run it at least three times and record the spread. If the
   variance swamps the gap, the measurement is the deliverable — say so and stop.
3. **Where does the time/memory actually go?** Profile. Do not reason about hot paths from reading
   code — measure them. Report the top costs with their share.
4. **What is the smallest change that closes the gap?** One change. Then re-measure with the same
   harness from question 2.

## 3. Measuring without lying to yourself

- **Same machine, same state, same data.** Note anything that differs between runs.
- **Warm up.** Discard the first run on any runtime with a JIT, a cache, or lazy imports — or
  measure cold explicitly if cold start is the budget.
- **Report the spread, not one number.** Median plus min/max over ≥3 runs. A single number is not
  a measurement.
- **Measure the thing the budget is about.** A microbenchmark of a function that accounts for 2% of
  wall time answers nothing.
- **Isolate the variable.** One change per measurement, exactly as in mutation probing.
- **Keep the harness.** Commit the benchmark or the command so the next session can re-run it.
  An unrepeatable improvement cannot be defended against the next regression.
- **Watch for the observer effect** — profilers, debug builds, and verbose logging change what you
  are measuring. Confirm the headline number outside the profiler.

## 4. Choosing the one change

Prefer, in this order:

1. **Do less work** — remove a redundant call, cache a repeated computation with an explicit
   invalidation story, drop an N+1 query, avoid loading what isn't used.
2. **Do it at a better time** — defer, batch, or parallelize work that doesn't need to be on the
   critical path.
3. **Use a better algorithm or data structure** — where the complexity class is the actual problem.
4. **Tune the runtime/config** — pool sizes, indexes, compression. Cheap to try, cheap to revert.
5. **Rewrite hot code in a lower-level style** — last, because it costs the most readability per
   unit of speed.

Never trade correctness or clarity for a gain you have not measured. If the winning change makes
the code materially harder to read, say so explicitly in the report and let the human decide —
the simplicity principle outranks an unrequested speedup.

## 5. Reporting

- **Budget** — target, source, and the measured gap
- **Harness** — the exact command(s) to reproduce, committed where possible
- **Baseline** — median and spread over N runs
- **Profile** — top costs with their share of the total
- **Change** — the one change made, and why it was chosen over the alternatives
- **After** — median and spread from the *same* harness, plus the delta against the budget
- **Correctness** — the test run proving behavior is unchanged, with output
- **Residual** — what is still slow, and what the next investigation would look at

## 6. Refusal cases

Say so plainly and stop:

- No budget, and none can be agreed
- No reproducible measurement (variance ≥ the gap)
- The profile shows the cost is outside the code under discussion (network, third-party service,
  test-environment artifact)
- The only change that would close the gap requires a structural rewrite — hand that to the
  architecture reviewer with the profile attached; do not start it
