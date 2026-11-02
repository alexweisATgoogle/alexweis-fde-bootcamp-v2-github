# Defect Log

## The No-Overfitting Rule

> **Never tune agent code, prompts, or fake data to match simulator quirks, platform judge hallucinations, or evaluation-specific literals.**
>
> Fix only genuine agent code defects where behavior violates the PRD or sound engineering principles. When an evaluation fails due to simulator off-script deviation, platform judge misinterpretation, or unmeetable persona constraints, record the finding as a defect entry (`DEF-xx`) in this log. Do not write agent workarounds or corrupt domain models to appease flawed evaluations.

---

## Triage Buckets

Every failing evaluation slot in a benchmark run (`make bench` or `make bench-prod-holdout`) is classified by `scripts/triage_failures.py` into one of three triage buckets:

1. **`code`**: A reproducible defect in agent instructions, tool implementations, service logic, or callbacks violating PRD requirements. Addressed via an isolated candidate fix commit on an experimental lane.
2. **`defect:<DEF-id>`**: A known, cataloged platform, simulator, judge, or environment defect tracked in this document. Does not receive an agent-side workaround.
3. **`offscript`**: Uncataloged simulator drift (e.g., caller refusing to answer prompts, terminating early, or deviating from persona instructions) or judge scoring noise.

---

## Defect Summary Table

| DEF ID | Found by | Evidence | Label | Status | Root-cause layer | Verification |
|---|---|---|---|---|---|---|
| DEF-01 | `sim__silent_recovery` | `bench/runs/failing_runs_data/run-01/VE-08__r2.md` | `simulator` | `open` | `simulator` | 1/3 (simulator non-determinism) |
| DEF-02 | `sim__mid_call_escalation` | `bench/runs/failing_runs_data/run-01/VE-20__r1.md` | `judge` | `open` | `platform` | 2/3 (judge timing artifact) |
| DEF-03 | `sim__tiered_auth_recovery` | `bench/runs/failing_runs_data/run-01/VE-12__r1.md` | `simulator` | `open` | `simulator` | 0/3 (persona missing credentials) |
| DEF-04 | `sim__card_decline_flow` | `bench/runs/failing_runs_data/run-01/HE-07__r1.md` | `fixture` | `resolved` | `fixture` | Resolved via non-canonical `7742` |
| DEF-05 | `sim__appointment_check` | `bench/runs/failing_runs_data/run-01/VE-05__r3.md` | `fixture` | `resolved` | `fixture` | Resolved via `relative_date(+1)` |
| DEF-06 | `sim__short_command_action` | `bench/runs/failing_runs_data/run-01/VE-15__r1.md` | `platform` | `resolved` | `platform` | Resolved via `maxConversationMessages=6` |

---

## Defect Entries

### DEF-01: User simulator cannot generate silent turns for timeout recovery evaluation
- **Found by**: `sim__silent_recovery` (`run-01`, `1/3` trials)
- **Evidence**: `bench/runs/failing_runs_data/run-01/VE-08__r2.md`, `bench/runs/failing_runs_data/run-01/VE-08__r3.md`
- **Label**: `simulator`
- **Status**: `open`
- **Root-cause layer**: `simulator`
- **Diagnosis (all 3 judge metrics)**:
  - *Expectations*: Slot 2 and Slot 3 FAIL. The evaluation expectation requires the agent to prompt for caller input after a silent pause. However, the LLM user simulator never injects empty turns; it always speaks on every turn. The judge reports: *"In the provided conversation, there are no instances of silent turns from the user."*
  - *User Goal*: PASS (1.0)
  - *Hallucination*: PASS (1.0)
- **Fix & `file:line`**: No fix. The evaluation persona lacks support for silent turns. Modifying agent prompts to force timeout messages without silence would violate conversational naturalness.
- **Alternatives considered**: None on agent side.
- **Verification (`strict 3/3 | majority >=2/3 | individual`)**: Classified as simulator limitation; waived from agent code fixes.

---

### DEF-02: Judge reads "immediately" as turn 1 for mid-call topic escalation
- **Found by**: `sim__mid_call_escalation` (`run-01`, `2/3` trials)
- **Evidence**: `bench/runs/failing_runs_data/run-01/VE-20__r1.md`
- **Label**: `judge`
- **Status**: `open`
- **Root-cause layer**: `platform`
- **Diagnosis (all 3 judge metrics)**:
  - *Expectations*: Slot 1 FAIL. The judge diagnostic states: *"The user was not immediately transferred. The conversation started with an account balance inquiry; transfer only occurred several turns later."* However, the caller did not mention emergency escalation until Turn 4. In Turn 4, the agent immediately offered empathy, called `handover_to_person`, and closed the turn with `end_session`.
  - *User Goal*: PASS (1.0)
  - *Hallucination*: PASS (1.0)
- **Fix & `file:line`**: No fix. The judge conflates "escalate immediately when requested" with "escalate on turn 1 regardless of user intent". Agent escalation was immediate upon the first trigger turn.
- **Alternatives considered**: Pre-emptive transfer rejected; would break caller opening intent.
- **Verification (`strict 3/3 | majority >=2/3 | individual`)**: Classified as platform judge timing artifact.

