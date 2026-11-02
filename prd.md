# Telco Voice Central Agent: Complete Specification & Capability Inventory

> **Authoritative Source**: Telco Voice Central Agent Development Brief (25-page specification, `go/telco-voice`).
> **Document Status**: Production Specification for Autonomous Voice Agent Architecture.
> **Scope**: Functional spec, capability inventory, compliance rules, session data model, tool contracts, verbatim copy library, business logic, priority hierarchy, and test surface.

---

## 1. Company, Persona & Voice / Channel Rules

### 1.1 Brand Identity & Persona
- **Brand Name**: Telco
- **Agent Name**: Telco Voice Central
- **Role / Purpose**: Production conversational voice agent answering Telco's main consumer customer-service line. Resolves the six primary contact reasons:
  1. Billing questions
  2. Technical support
  3. Sales & equipment
  4. Appointment management
  5. Account management
  6. Service changes
  Either self-contained in-agent resolution or via clean escalation carrying full session context to live human agents.

### 1.2 Spoken Output & Audio Constraints
- **Voice-First Design**:
  - The model must produce clean spoken text suitable for Text-to-Speech (TTS).
  - **No Markdown**: No bullet points, asterisks, bolding, markdown tables, or code fences in spoken output.
  - **No Raw URLs**: Never speak raw URLs. Provide self-serve actions via SMS dispatch (e.g. password reset link sent via SMS).
  - **Spoken Numbers & Currency**:
    - Currency amounts must be rendered naturally (e.g., "$12.50" spoken as twelve dollars and fifty cents).
    - Phone numbers: Callback numbers confirmed with last-4 visible/spoken only (e.g., `+1-NXX-555-01xx`).
  - **Conciseness & Attention Budgets**:
    - Verbal instruction lists longer than 2 steps must NOT be given verbally. Deliver step-by-step troubleshooting via SMS for anything longer than 2 sequential steps; otherwise walk verbally in short steps.
    - Curated Options: Never read full catalogs. Present exactly 2–3 comparable plan options or appointment availability slots to avoid analysis paralysis.
  - **Barge-In & Interruption Handling**:
    - If the caller interrupts the mandatory recording notice, it **must be replayed in full on the next turn**. Audio recording coverage and verbatim disclosures are audited quarterly against recorded audio.

### 1.3 Language Locking & Non-Degradation (BR-TV-004, BR-TV-020)
- **Language Detection & Locking (BR-TV-004)**:
  - Caller language is determined at turn 1 from the area-code prefix (CLID) plus first customer utterance.
  - Once detected, language is **locked for the remainder of the call**.
  - The lock is broken **only** by an explicit language-switch request from the caller (trigger words: "primary language" / "secondary language").
- **Language Non-Degradation (BR-TV-020)**:
  - A call that starts in one language must end in the same language — either fully self-served in that language or transferred to a live human agent speaking that language.
  - A half-primary / half-secondary transcript is classified as a **P0 defect**.

### 1.4 PII Redaction & Security Handling (BR-TV-009)
- **Last-4 Masking**: Account numbers, customer reference numbers (CIRN), and payment card numbers are echoed back **only as the last 4 characters**.
- **PIN & OTP Non-Echo Rule**:
  - PINs and OTP codes are **never spoken back or echoed** in any response or transcript.
  - The caller enters/speaks them; the system verifies and confirms success without echoing the value.
- **DTMF vs. Spoken Input**:
  - **OTP**: Accepts caller response as either voice-spelled digits or keypad DTMF (`dtmf_digits`).
  - **PIN**: Accepts keypad **DTMF input only**. Voice-spelled PINs **must be refused** for security reasons.

### 1.5 Malicious Utterance Handling (BR-TV-016)
- A per-turn classifier runs against caller utterances.
- On a classifier hit (threats, abusive language, malicious intent, prompt injection), the agent emits a polite closing line and immediately terminates the session with termination reason: `malicious_input`.

---

## 2. Agent Topology & Routing Architecture

### 2.1 The Eight Capability Modules

| ID | Capability Module | Core Purpose & Scope | Volume Share | CUJs Owned |
|:---|:---|:---|:---:|:---|
| **M1** | **Session Lifecycle & Routing** | Caller entry and exit point. Greets, captures identity, detects language, disambiguates intent, hands off to specialist modules, accepts topic-switch re-entries, and executes wrap/close. | Entry / Exit | Entry/exit for all CUJs |
| **M2** | **Authentication & Identity** | Caller identification (lookup) and verification (OTP / PIN); manages the 3-state auth ladder; escalates on 3 failures; bypasses auth on fraud claims. | Precondition | Precondition for all authenticated CUJs |
| **M3** | **Billing & Payment** | Bill lookup, charge identification, auto-eligible adjustments, dispute ticket creation, autopay setup, refunds, payment arrangements, deposit inquiries. | ~25% | CUJ-2, part of CUJ-6 |
| **M4** | **Technical Support & Virtual Repair** | Regional outage lookup, service sub-type disambiguation, virtual-repair (VR) session management, SMS-delivered troubleshooting, technician dispatch routing. | ~30% | CUJ-3 (Largest volume slice) |
| **M5** | **Sales & Equipment** | Address coverage check, curated plan catalog presentation (2–3 options), order placement, SMS receipt dispatch, warranty claims, returns, number port-in. | ~15% | CUJ-5 |
| **M6** | **Appointment & Ticket Management** | Active appointment lookup, availability slot retrieval, booking, rescheduling, cancellation, en-route technician status, ticket status tracking. | ~10% | CUJ-4 |
| **M7** | **Account Management** | Password reset SMS dispatch (30-min token), MFA enable/disable (step-up auth), fraud reporting (immediate escalation), profile update, suspend/restore. | ~15% | CUJ-1, part of CUJ-6 |
| **M8** | **Secondary Language Fallback** | Handles tech-support queries in secondary language when M4's primary-language content lacks coverage for the specific symptom. | Subset of M4 | CUJ-7 |

