# When does a technician need a shaft reading?

The operator must decide whether a ventilation incident has recovered. The technician must decide what to inspect first. A device can acknowledge 95% opening while airflow stays low in both a travel-mismatch case and a case where the shaft reaches its setpoint. A flow meter alone cannot distinguish those two outcomes.

## Compare the decisions

The [case matrix](../scenarios/inspection-benchmark.json) defines the input and reference decision before the applications run. Nine designed cases are repeated in a cooking zone with a 900 m³/h target and a conservation workshop with a 560 m³/h target. Each case starts a fresh ACME database. Each site gets its own incident, damper, encoder binding and work order. At each site the paired low-flow examples use the **same** command, the same two airflow readings and the same control-reported position. Only the separately published virtual encoder value changes.

| Policy | Evidence available | Decision rule |
| --- | --- | --- |
| ACK only | CSE device acknowledgement | Treat an acknowledged command as recovered. Provides no technical first check. |
| Airflow only | Same ACK and fresh post-ACK airflow | Require the site's two most recent readings to meet its commissioned target. Retain a general inspection when additional investigation is needed. |
| openSoom | Same ACK, site observations and a separately mapped shaft sensor when needed | The operations service evaluates the facility profile. The maintenance worker requests shaft position only after qualifying low flow and uses a valid, settled measurement to prioritize actuator feedback or the airflow path. |

The first two rules are illustrative comparators computed on the **same actual oneM2M input records**. They represent two plausible information levels and make no claim about a competing product. The test driver never gives the reference decision to either application. Correct first checks follow the configured inspection rule. A technician must verify the underlying physical cause onsite.

## Observed results in 18 virtual runs

| Endpoint | ACK only | Airflow only | openSoom |
| --- | ---: | ---: | ---: |
| False recovery among cases requiring further investigation | 14/16 | 2/16 | 0/16 |
| Confirmed recovery missed | 0/2 | 0/2 | 0/2 |
| Specific first inspection matched the reference | 0/4 | 0/4 | 4/4 |
| Unsupported specific first inspection with missing or stale shaft input | 0/4 | 0/4 | 0/4 |

At the conservation workshop, both paired trials acknowledged the **same 95% setpoint** and recorded **515 m³/h against a 560 m³/h target**. In one trial the independent encoder read 35%, so the suggested first check was the actuator and its feedback. In the other it read 93%, so the first check was the airflow path. The same comparison returned both branches at the cooking line (855/900 m³/h). The two sites are replications of the same nine designed conditions. The four informative cases represent two different inspection branches, each repeated at two sites.

## Reproduce

From the repository root:

```sh
uv sync --locked --python 3.12
uv run --no-sync python scripts/cse_runtime.py install
uv run --no-sync python scripts/inspection_benchmark.py --output .runtime/inspection-benchmark.json
```

The run starts temporary loopback CSE instances with the pinned ACME distribution and ordinary facility-scoped application identities. The shipped operations core reads original CSE observations. Separate maintenance and bridge CLI processes consume and write oneM2M resources. After each trial, the driver retrieves the final work-order CIN and the exact source ACK and observations. Temporary processes and databases are removed when the run finishes. Independent shaft observations use the facility-local sensor route here. The [separate Option C deployment](../evidence/runtime/option-c/commissioned-sensor-roundtrip.json) covers actual MEC 033 commissioning, MEC 046 subscription and measured-value retrieval.

## What the counts mean

The [captured results](../evidence/runtime/inspection-benchmark.json) report a numerator for each policy and a shared eligible denominator.

- **False recoveries** count a policy declaring recovery at a checkpoint where the fixture still requires investigation. This includes acknowledged low airflow, missing or stale evidence, elevated particles, a single healthy reading and the no-ACK control. A false recovery is an incorrect declaration at that checkpoint.
- **Missed recoveries** count the two site cases with two healthy observations after a valid ACK. In each, the actual operations incident resolves and its independently owned work order stays open.
- **Matching specific first checks** count the four paired low-flow trials with valid independent evidence. A 35% shaft reading after a 95% command calls for a travel/feedback inspection. A 93% reading falls within both sites' commissioning tolerance and directs the technician to the airflow path. Each operation remains unresolved. A general inspection receives no specific-triage credit.
- **Unsupported specific checks** count guesses at a cause-specific first check in the four low-flow trials with a missing or five-minute-old shaft reading. The sensible result is a general inspection. This metric alone gives no credit for choosing between the two informative cases.

The particle-only cases have adequate airflow and elevated particles. Each creates zero shaft requests. The one-good-reading and no-ACK cases challenge early recovery. Future repetitions generate new run and CSE resource identities. The fixture expectations, scoped policy comparisons and counts should remain stable. These are bounded scenario outcomes, without claims about field diagnostic accuracy, statistical prevalence, maintenance time saved or real equipment performance.
