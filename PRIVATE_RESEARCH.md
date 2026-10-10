# Ganates private research prototype — v0.2

## What is implemented
Four-step daily updates remain intact. Step 3 accepts an optional structured evidence bundle. PMs define weighted acceptance criteria before submissions; the baseline locks after the first entry. Review screens calculate current imported coverage and potential new coverage excluding criteria evidenced in already verified/billable entries. These figures do not change the existing claimed percentage or hours automatically.

The local collector computes Git stable patch IDs, rather than relying on commit IDs, to match unchanged patches across many rebases and cherry-picks. Matches are scoped to the supplied repository identifier and classified by implementation/testing/review. A fingerprint match flags possible overlapping claims; it does not establish authorship or misconduct. Different contribution kinds still need evidence of distinct work.

Evidence snapshots are append-only through the app; approved entries cannot be revised. SHA-256 checks detect changes to stored snapshot text. Line managers acknowledge research warnings before verification. PMs retain invoice approval.

## Private setup
Use a private GitHub repository accessible only to named collaborators. Do not make the repository or prototype publicly discoverable. The app is not deployed by this package. A normal free Render web service is reachable on the internet even when its GitHub repository is private: application login protects data, but does not provide network isolation. Use local/internal hosting or an authenticated access gateway for a restricted research environment.

For local testing, install requirements, set SECRET_KEY to a random 32+ character secret, ADMIN_EMAIL, ADMIN_PASSWORD (12+ characters), COOKIE_SECURE=0 and DATABASE_URL=sqlite:///ganates-research.db; then run flask --app app run. Do not expose this development server publicly. For an HTTPS hosted pilot set COOKIE_SECURE=1, a separate private Neon DATABASE_URL and the owner credentials in host settings. Follow START_HERE.md for the existing deployment workflow. Do not reuse the Crispy Gold database. New research tables are created on startup without altering the original tables. Back up an existing database before upgrading.

## Example journey
1. PM creates team, project and task, then follows Configure weighted outcome criteria to add PAY-01 and PAY-02 with agreed weights.
2. Developer creates daily update in four steps: task/date; hours and claimed increment; contribution, evidence and optional bundle; confirmation.
3. Line manager opens Evidence engine review, checks criteria coverage, warnings and snapshots, inspects actual PR/test artifacts separately, then verifies or rejects with a rationale.
4. PM approves verified work for invoicing; existing CSV export remains available.

## Collect an evidence bundle
Run locally inside your trusted repository:

python collect_evidence.py --repo /path/to/repository --commit HEAD --repository-id payments-service --criterion PAY-01 --artifact test-run-42 --result pass

Paste the resulting JSON in daily step 3. Repeat criteria in the JSON array when needed. Set result=pass only after inspecting the real result; the collector does not execute tests. Use the same repository identifier for all contributors. Do not upload source code or credentials.

## Honest research boundaries
No GitHub/GitLab OAuth, CI connector, webhooks, signed attestations or background artifact revalidation is implemented. Evidence and test outcomes are user supplied. External deletion or supersession is not detected automatically; append a new snapshot before review when it happens. Git stable patch IDs are an existing Git mechanism, not a new invention claimed by Ganates. Squashed/modified/merge commits may not match, and fingerprints do not prove hours or value. Separate contribution labels can be misused and require human review. Database administrators can change snapshots and hashes together; storage is not tamper-proof. Coverage is normalized criterion weight, not proof of delivery or an invoice calculation.

This is a research pilot, not production security certification. Existing session-based login retry controls are not robust distributed rate limiting; add host-level rate limiting/access controls before exposing a wider pilot. There is no patentability determination or prior-art clearance. Document experiments and consult a patent practitioner before publishing a potentially novel mechanism.

## Verification
Run python test_research.py. Local SQLite workflow checks cover snapshot revisions, scoped access, matching, integrity warnings, incremental coverage, manager acknowledgment, baseline locking, approval and export. PostgreSQL/Neon integration is not tested in this build. Conduct a private hosted pilot and independent security review before broader use.