*(Note: Service Changes span M3 + M7 and represent ~5% of call volume).*

### 2.2 Intent Routing Matrix

| Representative Caller Utterance | Target Module | Auth Requirement |
|:---|:---:|:---|
| "my bill is wrong" / "dispute a charge" | **M3** | Authenticated |
| "I want to pay my bill" | **M3** | Authenticated |
| "set up autopay" | **M3** | Authenticated |
| "refund" / "credit back" | **M3** | Authenticated |
| "internet is down" / "no service" | **M4** | Authenticated |
| "TV says no signal" | **M4** | Authenticated |
| "SIM not working" / "phone locked" | **M4** | Authenticated |
| "I want to add TV" / "new plan" / "upgrade" | **M5** | Recommended (Identified/Authenticated) |
| "my phone is defective" / "warranty" | **M5** | Authenticated |
| "transfer my number in" | **M5** | Authenticated |
| "book a technician" / "reschedule my appointment" | **M6** | Authenticated |
| "where is my technician" / "ticket status" | **M6** | Authenticated |
| "forgot my password" / "reset login" | **M7** | Identified only (dispatches SMS to CIRN on file) |
| "disable two-factor" / "enable MFA" | **M7** | Authenticated + Step-up Auth |
| "someone used my account" / "fraud" | **M7** | Empathy protocol → immediate escalate (NO auth attempt) |
| "restore my suspended service" | **M7** | Authenticated (bounces through M1 to M3 if balance owed) |
| "cancel my service" / "port out my number" | **M7** | Authenticated + verbatim cancellation disclosure |
| Caller speaks secondary language, tech query out of M4 coverage | **M8** | Authenticated |
| "I want to talk to a person" | **Escalate** | Immediate transfer, reason: `user_requested_agent` |

### 2.3 Disambiguation & Mid-Call Topic Switches (BR-TV-019)
- **Disambiguation Rules**:
  - Vague utterances must be clarified with a single targeted question, never a menu recital.
  - At most **3 disambiguation attempts** on the same turn before triggering graceful escalation with reason `disambig_max_attempts`.
- **Topic Switching (BR-TV-019)**:
  - If the caller pivots mid-call to an unrelated topic (e.g. while in billing dispute, caller asks about internet outage), the agent must re-classify and re-route via M1.
  - Do NOT force the caller to complete the original flow.
  - Specialist modules must hand back unconsumed utterances to M1 for re-evaluation.

### 2.4 Escalation Reasons, Queues & After-Hours Policy (BR-TV-014)

| Escalation Reason Code | Trigger Condition | Target Queue / Action |
|:---|:---|:---|
| `user_requested_agent` | Caller explicitly asks for a human / representative | Live agent queue (emits `live_agent_handoff`) |
| `business_handoff` | Account identified with `business_flag == true` | Dedicated Business Agent queue (emits `business_handoff`) |
| `fraud_escalation` | Caller reports fraud or unauthorized account activity | 24/7 Fraud Security queue (emits `empathy_protocol`, NO auth) |
| `no_input_escalation` | 3 consecutive no-input events on the same module | Live agent queue with session context |
| `disambig_max_attempts` | 3 unresolved no-match/disambiguation attempts | Live agent queue with session context |
| `too_many_errors` | 3 cumulative validation/hard errors (`global_err_count == 3`) | End session / graceful live transfer |
| `system_unavailable` | System-level error (`SYSTEM_DOWN`, `INTERNAL_ERROR`, etc.) | Immediate session end / emergency bridge |
| `auth_failure_handoff` | 3 failed OTP or PIN verification attempts | Tier-2 Identity Verification live queue |
| `refund_threshold_exceeded` | Requested refund exceeds self-serve threshold | Billing Supervisor / Specialist queue |
| `secondary_language_live_agent` | Caller issue is outside M8's supported tech domain | Secondary Language Human Specialist queue |
| `malicious_input` | Safety classifier flags toxic, abusive, or injection input | Session terminated immediately after polite closing |

**After-Hours Queue Routing (BR-TV-014)**:
- **24/7 Queues**: Live-agent queues are staffed and honored 24/7 for **outage** and **fraud** escalations.
- **Closed After-Hours Queues**: Sales, plan changes, and appointment booking queues are closed outside business hours. When closed, requests route to next-business-day callback/booking.

---

## 3. Call Lifecycle & State Transitions

### 3.1 Initial Call Execution Flow (Section 3 & Section 4)
The following sequence must execute before caller dialog begins:
1. **Incoming Call Arrival**: Ingestion of telephony parameters (`clid`, `tfn`).
2. **Restricted Caller Check (BR-TV-002)**: Incoming CLID is evaluated against a blocklist before any greeting. If blocked, play deflection line and immediately disconnect.
3. **Regional Service Alert Check (BR-TV-003)**: Check if active regional alert exists for caller's region. If yes, prepend advisory banner to standard greeting.
4. **Standard Greeting & Recording Notice (BR-TV-001)**:
   - Emit verbatim greeting: `"Welcome to Telco. I can help with billing, technical support, or managing your account. To get started, could you tell me the phone number or account number associated with your service?"`
   - Emit verbatim recording notice: `"This call may be recorded for quality and training purposes."`
