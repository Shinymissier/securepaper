Title: SecurePaper – Secure Examination Question Paper Management System

2. Brief Description

SecurePaper is a web-based examination question-paper management system developed using Flask and Supabase.

The system provides a controlled workflow for securely managing question papers from upload to moderation, approval, scheduled release, examination-centre access, secure decryption, integrity verification, and audit logging.

Main workflow

Setter
   |
   | Upload Question Paper
   v
Encrypted Storage
   |
   v
Moderator Review
   |
   +---- Reject
   |
   +---- Approve
            |
            v
     Release Officer
            |
            | Release
            v
      Examination Centre
            |
            | Authorized Access
            v
      Decrypt + Verify
            |
            v
       Question Paper
            |
            v
        Audit Log

3. Technologies / Tools Used

Technology / Tool

Purpose

Python

Main programming language

Flask

Web application framework

Supabase

Backend database and storage platform

PostgreSQL

Relational database

HTML5

Web page structure

CSS3

User interface styling

Jinja2

Dynamic Flask templates

AES-256-GCM

Question-paper encryption

SHA-256

File integrity verification

Werkzeug

Password hashing

Requests

REST API communication

python-dotenv

Environment variable configuration

VS Code

Development environment

Git / GitHub

Source-code version control and submission

4. User Roles

Role

Main Function

SETTER

Upload question papers

MODERATOR

Review, approve, or reject uploaded papers

RELEASE_OFFICER

Release approved papers

EXAM_CENTRE

Access released papers assigned to the centre

ADMIN

Administrative access

5. Key Features

Authentication

Login and logout

Session-based authentication

Password hashing

Active-user verification

Role-Based Access

Different users can perform different operations based on their assigned role.

Secure Upload

Question papers are uploaded through the setter workflow and stored in encrypted form.

Moderation

Moderators can review a paper and either approve or reject it.

Controlled Release

Only approved papers can be released by the release officer.

Examination-Centre Restriction

An examination-centre account can access only released papers assigned to that centre.

Encryption

Question-paper data is protected using AES-256-GCM before secure storage.

Integrity Verification

SHA-256 hashes are used to verify that a downloaded/decrypted question paper has not been modified.

Audit Logging

Important operations such as login, upload, approval, release, and paper access can be recorded for traceability.

Scheduled Release

Question papers can contain a scheduled release time. Release information is stored and handled using UTC timestamps and displayed in IST by the application.

6. Installation and Setup

Prerequisites

Install the following before running the project:

Python 3.x

Git

VS Code or another Python IDE

A Supabase project

PostgreSQL database provided through Supabase

Step 1 – Clone the GitHub Repository

git clone <YOUR-GITHUB-REPOSITORY-URL>
cd SecurePaper

Replace <YOUR-GITHUB-REPOSITORY-URL> with your actual GitHub repository URL.

Step 2 – Create a Virtual Environment

Windows

python -m venv venv
venv\Scripts\activate

Linux / macOS

python3 -m venv venv
source venv/bin/activate

Step 3 – Install Dependencies

pip install -r requirements.txt

If requirements.txt is not available, install the main packages with:

pip install flask requests python-dotenv werkzeug cryptography

Step 4 – Configure Environment Variables

Create a .env file in the project root.

Example:

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
AES_KEY=your-64-character-hex-key
SECRET_KEY=your-flask-secret-key

AES-256 Key

The AES-256 key must be 32 bytes long.

When represented in hexadecimal, it should contain:

64 hexadecimal characters

Example format:

0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

Do not publish actual secret keys in the GitHub repository.

Step 5 – Configure the Database

Open the Supabase SQL Editor and execute the SQL present in:

schema.sql

The project uses tables including:

users
question_papers
audit_logs

Important fields include:

users.examination_centre
question_papers.examination_centre
question_papers.status
question_papers.scheduled_release
question_papers.released_at

For an existing database, these migrations may be required:

ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS examination_centre text;

ALTER TABLE public.question_papers
ADD COLUMN IF NOT EXISTS released_at timestamptz;

