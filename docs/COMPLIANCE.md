# Compliance and privacy notes (Kenya)

> **Status:** engineering design notes, written from a privacy-by-design perspective. **Not legal advice.**
> Statute section numbers are cited from memory and the 2024/2025 Digital Health regulations were still evolving - the clinic's DPO/counsel must confirm which provisions apply before real patient data is processed.

## 1. Instruments considered

| Instrument | Why it matters here |
|---|---|
| **Data Protection Act, 2019** (Cap. 411C) + **General Regulations 2021** + **Registration Regulations 2021** | Health data is *sensitive personal data*. Principles, lawful basis/consent, data-subject rights, DPIA, breach notification, cross-border transfer limits, controller/processor **registration with the ODPC**. |
| **Digital Health Act, 2023** + **Digital Health (Health Information Management Procedures) Regulations, 2025** | Sector law for digital health solutions: health data controllers/processors, health data privacy/sharing/archiving, certification of digital health solutions, national/county health data banks. |
| **Health Act, 2017** | Confidentiality of health records. |
| **Constitution, Art. 31** | Right to privacy. |
| **Computer Misuse and Cybercrimes Act, 2018** | Offences around unauthorised access - informs access control and logging. |

## 2. Roles

- **Controller:** the clinic (decides purposes/means). **Processor(s):** the hosting provider (Render), the MySQL database provider, and any SMS/email vendor - each needs a written processing agreement.
- A **Data Protection Officer** should be designated and the clinic **registered with the ODPC** (health is a mandatory-registration category - confirm). The Digital Health Act regime may add its own registration/certification steps.

## 3. Data inventory (what the system holds, and why)

| Data | Purpose | Sensitive? | Notes |
|---|---|---|---|
| Patient name, phone, email | Identify the patient, confirm/cancel/reschedule | Personal (and *health-linked* in context) | Phone required for staff-created patients; email optional |
| Guardian name/phone (optional) | Minors' bookings (children's data has extra protection) | Personal | Only when relevant |
| Appointment (doctor, time, status) | Deliver the booking service | **Health-linked → treated as sensitive** | |
| Cancellation reason (≤200 chars) | Required by the product spec; operational | **Potentially sensitive** (free text) | Not logged, not in audit trail; UI should offer preset reasons |
| Consent timestamp + privacy-notice version | Evidence of consent | Personal | |
| Audit log (actor id, action, object ids) | Accountability, breach investigation | Pseudonymous | No names or free text |
| **Deliberately NOT collected** | national ID, diagnosis, symptoms, "reason for visit", insurance numbers, photos | | Data minimisation |

## 4. Principles → implementation

| Principle | How it is met |
|---|---|
| Lawfulness, fairness, transparency | Registration requires explicit `consent: true`; consent time and notice version stored. A privacy notice must be published (not included in this repo). |
| Purpose limitation | Data used only to run bookings; no analytics/marketing fields. |
| Data minimisation | See inventory; no clinical data; free-text limited and kept out of logs. |
| Accuracy | Patients can re-register/contact staff; a staff *rectification* endpoint is listed as a gap (§8). |
| Storage limitation | `anonymise_patient` command; retention period to be set by the clinic (clinical-record retention rules differ from booking-metadata rules). |
| Integrity & confidentiality | TLS + HSTS, JWT with short expiry, object-level authorisation, UUID identifiers, throttling, no admin UI, non-root container, dependency/image/SAST scanning in CI, DB encryption at rest by the managed provider. |
| Accountability | Immutable audit log of booking changes, patient exports and views; this document; DPIA summary below. |
| Data protection by design/default | Secure defaults (DEBUG off, app won't boot without a secret key), public endpoint exposes no PII, 404-not-403 on foreign objects. |

## 5. Data-subject rights

| Right | Support |
|---|---|
| Access / portability | `GET /patients/{id}/export` (patient themself or staff) - JSON of everything held; the access is itself audited. |
| Erasure | `manage.py anonymise_patient <id>`: removes identity and login, cancels future bookings, **keeps** the anonymised appointment history (may need to be retained). |
| Rectification | Gap - currently via re-registration/staff process (see §8). |
| Objection / restriction | Manual process via the DPO (see §8). |
| Automated decisions | None. |

## 6. Breach response (runbook outline)

1. **Detect & contain** - revoke tokens (rotate `DJANGO_SECRET_KEY`), disable affected accounts, snapshot logs.
2. **Assess** - use the audit log to establish *which* patients/records were exposed and whether data was readable.
3. **Notify the ODPC within 72 hours** of becoming aware (where risk to rights and freedoms exists); **notify affected data subjects** without undue delay when risk is high. Where applicable, notify the Digital Health Agency per the Digital Health regulations.
4. **Record** the incident, decisions and remediation; review controls.

## 7. Hosting and cross-border transfer

- The 2021 General Regulations contain **data-localisation expectations for certain processing, including health-related processing** (e.g. a server/data centre or at least a serving copy in Kenya) and the DPA restricts transfers abroad to specified conditions. **Confirm exact scope with counsel.**
- **This repository's deployment (Render, Frankfurt; MySQL hosted separately - confirm its region too) is for assessment only and must contain synthetic data only.** For production: host in Kenya or provide a compliant Kenyan serving copy, sign processing agreements, document the transfer basis, and keep backups in the same jurisdiction.

## 8. DPIA summary and open items before real patient data

| Risk | Mitigation in place | Remaining action |
|---|---|---|
| Unauthorised access to appointment data | AuthN/Z, UUIDs, 404-on-foreign, throttling | **MFA for staff accounts**; periodic access review |
| Enumeration / scraping of availability | Public endpoint returns free slots only, throttled, 90-day horizon | WAF / bot protection |
| Sensitive free text in cancellation reason | Length limit, excluded from logs/audit | Preset reasons in UI; staff training |
| Data at rest | Provider disk encryption | Field-level encryption for contact data if the threat model requires; encrypted, restore-tested backups |
| Logs leaking PII | Bodies never logged; audit stores ids only | Central log retention policy; PII-scrubbing in error tracker |
| Cross-border hosting | Synthetic-only demo | **Kenyan hosting/serving copy** (§7) |
| No rectification/restriction tooling | Documented manual process | Add staff rectification + "restrict processing" flag |
| Regulatory registration | - | ODPC registration, DPO appointment, privacy notice, Digital Health Act registration/certification as applicable, processor agreements |
| Pen-test / hardening | CI SAST + dependency + image scans | Independent penetration test before go-live |