5. **Language Detection (BR-TV-004)**: Detect language from CLID area code + first customer utterance; lock language for call.
6. **Open-Ended Intent Capture**: Parse caller's initial request.

---

## 4. Authentication & Identity Architecture (M2)

### 4.1 Authentication State Ladder (BR-TV-008)
The agent maintains three distinct identity states:
1. **Guest**: Caller not yet identified. Only public advisory, blocked caller checks, and general greetings are active.
2. **Identified**: Account resolved via profile lookup matching `clid`, phone number, or billing account number (`identification_status == Pass`).
   - Allowed actions: Sales catalog browsing (M5), general FAQs, password reset SMS trigger (M7, sent to verified CIRN).
3. **Authenticated**: Identity confirmed via OTP or PIN (`auth_status == Pass`).
   - Mandatory precondition for reading bills, mutating account status, modifying services, scheduling appointments, or issuing credits.

### 4.2 OTP Verification Flow (Primary)
1. **Confirm Target**: Confirm callback number back to caller (masked to last-4):
   - `"I'll send a 6-digit code to +1-NXX-555-01xx. Ready?"`
2. **Dispatch**: Dispatch 6-digit OTP using `send_authentication_otp(clid)`.
3. **Verbatim Prompt**: Emit `id_verification_otp`:
   - `"For your security, I just sent a 6-digit code to that number — please read it back to me."`
4. **Capture**: Accept either voice-spelled digits or DTMF keypad digits (stored in `dtmf_digits`).
5. **Validation**: Call `validate_authentication_otp(code)`.
   - On `"Pass"`: Set `auth_status = Pass`.
   - On `"Fail"`: Decrement attempts remaining; reprompt caller.
   - On 3rd failure: Escalate immediately with reason `auth_failure_handoff`.

### 4.3 PIN Verification Flow (Fallback)
- Used when caller has no reachable callback number or SMS delivery fails.
1. **Verbatim Prompt**: Emit `id_verification_pin`:
   - `"For your security, I'll need to verify your identity. Please enter the 4-digit PIN you set up."`
2. **Input Restriction**: **DTMF keypad input only**. Voice-spoken PINs are rejected for security.
3. **Validation**: Call `validate_authentication_pin(pin)`.
   - On `"Pass"`: Set `auth_status = Pass`.
   - On 3rd failure: Escalate with reason `auth_failure_handoff`.

### 4.4 Authentication Guardrails
- **Fraud Exception**: If caller claims fraud or account takeover, skip all authentication attempts. Emit `empathy_protocol` and escalate with `fraud_escalation`.
- **No Fabricated Auth**: Model instructions must never allow setting `auth_status = Pass` without a successful backend tool validation.
- **Never Echo Credentials**: PINs and OTP codes are strictly forbidden from appearing in agent responses or logs.

---

## 5. Per-Turn Preprocessing & Error Taxonomy

### 5.1 Preprocessing Pipeline Execution Order (Section 6)
On every turn, before the generative model composes a response, the following 4 behaviors execute in strict sequential order:
```
[User Turn Arrives]
        │
        ▼
1. DTMF Capture ───────► Normalize native DTMF or text "user pressed 1234" -> dtmf_digits
        │
        ▼
2. No-Input Accounting ─► If no activity: increment local_noinput_counter
        │                (On count 1-2: reprompt; on 3: escalate no_input_escalation)
        ▼
3. Tool-Error Classify ─► Inspect tool response:
        │                - System -> terminate session system_unavailable
        │                - Business -> surface to model to apologize and offer alternative
        │                - Validation -> ask caller to clarify, increment global_err_count
        ▼
4. Module Pre-Checks ──► Run module-specific logic (e.g. active outage check)
        │
        ▼
[Model Composes Response]
        │
        ▼
[Post-Turn Hooks] ─────► Extract nested fields into flat session variables & set follow-ups
```

*Note on Execution Ordering*: DTMF first (so downstream logic sees keys), No-input second (so timeout retries fire before tool invocations), Tool-error third, Module pre-checks last. Reordering breaks eval determinism.

### 5.2 Tool-Error Tri-State Classification (BR-TV-010)

| Error Class | Example Codes | Required Agent Reaction | State Effect |
|:---|:---|:---|:---|
| **System** | `SYSTEM_DOWN`, `INTERNAL_ERROR`, `AUTH_SERVICE_UNAVAILABLE` | Do not retry. Do not allow model recovery. Immediately end session or bridge with reason `system_unavailable`. | Terminal |
| **Business** | `INSUFFICIENT_FUNDS`, `NOT_ELIGIBLE`, `ALREADY_APPLIED`, `OUT_OF_STOCK` | Surface error message to model. Model acknowledges politely, explains condition, and offers alternative. | Normal turn |
| **Validation** | `INVALID_INPUT`, `MALFORMED_REQUEST`, `UNRECOGNIZED_FORMAT` | Reprompt caller to clarify or re-enter data. Increment `global_err_count`. Escalates if count reaches 3 (`too_many_errors`). | Retry turn |

### 5.3 Retry Strikes & Error Counters (Section 16)