Step 6 – Create the Supabase Storage Bucket

Create a private Supabase Storage bucket named:

question-papers

Question-paper files should not be publicly accessible.

Step 7 – Run the Flask Application

python app.py

Open:

http://127.0.0.1:5000

7. Project Structure / Modules

SecurePaper/
│
├── app.py
│   └── Main Flask application
│       - Authentication
│       - Session handling
│       - Question-paper upload
│       - Moderation
│       - Approval / rejection
│       - Release
│       - Secure download
│       - Encryption / decryption
│       - Integrity verification
│       - Audit logging
│
├── schema.sql
│   └── Database tables, constraints and database setup
│
├── requirements.txt
│   └── Python package dependencies
│
├── .env
│   └── Local environment configuration and secrets
│
├── README.md
│   └── Project documentation
│
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── moderation.html
│   ├── release.html
│   └── other HTML templates
│       └── Flask/Jinja user-interface pages
│
└── static/
    └── style.css
        └── Frontend styling

File names may vary slightly depending on the final submitted version of the project.

8. Database Modules

users

Stores login and authorization information.

Example fields:

id
username
password_hash
role
examination_centre
active
created_at

question_papers

Stores question-paper metadata and workflow state.

Example fields:

id
original_name
storage_path
sha256
created_by
scheduled_release
examination_centre
status
approved_by
approved_at
rejection_reason
released_at
created_at

Possible status values:

PENDING
APPROVED
REJECTED
RELEASED

audit_logs

Stores security and operation history.

Example fields:

id
username
action
paper_id
details
ip_address
created_at

9. Sample Input and Output

Sample Input 1 – Login

Input

Username: setter01
Password: Setter@123
Username: moderator01
Password: moderator@123
Username: admin01
Password: admin@123
Username: examcentre01
Password: examcentre123
<img width="1143" height="683" alt="image" src="https://github.com/user-attachments/assets/845bd1d9-20fe-4a70-8b7d-83372be6a807" />


Sample Input 2 – Upload Question Paper

Input
<img width="1503" height="720" alt="image" src="https://github.com/user-attachments/assets/a9a22ac3-20df-41b3-aba8-0e2db098145e" />

<img width="1493" height="713" alt="image" src="https://github.com/user-attachments/assets/264d3e0c-cb79-4a34-995c-709e03587298" />

Sample Input 3 – Moderator Approval

Input

Paper ID: 12
Action: APPROVE

Expected Output

Question paper approved successfully.
Status: APPROVED

Sample Input 4 – Release

Input

Paper ID: 12
Action: RELEASE

Expected Output

Question paper released successfully.
Status: RELEASED

The release timestamp is recorded in the database.

Sample Input 5 – Examination Centre Access

Input

Logged-in Role: EXAM_CENTRE
Examination Centre: Coimbatore Centre
Paper Status: RELEASED
Paper Centre: Coimbatore Centre

Expected Output

Question paper displayed on dashboard.

[ Access Paper ]

The user can access the paper because both the release status and examination-centre authorization conditions are satisfied.

Sample Input 6 – Unauthorized Centre

Input

Logged-in Role: EXAM_CENTRE
User Centre: Chennai Centre
Paper Centre: Coimbatore Centre
Paper Status: RELEASED

Expected Output

Paper is not displayed / access is denied.

10. Security Workflow

Upload

Question Paper
      |
      v
Calculate SHA-256
      |
      v
AES-256-GCM Encryption
      |
      v
Store encrypted file
      |
      v
Store metadata in database

Secure Access

User requests paper
       |
       v
Check authentication
       |
       v
Check user role
       |
       v
Check RELEASED status
       |
       v
Check examination centre
       |
       v
Retrieve encrypted file
       |
       v
Decrypt
       |
       v
Calculate SHA-256
       |
       v
Compare with stored hash
       |
       v
Return original file
       |
       v
Create audit record

11. Example Database Queries

To check question-paper status and centre assignment:

