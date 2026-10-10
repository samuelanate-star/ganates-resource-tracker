# Ganates Resource Workload/Efficiency Tracker — daily evidence and weekly delivery review

A lightweight browser app for a software team. Works on phones and computers after deployment. This package is deployable code, not an already hosted service.

## Roles and routine
1. PM creates a line-manager account, then resource accounts linked to that manager.
2. PM creates a project with a measurable goal and assigns tasks with acceptance criteria and relative weights (e.g. story points). Keep weights stable during review: adding scope changes the denominator.
3. A resource signs in and logs an update in four screens: work/date/hours → delivered outcome/increment → evidence/blocker → confirm/submit. Logging in is separate from these four entry screens. Multiple tasks can be recorded separately on the same day.
4. Each week, select the review week. Line managers inspect tickets/PRs/tests and verify or reject each submitted claim, documenting their reasoning. Rejected claims can be resubmitted as a new corrected entry; they do not count toward progress.
5. The PM reviews verified work with the manager, then approves invoice eligibility. Export the week's approved entries as CSV. No automatic financial invoice, rate calculation or payment is generated.

Only assigned line managers verify claims. Only the PM approves invoice eligibility. Resources see only their entries, managers see their own and their team's entries, and the PM sees all. Weekly counts show days with submissions, not attendance or missing-day alerts. This tool does not monitor screens, keystrokes or prove work happened. It provides reviewable delivery evidence. Leave, holidays and expected working days are not configured in this release.

## Online deployment: your existing Render + Neon approach
Use a NEW repository, NEW Render service and NEW Neon project/database for Ganates Resource Workload/Efficiency Tracker. Do not replace your Crispy Gold files or reuse its database.

1. Create a Neon project/database and copy the pooled PostgreSQL connection URI beginning postgresql://. Keep sslmode=require and other parameters. Do not include psql or surrounding quotes.
2. Create a private GitHub repository called resourceflow. Upload the contents of this folder at the repository root. Keep templates/index.html inside templates. Dockerfile and render.yaml must be at the root.
3. Render → New → Blueprint → select resourceflow repository.
4. Supply DATABASE_URL (Neon URI), ADMIN_EMAIL (your sign-in email) and ADMIN_PASSWORD (unique 12+ character password). Render generates SECRET_KEY and enables secure cookies.
5. Confirm the selected plan and any provider charges before deployment. Free plans are subject to provider limits; service sleeping can delay the first visit. No pricing promise is made by this package.
6. Deploy; open the resulting HTTPS URL. Sign in as PM with ADMIN_EMAIL and ADMIN_PASSWORD, add the line manager first, then resources, projects and tasks.
7. Test an entire resource → manager → PM approval flow before sharing the address. Confirm entries survive a redeployment.

The initial admin password is used only when the database is empty. Change it in the app afterwards. Changing ADMIN_PASSWORD in Render will not reset an existing account. PM can reset user passwords in the dashboard. Password change/reset revokes that user's existing sessions. Store all credentials only in Render environment settings; never commit them to GitHub.

## Local evaluation
Python 3.12: pip install -r requirements.txt
Set SECRET_KEY (32+ random characters), ADMIN_EMAIL and ADMIN_PASSWORD (12+ characters). Set COOKIE_SECURE=0 only for local HTTP. DATABASE_URL can be omitted locally to use SQLite; this default is unsuitable for Render because its local files may be lost. Run: gunicorn --bind 127.0.0.1:8000 --workers 1 --threads 4 app:app
Use one worker/service instance for the initial schema and admin bootstrap. PostgreSQL stores live orders centrally; browser storage is not used.

## Before broader production use
- Enforce login rate limits at a gateway or add a shared server-side rate limiter. The included signed-session retry throttle is basic and can be bypassed by clearing cookies; it is not a production brute-force defence.
- Enable database backups and test restore; define data retention and access policy for employee evidence.
- Evidence references are displayed as text, not fetched automatically. Review evidence in your existing Git/ticket tools; no integrations or attachments are included.
- Audit records preserve decisions made through the app but are not tamper-proof against database administrators.
- This first version has one PM account, no self-registration, email invitations, MFA, timesheet editing, account deactivation or automatic notifications. For departures reset passwords immediately; add account deactivation before larger rollout.
- Percent increments are explicit claims capped at 100% per task. Zero-progress investigation can still be verified and approved if its documented value meets your contract.
- The CSV includes individual entry IDs; reconcile these against your invoice register to prevent billing the same entries twice. Export does not mark entries as invoiced.

## Implementation and verification
Flask, server-rendered HTML, SQLAlchemy and PostgreSQL (Neon). Password hashing, role enforcement, CSRF validation, secure session cookies, input bounds, scoped review access, owner-row locking for progress/hour caps, and audit trail are included. Tested locally with SQLite: task setup, login, scope restrictions, daily submission, progress cap, CSRF rejection, manager verification, PM approval and CSV export. Desktop/mobile layout checked in Chromium. A live Neon/Render deployment has not been tested in your account.