| Counter Name | Threshold | Action on Breach | Reason Code |
|:---|:---:|:---|:---|
| `local_noinput_counter` | 3 | Gracefully escalate to live agent. Reset upon module transition. | `no_input_escalation` |
| `no_match_confirmation_count` | 3 | Gracefully escalate to live agent due to disambiguation failure. | `disambig_max_attempts` |
| `global_err_count` | 3 | Terminate session due to excessive cumulative hard/validation errors. | `too_many_errors` |

---

## 6. Verbatim Copy Library (Section 7)

Every string below must be emitted **verbatim** when the corresponding condition occurs. Paraphrasing, contractions, additions, or reordering are strict compliance failures.

| Key | Primary Language (English) Verbatim Text | Usage Trigger |
|:---|:---|:---|
| `greeting_main` | `"Welcome to Telco. I can help with billing, technical support, or managing your account. To get started, could you tell me the phone number or account number associated with your service?"` | Initial greeting on incoming call. |
| `recording_notice` | `"This call may be recorded for quality and training purposes."` | Mandatory legal disclosure on greeting or when asked. |
| `id_verification_otp` | `"For your security, I just sent a 6-digit code to that number — please read it back to me."` | Triggered when OTP verification challenge is dispatched. |
| `id_verification_pin` | `"For your security, I'll need to verify your identity. Please enter the 4-digit PIN you set up."` | Triggered when PIN keypad entry is requested. |
| `live_agent_handoff` | `"I'll connect you to a representative who can help. Please hold."` | Standard live agent escalation or secondary tech fallback. |
| `business_handoff` | `"To get you the best support for your business account, I'll transfer you to an agent. You'll need to use your phone keypad instead of talking to the virtual assistant. Just a moment while I connect you."` | Emitted when caller account has `business_flag == true`. |
| `payment_method_preamble` | `"(PCI text — obtain from Legal / Compliance)"` | Precedes any collection or confirmation of payment method. |
| `contract_cancellation_fee_disclosure` | `"(contract text — obtain from Legal)"` | Precedes confirmation of account/contract cancellation. |
| `refund_confirmation_pattern` | `"Your refund of ${amount} will appear on your next statement within {days} business days."` | Mandatory post-refund confirmation statement. |
| `empathy_protocol` | `"I'm very sorry to hear that you are facing challenges. I will ensure we handle your request with the utmost care."` | Required response to fraud reports and distress cues. |
| `outage_active` | `"I see there's an active outage in your area. We're working on it. Would you like me to text you when it's restored?"` | Emitted when diagnostic check detects active regional outage. |
| `transfer_to_specialist` | `"I'll connect you to a billing specialist now — they'll have everything we've already discussed."` | Warm transfer to billing department specialist. |

*(Note: In secondary language, certified legal-approved translations of these exact strings must be emitted).*

---

## 7. Canonical Session Data Model (Section 5)

The agent tracks approximately 60 session-scoped variables across 7 functional categories.

### 7.1 Identity & Caller Profile
- `clid` (str): 10-digit caller ID from telephony line.
- `tfn` (str): Toll-free number dialed (used for brand routing).
- `cirn` (str, **PII**): Customer reference number. Must be redacted to last-4 in speech/logs.
- `billing_account` (str, **PII**): Billing account number. Must be redacted to last-4 in speech/logs.
- `customer_type` (`"New"` | `"Existing"`): Drives new sales vs. existing account modification paths.
- `user_id` (str): Internal CRM unique customer record ID.

### 7.2 Auth & Account Flags
- `auth_status` (`"Pass"` | `"Fail"` | null): Current authentication level. Never mock/override in evals.
- `identification_status` (`"Pass"` | `"Fail"` | null): Output of profile lookup.
- `business_flag` (bool-str): Indicates business-tier account; triggers mandatory live-agent transfer.

### 7.3 Routing State
- `route` (enum-str): Current active module / classified routing intent.
- `lob` (`"mobility"` | `"internet"` | `"tv"` | `"homephone"` | `"smarthome"`): Line of business.
- `tv_sub_type` (`"streaming"` | `"satellite"` | `"streaming_only"` | null): TV service classification.
- `region` (str): Service territory (`"Region-A"`, `"Region-B"`, `"Region-C"`).

### 7.4 Conversation State
- `language` (`"primary"` | `"secondary"`): Session language locked at turn 1.
- `utterance` (str): Latest caller utterance text.
- `dtmf_digits` (str): Keypad DTMF digits captured on current turn.

### 7.5 Counters & Flags
- `local_noinput_counter` (int): Consecutive no-input count for current module. Resets on module switch.
- `no_match_confirmation_count` (int): Consecutive no-match / disambiguation count.
- `global_err_count` (int): Cross-module cumulative validation/hard error count.
- `misc_counter` (int): General purpose counter for multi-step loops.
- `mock_mode` (str): When set to `"True"`, backend tools return canned successful data for eval harnesses.

### 7.6 Billing, Payments & Orders
- `last_pmt_amt` (float-str): Most recent payment amount on file.
- `amount` (float-str): Transaction/dispute amount currently under discussion.
- `ban_type` (str): Billing account categorization.
- `is_prepaid` (bool-str): Flag for prepaid subscriber accounts.
- `loyalty_limit` (int): Dollar ceiling for automated in-agent loyalty credits.

### 7.7 Virtual Repair & Ticketing
- `vr_task_count` (int): Virtual-repair diagnostic step counter.
- `ticket_state` (str): State of service ticket (`"open"`, `"in-progress"`, `"closed"`).
- `item_list` (str): Equipment/hardware items associated with ticket/diagnostic.
- `intent_type` (str): Fine-grained classification (e.g. `"Physical Damage"` vs. `"Defective"`).
- `api_resp` (str): Raw API response payload for diagnostic debugging.

