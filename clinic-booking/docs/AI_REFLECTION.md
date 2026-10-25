# Section 4 - AI reflection

> **Read me first.** The questions ask for *your* honest account. The "what happened" notes below record what actually occurred in this build so you don't have to reconstruct it - but **edit them to match your own experience, and write items 2-4 in your own words**. Reviewers say honesty matters more than the answer.

## 1. What did I use AI for across the four sections?

*(Factual log - confirm and edit.)*

- **Section 1 (design):** I asked an AI assistant to reason from several roles at once - solution architect, data-protection officer, senior engineer, DevOps and security. It researched the current Kenyan legal landscape (Data Protection Act 2019, Digital Health Act 2023 and its regulations) and proposed the model, the "derive slots instead of storing them" idea, and the privacy decisions. I then reviewed and approved the plan before any code was written.
- **Section 2 (API):** AI wrote the Django/DRF implementation, migrations, seed command, and the 65-test suite.
- **Section 3 (CD):** AI drafted the Dockerfile, `render.yaml` and GitHub Actions workflow.
- **Documentation:** AI drafted the README and compliance notes.
- **What I did myself:** *<fill in honestly: reviewing, running, deploying, choosing Render, wiring secrets, anything you changed>*

## 2. One example where an AI suggestion improved my work

*What I prompted it with:* *<paste your real prompt - e.g. the instruction to think as a solution architect, DPO, senior engineer, DevOps and cyber-security expert, and to explain the thought process before implementing>*

*What improved:* that framing surfaced issues I had not specified: the free-text cancellation reason can contain health information (so it is kept out of logs and the audit trail); the bonus patient endpoint is an IDOR risk without object-level auth (so ids are UUIDs and foreign objects return 404); naive datetimes are rejected; and the booking guarantee lives in a database constraint rather than application code.

## 3. One example where AI output was wrong or incomplete, and how it was caught

*(Real incident from this build - confirm who caught it and edit.)*

- To prove the concurrency test was meaningful, the AI ran a "mutation check": remove the DB constraint, expect the test to fail. **The first run reported "2 passed"**, which would have falsely suggested the test was sound. The mutation script had edited the wrong place (the constraint was declared inside the migration's `CreateModel` options, not as a separate `AddConstraint`), so the constraint was never removed. This was caught because the check printed `grep -c` of the constraint name and it was still `1`. After fixing the script, the mutant produced `['ok','ok','ok',…]` (8 "winners") and both tests failed as they should.
- Smaller slips, all caught by running the code: a shell brace-expansion mistake created malformed directories; the test settings failed to import because production settings (correctly) refuse to boot without a secret key; the OpenAPI schema generator reported four views with no serializer.
- **Not verified:** the Docker image was not built in the authoring sandbox (no Docker), and the Render deploy hook's `ref` parameter and the `RENDER_GIT_COMMIT` variable are used from my understanding of Render's docs - *I should verify both on the first real deploy.*

## 4. Two decisions I made without AI, and why I trusted my judgment

*<Write these yourself - the point is your reasoning, not the AI's. Candidates that are genuinely yours if true: choosing Render as the host; deciding the deployment holds synthetic data only; choosing which branch deploys; deciding scope (e.g. what to cut) given your time budget. Explain what you knew or had experienced that made you confident.>*

1. *<decision>* - *<why I trusted my own judgment>*
2. *<decision>* - *<why I trusted my own judgment>*
