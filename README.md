# openSoom

Open-source ventilation and air-operations software for connecting equipment, diagnosing operating issues, coordinating authorized actions, and checking their results across facilities and vendors.

**Status: product and review foundation.** This initial version contains the product contract, implementation acceptance targets, and independent review process. A runnable service, installable Codex plugin, and live LLM runner are not included yet.

## The problem

A ventilation device reporting “on” does not establish that the intended airflow is present. Operators need to connect equipment state, relevant observations, data freshness, maintenance actions, and recovery evidence.

School kitchens are one reference case. Reporting on upgraded facilities that still failed performance assessments motivates the need to examine operation after installation. The product is intended to support food-production and other ventilation-required facilities through separate facility profiles. The reporting does not establish that vendor integration caused those deficiencies. [Reference reporting](https://www.yna.co.kr/view/AKR20261010032900004), [official inspection](https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=18528).

## Intended experience

The first supported host to validate is **Codex**. A facility manager should be able to use an openSoom plugin to check prerequisites, configure a facility, connect equipment, inspect an issue, and verify the outcome without editing application source.

The proposed shared path is:

```text
Codex + openSoom plugin       Standalone real LLM API runner
            \                         /
               Shared MCP tools
                       |
             openSoom operations core
                       |
              Real oneM2M CSE services
                       |
          Device adapters / virtual equipment
```

Plugin installation, MCP connection, runtime startup, and successful service execution are separate checks. Additional agent hosts will only be listed as supported after testing.

Two execution modes are required:

- An account-free, deterministic local demonstration using real oneM2M software and simulated devices.
- A real LLM API runner that generates tool calls, uses the same service path, and checks actual CSE outcomes. A scripted fixture or a successful text response is not equivalent to this test.

No installation command is published yet because those paths have not been implemented or verified.

## What should be reusable

- **Core:** facility and equipment identity, observations, discovery, incidents, permissions, commands, acknowledgements, and result verification.
- **Facility profiles:** equipment relationships, relevant measurements, operating modes, approved rules, allowed actions, and recovery conditions.
- **Device adapters:** vendor protocols, fields, units, capability and acknowledgement mappings.
- **Examples:** a school kitchen or food-production area, plus a different ventilation scenario, using the same application code.

Consistent management does not mean identical ventilation thresholds. Facility-specific objectives and controls require appropriate validation. Real-device onboarding defaults to observation and diagnosis until scoped controls are explicitly configured.

## Why oneM2M

The design uses oneM2M discovery, subscriptions, groups, resource access policies, and distributed resource sharing so independent operations applications can reuse equipment data. The key interoperability acceptance target is adding a second vendor adapter without modifying diagnosis or operator application code.

The agent interface makes these services easier to use; it does not replace them. See the [product contract](docs/product-contract.json) for the planned tool contract and execution boundaries.

## Development and review

Four independent GPT-6.1 Sol reviewers, using Max reasoning, own all 17 hackathon criteria. The main agent records each finding, accepts an improvement or documents an alternative/deferral, coordinates implementation, and requests independent re-verification.

| Team | Primary rubric criteria |
| --- | --- |
| oneM2M architecture and interoperability | 1, 2, 3, 11 |
| Open-source adoption and deliverables | 4, 5, 6, 7 |
| Operations, trust and product AI | 8, 9, 10, 17 |
| Edge and distributed standards | 12, 13, 14, 15, 16 |

- [Contributor and agent guidance](AGENTS.md)
- [Review charter](docs/review/review-charter.json)
- [Findings and main-agent dispositions](docs/review/review-ledger.json)
- [Rubric baseline and evidence requirements](docs/hackathon/rubric-baseline.json)

Reviewer recommendations are internal acceptance targets, not additional official competition rules. Planned features do not receive implementation scores. No official aggregate score or automatic N/A policy is assumed.

## First implementation milestones

1. Build the actual CSE-backed observation → incident → authorized action → observed-result path.
2. Demonstrate two facility profiles and two vendor adapters with unchanged core applications.
3. Validate Codex plugin onboarding, declared runtime prerequisites, diagnostics, and lifecycle operations.
4. Run the deterministic scenario and actual LLM API scenario separately, retaining redacted tool and CSE traces.
5. Produce reproducible documentation and a demo video from verified behavior.

MEC deployment/services, CSE handover, federated learning, and geolocation require an operational justification and their own execution evidence. They are not added solely to fill rubric rows.

## Evidence boundaries

Physical measurements and device behavior in the planned hackathon demonstration are simulated. No certified ventilation performance, personal-exposure reduction, clinical benefit, or production readiness is claimed. Command acknowledgement, device-reported state, and observed physical response are separate evidence.

## Licensing

Project source code is licensed under [Apache-2.0](LICENSE). Original project documentation and other non-code content are licensed under [CC BY 4.0](LICENSE-DOCS.md), consistent with the [event requirements](https://onem2m-hackathon.io/introduce.asp). Third-party code, standards, references, and assets retain their own licenses; linked sources and organizer attachments are not relicensed or redistributed by this repository.