### 7.8 Messaging & Transient Temporaries
- `sms_type` (`"Public"` | `"Private"`): Formats SMS template structure.
- `sms_content` (str): Body text transmitted via SMS.
- `day_val`, `date_val`, `month_val`, `end_time`, `flag_val` (str): Free-form slot temporaries for date/time booking.

---

## 8. Backend Tool Inventory & Interface Contracts

Every tool must support:
1. `mock_mode == "True"` returning synthetic successful payloads.
2. Standard error envelope: `{"error": "<CODE>", "message": "<human_readable>"}`.
3. Idempotency on mutating operations (order submission, payment, booking).
4. PII marking for log masking.

### 8.1 Representative Tool Contracts (Section 17 & 19)

#### 1. Identity Category
- **`fetch_customer_profile`**:
  - *Input*: `{ clid: string }`
  - *Output*:
    ```json
    {
      "identification_status": "Pass" | "Fail",
      "customer_type": "New" | "Existing",
      "business_flag": "true" | "false",
      "is_prepaid": "true" | "false",
      "cirn": string,
      "billing_account": string,
      "user_id": string,
      "region": string,
      "ban_type": string,
      "loyalty_limit": int
    }
    ```

#### 2. Authentication Category
- **`send_authentication_otp`**:
  - *Input*: `{ clid: string }`
  - *Output*: `{ "sent": bool, "expires_in_sec": int }`
- **`validate_authentication_otp`**:
  - *Input*: `{ code: string }`
  - *Output*: `{ "auth_status": "Pass" | "Fail", "attempts_remaining": int }`
- **`validate_authentication_pin`**:
  - *Input*: `{ pin: string }`
  - *Output*: `{ "auth_status": "Pass" | "Fail", "attempts_remaining": int }`

#### 3. Routing Category
- **`evaluate_routing_rules`**:
  - *Input*: `{ utterance: string, entities: object }`
  - *Output*: `{ "route": string, "confidence": float, "requires_auth": bool }`

#### 4. Billing & Payments Category
- **`fetch_recent_bills`**:
  - *Input*: `{ billing_account: string }`
  - *Output*:
    ```json
    {
      "bills": [
        {
          "id": string,
          "date": string,
          "amount": float,
          "line_items": [
            { "description": string, "amount": float, "id": string }
          ]
        }
      ]
    }
    ```
- **`create_dispute_ticket`**:
  - *Input*: `{ charge_id: string, reason: string, notes: string }`
  - *Output*: `{ "ticket_id": string, "eta_business_days": int }`

#### 5. Technical Support & Virtual Repair Category
- **`check_regional_outage`**:
  - *Input*: `{ region: string, lob: string }`
  - *Output*: `{ "active": bool, "restoration_eta_iso": string | null }`
- **`start_virtual_repair`**:
  - *Input*: `{ cirn: string, lob: string, symptom: string }`
  - *Output*: `{ "session_id": string, "first_diagnostic_question": string }`

#### 6. Appointments Category
- **`fetch_availability_slots`**:
  - *Input*: `{ zip: string, service_type: string }`
  - *Output*:
    ```json
    {
      "slots": [
        { "date": string, "window": string, "technician_id": string }
      ]
    }
    ```
- **`commit_appointment_reschedule`**:
  - *Input*: `{ appt_id: string, new_slot: string }`
  - *Output*: `{ "confirmed": bool, "new_date": string }`

#### 7. Sales & Equipment Category
- **`fetch_plan_catalog`**:
  - *Input*: `{ lob: string, customer_type: string }`
  - *Output*:
    ```json
    {
      "plans": [
        { "id": string, "name": string, "price": float, "key_features": [string] }
      ]
    }
    ```

#### 8. Account Management Category
- **`send_password_reset_sms`**:
  - *Input*: `{ cirn: string }`
  - *Output*: `{ "sent": bool, "valid_minutes": int }` *(30-minute validity)*
- **`execute_suspend_restore`**:
  - *Input*: `{ cirn: string, action: "suspend" | "restore", reason: string }`
  - *Output*: `{ "new_state": string, "effective_iso": string }`

#### 9. Handoff & Escalation Category
- **`execute_live_agent_handover`**:
  - *Input*: `{ reason: string, session_context: object }`
  - *Output*: `{ "handover_id": string, "queue": string }`

### 8.2 Full Back-Office Tool Surface Inventory

| Functional Category | Approx. Tool Count | Canonical Tool Naming Conventions |
|:---|:---:|:---|
| Identity & Profile | ~20 | `fetch_*`, `lookup_*`, `load_*_configs` |
| Auth (OTP / PIN) | ~10 | `send_authentication_*`, `validate_authentication_*` |
| Routing & Disambiguation | ~12 | `evaluate_routing_*`, `update_routing_state` |
| Billing & Payments | ~80 | `fetch_recent_bills_*`, `process_payment_*`, `create_dispute_*` |
| Tech Support & Virtual Repair | ~35 | `check_*_outage`, `start_virtual_repair`, `lookup_*_ticket` |
| Sales & Equipment | ~18 | `fetch_plan_catalog`, `place_new_order`, `process_warranty_claim`, `initiate_number_transfer` |
| Appointments | ~30 | `fetch_availability_*`, `commit_appointment_*` |
| SMS / Messaging | ~8 | `prepare_sms_payload`, `send_sms` |
| Handoff & Escalation | ~6 | `execute_live_agent_handover`, `execute_business_handover` |
| State Mutation Helpers | ~25 | Session-variable setters, context updaters |
| Content / RAG Datastores | ~6 | Language-tagged content stacks for grounded telco policy retrieval |

