# Section 4 - AI Reflection

## 1. What did I use AI for across the four sections?
I used AI as a development and reasoning assistant throughout the project, but I did not treat its output as automatically correct. I reviewed, tested, and made the final decisions on the design, implementation, security, privacy, and deployment.

### Section 1 – Design

I used an AI assistant to help me reason about the solution from several perspectives, including solution architecture, data protection, software engineering, DevOps, and cybersecurity. I also used it to research and interpret the relevant Kenyan legal and regulatory requirements, including the Data Protection Act 2019, the Digital Health Act 2023, and relevant regulations.

AI helped propose the overall model, including the approach of deriving available appointment slots rather than permanently storing unnecessary slot records. It also highlighted privacy and security considerations that needed to be addressed in the design.

However, I remained responsible for reviewing these recommendations, deciding which ones were appropriate for the project, and approving the final architecture before implementation began. Legal and compliance-related suggestions were treated as areas requiring human verification rather than being accepted solely because AI suggested them.

### Section 2 – API

I used AI to assist with implementing the Django/Django REST Framework API, including models, serializers, views, migrations, seed data, and the automated test suite.

AI generated a significant amount of the initial implementation, including the 65 tests. I then reviewed the implementation, ran the application and tests, investigated failures, and made or requested corrections where necessary.

Human review was particularly important for authentication, authorization, object-level access control, data validation, privacy, and database constraints because these areas directly affect the security and correctness of the system.

### Section 3 – Continuous Delivery

I used AI to draft the Dockerfile, `render.yaml`, and GitHub Actions workflow.

I reviewed the deployment configuration and was responsible for decisions such as the hosting approach, environment configuration, secrets, deployment flow, and what data could safely be used in the deployed environment.

Because deployment configuration can affect the security and availability of the application, I did not rely solely on AI-generated configuration. It required human review and verification before being used.

### Documentation

I also used AI to help draft the README, technical documentation, and compliance notes. I reviewed these documents to ensure that they accurately described what was actually implemented rather than what the AI assumed had been implemented.

### What I did myself

My role was not simply to accept AI-generated output. I reviewed the proposed architecture, made product and scope decisions, ran the code and test suite, investigated errors, checked security implications, reviewed the database design, configured the deployment environment, and decided whether proposed changes should actually be included.

Where AI-generated output affected privacy, security, authorization, compliance, or deployment, human review and testing were particularly important before accepting it.

---

## 2. One example where an AI suggestion improved my work

One useful example was when I asked the AI to review the system from multiple perspectives, including those of a solution architect, data-protection officer, senior engineer, DevOps engineer, and cybersecurity reviewer.

The purpose was not simply to generate code. I wanted the design to be challenged before implementation.

This review identified several issues that I had not explicitly specified in my original design.

First, it pointed out that a free-text cancellation reason could potentially contain health information. This meant that the field needed to be treated as sensitive information and should not unnecessarily appear in application logs or audit records.

Second, the review identified a potential IDOR vulnerability in the additional patient endpoint. An authenticated user should not automatically be able to access another patient's information simply by changing an ID in the request. This led to the use of UUIDs and object-level authorization, with unauthorized or nonexistent objects returning a 404 response.

Third, the review highlighted the importance of rejecting naive datetimes rather than silently interpreting them according to the server's timezone. This reduced ambiguity in appointment scheduling.

Finally, it highlighted that the appointment-booking guarantee should not depend only on application-level checks. The database should enforce the relevant uniqueness constraint so that concurrent requests cannot bypass the guarantee.

The important part was that AI identified these risks, but I still had to evaluate whether they applied to my system, implement the changes, and test them. The improvement therefore came from using AI as an additional reviewer while retaining human responsibility for the final decisions.

---

## 3. One example where AI output was wrong or incomplete, and how it was caught

A good example was the concurrency test and the mutation check that I used to verify that the database constraint was actually responsible for preventing duplicate bookings.

The purpose of the mutation check was to temporarily remove the database constraint and confirm that the concurrency test would then fail. If removing the constraint made no difference, the test could be passing for the wrong reason.

The first mutation attempt reported that the tests still passed. At first this could have been interpreted as evidence that the test was not meaningful. However, I did not accept the result immediately.

I checked the mutation script and found that it had modified the wrong part of the migration. The constraint was declared inside the `CreateModel` options rather than as a separate `AddConstraint` operation. Therefore, the script had not actually removed the constraint.

I verified this by checking the constraint name with `grep -c`, which still returned `1`. After correcting the mutation script, the database constraint was actually removed. The resulting mutant then caused the expected test failures, demonstrating that the concurrency test was genuinely dependent on the database constraint.

This was an important lesson because it showed that passing automated tests is not by itself proof that the tests are testing the intended behaviour. Human inspection of the test methodology was necessary.

There were also several smaller issues that were identified by actually running the implementation:

- A shell brace-expansion mistake created malformed directories.
- The test settings initially failed to import because the production settings correctly refused to start without a secret key.
- The OpenAPI schema generator identified four views that did not have serializers configured.
- These issues required investigation and correction rather than simply accepting the AI-generated implementation.

There were also areas that I had not fully verified at the time of writing. In particular, the Docker image had not been built in the authoring environment because Docker was unavailable there. The Render deployment configuration also contained assumptions about the deployment hook's `ref` parameter and the `RENDER_GIT_COMMIT` variable based on my understanding of Render's documentation. These should be verified during the first real deployment rather than presented as independently verified facts.

This experience reinforced that AI-generated code and configuration must be executed, tested, and reviewed. A plausible-looking answer from an AI is not evidence that the implementation is correct.

---

## 4. Two decisions I made without AI, and why I trusted my judgment

### 1. I decided that the deployed environment should use synthetic data rather than real patient data.

I made this decision because the system deals with information that could potentially include sensitive health and personal information. Using real patient information was unnecessary for demonstrating the functionality of the application and would introduce additional privacy and security risks.

I trusted my judgment on this because the project could be fully demonstrated using synthetic data, while using real health information would create risks that were not necessary to achieve the project's objectives. This was therefore both a product-scope decision and a data-protection decision.

AI helped me identify and reason about privacy risks, but the final decision to keep the deployed demonstration environment limited to synthetic data was mine.

### 2. I decided to use Render as the hosting platform and to keep the deployment scope manageable.

I chose Render because it provided a practical way to deploy the application without spending a disproportionate amount of the project time managing infrastructure. It also allowed the application to be deployed using configuration and CI/CD rather than requiring a manually maintained server.

I trusted this decision because the project's objective was to demonstrate a functioning API, testing, containerization, and continuous delivery rather than to build a complex production infrastructure platform. Given the available time and project scope, I considered a managed hosting platform a reasonable trade-off.

AI helped me compare and configure deployment approaches, but the decision about which platform to use and what level of infrastructure was appropriate for the project was ultimately mine.

## Overall Reflection

The main lesson from using AI in this project was that it is most useful as an accelerator and an additional reviewer rather than as a replacement for engineering judgment.

AI was particularly useful for generating implementation code, identifying possible security and privacy issues, producing tests, and preparing deployment and documentation drafts. However, human intervention was essential when deciding whether a recommendation was appropriate, interpreting legal and privacy requirements, validating security controls, testing the actual implementation, investigating unexpected results, selecting the deployment strategy, and deciding what data could safely be used.

The final responsibility for the system therefore remained with me. I treated AI-generated output as a proposal that had to be reviewed, tested, and, where necessary, corrected before it became part of the project.