SELECT
    id,
    original_name,
    examination_centre,
    status,
    scheduled_release,
    released_at
FROM public.question_papers
ORDER BY id DESC;

To check an examination-centre user:

SELECT
    id,
    username,
    role,
    examination_centre,
    active
FROM public.users
WHERE username = 'examcentre01';

12. Testing the Project

Use this demonstration workflow:

1. Login as SETTER
2. Upload a question paper
3. Confirm status = PENDING
4. Login as MODERATOR
5. Approve the paper
6. Confirm status = APPROVED
7. Login as RELEASE_OFFICER
8. Release the paper
9. Login as EXAM_CENTRE
10. Verify only matching RELEASED papers are visible
11. Access the paper
12. Verify secure decryption and integrity checking
13. Check audit logs

13. Expected Project Output

A successful demonstration should show:

SETTER
  -> uploads paper

MODERATOR
  -> approves paper

RELEASE_OFFICER
  -> releases paper

EXAM_CENTRE
  -> sees authorized released paper

SYSTEM
  -> decrypts paper
  -> verifies SHA-256 integrity
  -> records audit activity

14. GitHub Submission Checklist

Before submitting the repository, verify:

[✓] Source code
[✓] README.md
[✓] requirements.txt
[✓] schema.sql
[✓] templates/
[✓] static/
[✓] All required project files
[✓] Installation instructions
[✓] Project structure and module descriptions
[✓] Sample input and output
[✓] No passwords or secret keys
[✓] No unnecessary temporary files

Do not upload real credentials or private keys to GitHub.

Recommended .gitignore:

.env
venv/
__pycache__/
*.pyc
uploads/

15. Common Troubleshooting

Examination Centre Shows None

Check:

SELECT id, username, role, examination_centre, active
FROM public.users
WHERE username = 'examcentre01';

If required:

ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS examination_centre text;

Assign the centre:

UPDATE public.users
SET examination_centre = 'Coimbatore Centre'
WHERE username = 'examcentre01';

Log out and log in again so the updated centre is loaded into the session.

Released Paper Is Not Showing

Check:

SELECT
    id,
    original_name,
    examination_centre,
    status,
    scheduled_release,
    released_at
FROM public.question_papers
ORDER BY id DESC;

Make sure:

status = RELEASED

and the paper's examination centre matches the logged-in examination-centre user's assignment.

released_at Column Error

Run:

ALTER TABLE public.question_papers
ADD COLUMN IF NOT EXISTS released_at timestamptz;

16. Evaluation Alignment – 20 Marks

Functionality & Correctness – 10 Marks

Demonstrable functionality includes:

User authentication

Role-based authorization

Question-paper upload

Moderation

Approval / rejection

Controlled release

Examination-centre restriction

Secure paper access

Decryption

SHA-256 integrity verification

Audit logging

Documentation – 5 Marks

The repository contains:

Project title

Project description

Technologies/tools used

Installation steps

Running instructions

Project structure

Module descriptions

Sample input and output

Database setup

Troubleshooting guidance

Code Quality – 5 Marks

The project is organized into:

Application code
Database schema
Templates
Static files
Dependency file
Configuration
Documentation

Sensitive configuration values are kept outside the source code using environment variables.

17. Security Recommendations

For production use:

Never expose the Supabase service-role key to the browser.

Keep the Storage bucket private.

Never store plain-text passwords.

Use a strong Flask SECRET_KEY.

Use a securely generated AES-256 key.

Keep .env out of version control.

Validate uploaded file types and sizes.

Restrict database access using proper server-side authorization.

Log important security actions.

Use HTTPS in production.

Rotate credentials if they are accidentally exposed.

18. Conclusion

SecurePaper provides a secure and controlled workflow for examination question-paper management.

The project combines:

Authentication
        +
Role-Based Access Control
        +
Encrypted Storage
        +
Controlled Release
        +
SHA-256 Integrity Verification
        +
Audit Logging

to protect confidential examination papers throughout their lifecycle