---

### DEF-03: Persona lacks verification credentials required by authentication ladder
- **Found by**: `sim__tiered_auth_recovery` (`run-01`, `0/3` trials)
- **Evidence**: `bench/runs/failing_runs_data/run-01/VE-12__r1.md`
- **Label**: `simulator`
- **Status**: `open`
- **Root-cause layer**: `simulator`
- **Diagnosis (all 3 judge metrics)**:
  - *Expectations*: All 3 runs FAIL. The agent correctly executes the step-up verification ladder (asking for secondary identity confirmation when primary auth is unavailable), but the simulator's user guide omits any secondary credential or PIN. The simulator repeats *"I don't have that"* until max turns expire.
  - *User Goal*: FAIL (0.0)
  - *Hallucination*: PASS (1.0)
- **Fix & `file:line`**: No fix. Gating or weakening authentication security to allow unauthenticated access violates PRD requirements.
- **Alternatives considered**: Bypassing verification rejected (violates security invariants).
- **Verification (`strict 3/3 | majority >=2/3 | individual`)**: Classified as evaluation persona design defect.

---

### DEF-04: Fixture value collides with simulator canonical test values
- **Found by**: `sim__card_decline_flow` (`run-01`, `0/3` trials)
- **Evidence**: `bench/runs/failing_runs_data/run-01/HE-07__r1.md`
- **Label**: `fixture`
- **Status**: `resolved`
- **Root-cause layer**: `fixture`
- **Diagnosis (all 3 judge metrics)**:
  - *Expectations*: All 3 runs FAIL. When prompted for payment details without explicit test card parameters, the simulator invents standard canonical numbers (`4242` or `1234`). In mock fixtures where `4242` was hardcoded as an active card, the decline expectation failed to trigger.
  - *User Goal*: FAIL (0.0)
  - *Hallucination*: PASS (1.0)
- **Fix & `file:line`**: `lib/fakes.py`: replace all canonical test literals with non-canonical fixture values (default card `7742`, declined card list `DECLINED_CARD_LAST4 = {"0000", "9999"}`). Enforce via Gate 0 rule `CANONICAL_VALUE_IN_FAKES`.
- **Alternatives considered**: Hardcoding card numbers into agent prompts rejected (Rule 8).
- **Verification (`strict 3/3 | majority >=2/3 | individual`)**: 3/3 strict pass on non-canonical fixtures.

---

### DEF-05: UTC midnight date rollover breaks hardcoded calendar fixtures
- **Found by**: `sim__appointment_check` (`run-01`, `1/3` trials)
- **Evidence**: `bench/runs/failing_runs_data/run-01/VE-05__r3.md`
- **Label**: `fixture`
- **Status**: `resolved`
- **Root-cause layer**: `fixture`
- **Diagnosis (all 3 judge metrics)**:
  - *Expectations*: Slot 3 FAIL. The test fixture contained a literal date string (`"2026-10-30"`). At UTC 00:00, the appointment status transitioned from upcoming to past-due, causing service tools to report expired status instead of scheduled confirmation.
  - *User Goal*: FAIL (0.0)
  - *Hallucination*: PASS (1.0)
- **Fix & `file:line`**: `lib/fakes.py`: define `relative_date(days)` computing ISO calendar dates relative to `datetime.now(timezone.utc)`. Replace all literal dates with `relative_date(+1)` or `relative_date(-2)`. Enforce via Gate 0 rule `LITERAL_DATE_IN_FAKES`.
- **Alternatives considered**: Static dates rejected due to inevitable expiration.
- **Verification (`strict 3/3 | majority >=2/3 | individual`)**: 3/3 strict pass across midnight rollovers.

---

### DEF-06: Platform guardrail misfires on short imperative sentences with single-message window
- **Found by**: `sim__short_command_action` (`run-01`, `1/3` trials)
- **Evidence**: `bench/runs/failing_runs_data/run-01/VE-15__r1.md`
- **Label**: `platform`
- **Status**: `resolved`
- **Root-cause layer**: `platform`
- **Diagnosis (all 3 judge metrics)**:
  - *Expectations*: Slot 1 FAIL. Caller issued a brief imperative command ("Désactivez le MFA" / "Cancel service"). With default platform guardrail window `customPolicy.maxConversationMessages=1`, the model evaluated the short imperative utterance in isolation without conversational context, triggering false-positive prompt injection flags and deflecting legitimate user requests.
  - *User Goal*: FAIL (0.0)
  - *Hallucination*: PASS (1.0)
- **Fix & `file:line`**: `cxas_app/app.json`: set `customPolicy.maxConversationMessages = 6` and interpolate `{language}` into `generativeAnswer.prompt` with localized deflection copy.
- **Alternatives considered**: Disabling safety guardrails entirely rejected.
- **Verification (`strict 3/3 | majority >=2/3 | individual`)**: 234 evaluated conversations with zero false injection triggers (3/3 strict pass).
