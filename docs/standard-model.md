# Data meaning, adapters and the adopted SDT scope

The adopted model is **oneM2M TS-0023 v5.6.0, §5.3.1.6 airQualitySensor**. The application creates actual type-28 flexContainers using `cod:aiQSr` and `cnd=org.onem2m.common.moduleclass.airQualitySensor`. The useful interoperability scope is PM2.5 only. [Pinned standard](https://specifications.onem2m.org/ts/ts-0023/v5.6.0/5.3/#5316-airqualitysensor).

| Quantity | Vendor A | Vendor B | Canonical observation | Standard projection |
| --- | --- | --- | --- | --- |
| PM2.5 | `pm25`, µg/m³ | `dust_mg_m3`, mg/m³ ×1000 | Nonnegative float, µg/m³ | `pm25`, integer µg/m³ using Python `round` (ties to even) |
| CO₂ | `co2`, ppm | `carbonDioxidePPM`, ppm | Nonnegative float, ppm | Omitted: SDT `co2` is mg/m³, so direct assignment would be wrong |
| Exhaust volume flow | `airflow`, m³/h | `flow_l_s`, litres/s ×3.6 | Nonnegative float, m³/h | Omitted: SDT `airFlow.speed` is not volume flow |
| Fan report | `fan_running`, boolean | `motor`, RUN/STOP | Boolean | Retained in observation CIN |
| Damper position | `damper_pct`, % | `valve_fraction` ×100 | 0–100 percent | Retained in observation CIN |
| Sample time | `observed_at` | `sampleTime` | Timezone-aware timestamp plus service receipt time | Full freshness in observation CIN |

The integer SDT view intentionally loses fractional precision. The original CIN remains authoritative for diagnosis and freshness; the standard projection supports interoperable discovery and inspection. New FCNTs have no invented initial reading. Missing PM2.5 is not replaced by zero. Latest standard values must be interpreted together with the current observation's freshness/provenance.

`discover` issues native `fu=1` queries for `ty=28` and a facility label. `read_evidence` reads those actual FCNTs with the caller's scoped AE, reports model ID, value, unit and request ID, and also returns the current canonical observations. This is application use, rather than a model created solely in a smoke test. The same projection serves both vendor adapters.

ACME's model validator rejects invalid PM2.5 field types. Unit/meaning conversion is checked in `tests/test_contracts.py`; native creation/discovery/type checks are captured in `evidence/runtime/cse-smoke.json` and secure equivalents. Product acceptance adds actual tool discovery/read evidence. This is a limited SDT mapping, not SAREF, a whole-device conformance certification or a claim that every air-management measurement fits this model.

The alternative was a fully custom payload alone. Keeping the canonical observation while providing a small valid standard projection allows consumers to recognize PM2.5 without adopting the entire openSoom schema. Extending the mapping requires checking data type, units, missing values, precision and actual consumer behavior before changing the model.
