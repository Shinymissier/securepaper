# SecurePaper Phase Checklist

## Phase 1 — Secure upload
- [x] Role-based setter access
- [x] File upload
- [x] SHA-256 hash
- [x] AES-256-GCM encryption
- [x] Private Supabase Storage
- [x] PENDING status
- [x] Upload audit event

## Phase 2 — Four-eyes moderation
- [x] Moderator queue
- [x] Approve
- [x] Reject with reason
- [x] Creator cannot approve own paper
- [x] Approval audit event

## Phase 3 — Controlled release
- [x] Approved-paper queue
- [x] Scheduled UTC release
- [x] Early release blocked
- [x] Approver cannot release same paper
- [x] RELEASED status
- [x] Release audit event

## Phase 4 — Controlled decryption
- [x] RELEASED-only access
- [x] Encrypted object retrieval
- [x] AES-256-GCM authentication/decryption
- [x] SHA-256 integrity verification
- [x] Download original file
- [x] Decryption audit event

## Phase 5 — Administration
- [x] All users
- [x] User roles and active state
- [x] Paper status counts
- [x] Recent audit activity
- [x] Complete audit page
- [x] Correct endpoint names


## Exam Centre User
- [x] `EXAM_CENTRE` role
- [x] User assigned to an examination centre
- [x] Centre-specific released-paper visibility
- [x] Centre-specific decryption authorization
- [x] Block and audit cross-centre access attempts