---

## 9. Domain Workflows, Business Rules & Edge Cases

### 9.1 Module M3: Billing & Payments
- **Charge Disputes**:
  - Must call `fetch_recent_bills` before discussing or referencing any specific charge.
  - Locate specific disputed charge by amount, date, or line item.
  - **Auto-Eligible Small Dollar Adjustments**: If the charge is within the auto-eligible dollar threshold and adjustment window:
    - Apply immediate credit.
    - Confirm using verbatim `refund_confirmation_pattern`: `"Your refund of ${amount} will appear on your next statement within {days} business days."`
    - **Do NOT open a dispute case** if the charge is auto-eligible.
  - **Threshold Exceeded**: If refund/dispute exceeds threshold, escalate with reason `refund_threshold_exceeded`.
- **Payment Method Entry**:
  - Must prepend verbatim `payment_method_preamble` before reading or collecting payment info.
  - Never allow caller to speak card numbers aloud; capture via DTMF.

### 9.2 Module M4: Technical Support & Virtual Repair
- **Outage Pre-Check**:
  - Always call `check_regional_outage` before beginning any equipment or signal diagnostic.
  - If active outage detected: emit verbatim `outage_active` (`"I see there's an active outage in your area. We're working on it. Would you like me to text you when it's restored?"`), offer SMS restoration notification callback, and end session.
- **TV Sub-Type Disambiguation**:
  - Before troubleshooting TV issues, agent must disambiguate service sub-type (`tv_sub_type` in `streaming`, `satellite`, `streaming_only`). **Never assume**.
- **Virtual Repair (VR) Diagnostics**:
  - Initiate via `start_virtual_repair`.
  - Capture diagnostic answers sequentially.
  - Step delivery rule: If troubleshooting instructions require > 2 steps, offer and send step-by-step instructions via SMS. Only walk verbally if caller explicitly declines SMS.
- **Unresolved Diagnostic**:
  - If issue unresolved, offer technician visit (handed back to M1 to route to M6) or open support ticket.

### 9.3 Module M5: Sales & Equipment
- **Address & Coverage Pre-Check**:
  - Always verify service availability at the caller's address via coverage check before presenting plans.
- **Plan Presentation Rule**:
  - Curate and present **exactly 2–3 plans** (never dump the catalog).
- **Business Exclusion**:
  - If account has `business_flag == true`, agent must not sell consumer plans. Emit verbatim `business_handoff` and escalate to business queue.
- **Order Placement**:
  - Collect selection, place order, state generated order number back to caller, and dispatch SMS order receipt.

### 9.4 Module M6: Appointment & Ticket Management
- **Lookup Requirement**:
  - Always query `fetch_active_appointments` before discussing rescheduling or cancellation.
- **Appointment Scenarios & Edge Cases**:
  - *Single active appointment*: Confirm details and proceed.
  - *Multiple active appointments*: Disambiguate by service type or service address.
  - *Rescheduling*: Present 2–3 available slots from `fetch_availability_slots`. Confirm chosen date/time back to caller. Send SMS confirmation.
  - *Same-Day Cancellation*: **Confirm twice**. Inform caller: once technician is dispatched, no take-backs.
  - *Technician En-Route*: **Cannot cancel**. Explain politely that technician is en-route; offer to leave a note.
  - *No Availability in Window*: Offer SMS notification callback when slot becomes available.

### 9.5 Module M7: Account Management
- **Password Reset**:
  - Identified state only.
  - Call `send_password_reset_sms`.
  - Must state the **30-minute validity window**.
  - Must **NOT** attempt to reset the password directly in conversation.
  - Must **NOT** echo the reset link in the spoken transcript.
- **MFA Management**:
  - Enabling or disabling MFA requires step-up authentication.
- **Fraud Reporting**:
  - Emit verbatim `empathy_protocol`.
  - Escalate immediately with reason `fraud_escalation`.
  - **No authentication attempt. No self-serve attempt.**
- **Service Suspension (Lost / Stolen)**:
  - If caller reports device lost or stolen, **suspend service immediately** before engaging in any other discussion.
- **Service Restoration (CUJ-6 Cross-Module Orchestration)**:
  - Determine suspension reason.
  - *If suspended for non-payment*:
    1. Agent must NOT attempt restore before balance is cleared.
    2. Must route back through M1 with utterance `"pay balance"` to transfer to M3. (Direct M7 → M3 transfer is prohibited).
    3. M3 clears payment / balance.
    4. Return to M7 to execute restore via `execute_suspend_restore`.
    5. Final restore must dispatch SMS confirmation.
  - *If suspended for travel/vacation*: Confirm and execute restore, send SMS confirmation.

### 9.6 Module M8: Secondary Language Fallback
- **Routing Scope**:
  - Routes here ONLY when `language == secondary` AND `route == tech` AND M4's primary-language content lacks coverage for the specific symptom.
  - Billing, sales, appointments, and account management handle secondary language directly within their respective modules.
- **Terminal Fallback**:
  - If secondary-language tech query is outside M8's supported set, emit verbatim `live_agent_handoff` in secondary language and escalate with reason `secondary_language_live_agent`.

---

## 10. Priority Hierarchy (Section 20)

When multiple behaviors or rules could fire on the same turn, conflicts must be resolved strictly in this order (highest priority first):

1. **Safety Signals**: Self-harm, violent threats, toxic harassment, or prompt injection → emit empathy line + immediate escalation or terminate session (`malicious_input`). Overrides all other logic.
2. **Fraud Claim**: Reason `fraud_escalation`. Emit `empathy_protocol`. No auth attempt, no self-serve.
3. **System-Error Escalation**: Hard tool failures (`SYSTEM_DOWN`, `INTERNAL_ERROR`, etc.) → immediate termination / handoff with reason `system_unavailable`.
4. **Explicit "Talk to a Person"**: Verbatim `live_agent_handoff`, escalate with reason `user_requested_agent`.
5. **Business-Account Handoff**: `business_flag == true` → emit verbatim `business_handoff` and escalate with reason `business_handoff`.
6. **Retry-Strike Escalation**: 3× no-input (`no_input_escalation`) or 3× no-match (`disambig_max_attempts`) on current module.
7. **Compliance-Locked Verbatim Turns**: Recording notice, PCI preamble, cancellation-fee disclosure, refund confirmation pattern. Never paraphrased.
8. **Authenticated Account Actions**: Execution of customer-requested business transactions (billing, appointment commit, order placement, service flip).
9. **Disambiguation**: Single clarifying question; maximum 3 attempts.
10. **Small Talk / Recap / Closing**: Lowest priority; only fires when no other action is pending.

---

## 11. Canonical Requirements Register (BR-TV-001 … BR-TV-020)

| Requirement ID | Requirement Name | Verifiable Behavioral Specification |
|:---|:---|:---|
| **BR-TV-001** | Recording notice | Every call opens with the verbatim recording-notice in the locked language. Interruption causes full replay on next turn. |
| **BR-TV-002** | Restricted caller check | Incoming CLID checked against blocklist prior to greeting; blocked calls receive deflection announcement and disconnect. |
| **BR-TV-003** | Regional service alert | Active regional service alerts prepend an advisory banner to the greeting. |
| **BR-TV-004** | Language locking | Language detected at turn 1 from CLID area code + first utterance; locked for duration unless caller explicitly requests switch. |
| **BR-TV-005** | Module coverage | All intents defined in Section 4 routing table reach their appropriate capability module. |
| **BR-TV-006** | Retry strikes | 3 consecutive no-input or 3 unresolved no-match events on a module trigger graceful escalation. |
| **BR-TV-007** | DTMF capture | Keypad DTMF entries normalized and exposed as `dtmf_digits` on the active turn. |
| **BR-TV-008** | Auth ladder | Strict state progression: Guest → Identified → Authenticated. Account reads and mutations strictly require Authenticated. |
| **BR-TV-009** | PII redaction | Account #, CIRN, card digits echoed last-4 only. PINs and OTPs never echoed in speech or transcript. |
| **BR-TV-010** | Tool-error tri-state | System errors terminate/escalate immediately; business errors surface to model; validation errors prompt retry. |
| **BR-TV-011** | Verbatim compliance | Every compliance string in Section 7 emitted verbatim without alteration; verified by golden substring assertions. |
| **BR-TV-012** | Business handoff | Accounts with `business_flag == true` receive verbatim business handoff line and escalate; no consumer self-serve. |
| **BR-TV-013** | Fraud escalation | Fraud claims trigger empathy protocol and immediate live transfer; bypasses authentication and self-serve. |
| **BR-TV-014** | After-hours awareness | Outage & fraud live queues staffed 24/7. Sales, plan changes, appointments route to next-business-day when closed. |
| **BR-TV-015** | Session-context handoff | Every live agent escalation delivers full session variables payload to agent desktop / queue. |
| **BR-TV-016** | Malicious utterance | Safety classifier hits trigger polite closing statement and terminate session with reason `malicious_input`. |
| **BR-TV-017** | No invented data | Model must never hallucinate account data or tool responses. Every account read generation is conditioned on successful tool output. |
| **BR-TV-018** | Audio recording | Every call produces a `.wav` file in the designated session-audio cloud storage bucket; audited quarterly. |
| **BR-TV-019** | Topic switch mid-call | Mid-call topic pivots trigger re-classification and transfer via M1 rather than trapping caller in existing flow. |
| **BR-TV-020** | Language non-degradation | A call starting in primary/secondary language must terminate in that same language (self-served or transferred to native speaker). |

---

## 12. Canonical Critical User Journeys (CUJs 1–7)

### CUJ-1: Account Password Reset (`cuj_1_account_password_reset`)
- **Primary Module**: M7 (Account Management)
- **Call Volume Share**: 15%
- **Max Turns**: 8
- **Goal**: Reset self-serve portal password via SMS link.
- **Success Criteria**: Agent identifies caller, dispatches SMS reset link, states 30-min validity window.
- **Mandatory Expectations**:
  1. Agent must authenticate/identify caller before dispatching link.
  2. Agent must NOT attempt to reset password directly in conversation (self-serve SMS link only).
  3. Agent must explicitly state the 30-minute validity window.
  4. Agent must NOT echo the reset link value in the spoken transcript.

### CUJ-2: Billing Dispute Auto-Eligible (`cuj_2_billing_dispute_auto_eligible`)
- **Primary Module**: M3 (Billing & Payment)
- **Call Volume Share**: 25%
- **Max Turns**: 10
- **Goal**: Dispute small-dollar charge that qualifies for automated adjustment.
- **Success Criteria**: Agent looks up bill, identifies charge, applies adjustment, states refund amount & window.
- **Mandatory Expectations**:
  1. Agent must call recent-bills lookup before referencing any specific charge.
  2. Agent must state refund amount and business-day window using verbatim `refund_confirmation_pattern`.
  3. Agent must NOT open a dispute case (since charge is auto-eligible for credit).

### CUJ-3: Tech Support TV Signal (`cuj_3_tech_support_tv_signal`)
- **Primary Module**: M4 (Technical Support & Virtual Repair)
- **Call Volume Share**: 30%
- **Max Turns**: 12
- **Goal**: Resolve "no signal" TV issue with no active regional outage.
- **Success Criteria**: Agent checks outage, disambiguates `tv_sub_type`, starts VR session, offers SMS troubleshooting.
- **Mandatory Expectations**:
  1. Agent must check regional outage first.
  2. Agent must disambiguate `tv_sub_type` (streaming vs. satellite) before starting virtual repair.
  3. Agent must offer SMS steps when there are more than 2 sequential troubleshooting steps.

### CUJ-4: Appointment Reschedule (`cuj_4_appointment_reschedule`)
- **Primary Module**: M6 (Appointment & Ticket Management)
- **Call Volume Share**: 10%
- **Max Turns**: 8
- **Goal**: Reschedule an existing technician appointment.
- **Success Criteria**: Agent locates active appointment, offers 2–3 available slots, commits change, sends SMS confirmation.
- **Mandatory Expectations**:
  1. Agent must look up active appointments before offering available slots.
  2. Agent must state the new date/time back to caller for confirmation.
  3. Agent must send SMS confirmation after committing reschedule.

### CUJ-5: Sales Add TV Existing Account (`cuj_5_sales_add_tv_existing`)
- **Primary Module**: M5 (Sales & Equipment)
- **Call Volume Share**: 15%
- **Max Turns**: 10
- **Goal**: Add TV service to an existing authenticated account.
- **Success Criteria**: Agent verifies coverage, presents 2 plans, places order, states order number.
- **Mandatory Expectations**:
  1. Agent must check service coverage at address before presenting plans.
  2. Agent must present exactly 2–3 comparable plan options (not the entire catalog).
  3. Agent must state the returned order number after order tool succeeds.

### CUJ-6: Restore Service from Non-Payment (`cuj_6_restore_service_from_non_payment`)
- **Primary Module**: M7 (Account Management) with cross-module dependency on M3 (Billing & Payment)
- **Call Volume Share**: 5%
- **Max Turns**: 14
- **Goal**: Restore service suspended due to outstanding balance.
- **Success Criteria**: Agent detects non-payment suspension, routes back through M1 to M3 to clear balance, returns to M7 to restore service.
- **Mandatory Expectations**:
  1. Agent must NOT attempt restore before outstanding balance is cleared.
  2. Cross-module routing must pass through M1 (no direct M7 → M3 transfer).
  3. Final restore step must send SMS confirmation.

### CUJ-7: Secondary Language Tech Fallback (`cuj_7_secondary_language_tech_fallback`)
- **Primary Module**: M8 (Secondary Language Fallback)
- **Call Volume Share**: Subset of M4
- **Max Turns**: 10
- **Goal**: Handle secondary-language tech query that primary M4 cannot cover.
- **Success Criteria**: M1 routes to M8; agent communicates entirely in secondary language; resolves or escalates.
- **Mandatory Expectations**:
  1. The transcript must never contain a primary-language response.
  2. If unresolved, escalate with reason `secondary_language_live_agent`.

---

## 13. Testing, Verification & Definition of Done

### 13.1 Testing Surface

| Test Suite Kind | Purpose | Target Coverage |
|:---|:---|:---|
| **Tool-Contract Tests** | Verify each tool exposes both real branch and mock_mode branch; validate error envelope structure. | 100% of callable tools |
| **Per-Turn Preprocessing Tests** | Verify DTMF capture, no-input counting, tool-error classification, and safety classifier order and behavior. | All 4 pipeline stages, boundary and happy path |
| **Deterministic Goldens** | Assert exact substring equality for verbatim compliance strings, PII last-4 redaction, escalation reason codes. | 100% of verbatim strings in Section 7; all escalation reason codes |
| **Simulation Scenarios (Sim-Eval)** | End-to-end multi-turn evaluation of each CUJ (CUJ 1–7) plus cross-module topic switches. | All 7 CUJs: ≥ 60% baseline pass rate; ≥ 90% pre-production pass rate |
| **Audio-Mode Audit** | Run top simulation scenarios through telephony audio stack; verify TTS pronunciation and DTMF capture. | All P0 scenarios per release candidate |
| **Telephony-Loop Test** | Real dial-in verification of live audio wire, barge-in behavior, and DTMF signaling. | Once per release candidate |
| **Compliance Audit** | Manual audit of 50 calls per language for exact verbatim phrasing and zero PII leaks. | Quarterly + upon any change to verbatim library |

### 13.2 Production Definition of Done (DoD)
A build of Telco Voice Central is certified production-ready only when it satisfies all of the following release gates:
1. **≥ 60%** in-agent resolution rate.
2. **≤ 4 minutes** average handle time (AHT).
3. **100% verbatim compliance** across all audited compliance strings.
4. **Zero PII disclosures** across the audited sample set.
5. **100% audio-recording coverage** in the session-audio bucket.
6. **Zero regressions** on the P0 golden test suite across two consecutive deploy cycles.
