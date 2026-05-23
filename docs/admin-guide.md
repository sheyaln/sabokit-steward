# Admin guide

If you're using Steward to manage members -- as a membership secretary,
organizer, or chapter admin -- this is for you. You don't need to know
what Authentik or Django are.

## Who can sign in

Anyone whose Authentik account is in the **steward-admins** group (or
whatever group your sysadmin configured at `/settings/`). If you can't
sign in but think you should, ask your sysadmin to add you. Steward
itself can't grant access -- that's an Authentik operation.

## Signing in

1. Visit Steward's URL (your sysadmin will tell you what it is).
2. You'll bounce to your org's Authentik sign-in page.
3. Sign in. You'll come back to Steward.

## Adding a member

Top nav → **Members** → **+ Add member**. Fill in:

- **Full name** -- how the person prefers to be addressed.
- **Email** -- this also becomes their login.
- **X-Number** (optional) -- your org's membership number, if you use
  one.

Hit Create. Steward creates the user in Authentik. They have no password
yet. If your sysadmin configured an enrollment flow (the *Invitation
flow slug* at `/settings/`), Steward also creates an invitation linked
to that flow; otherwise the member needs your sysadmin to send them
credentials another way.

## Editing a member

**Members** → click a row → **Edit**. Change name, email, X-Number.

Changing the email also changes their login (Authentik uses email as
username). Warn the person first.

## Activating / deactivating

On the member's detail page there's one button -- it flips between
**Deactivate** and **Activate** depending on current state.

- *Deactivate* is the soft "they're not a member anymore" action. The
  account stays in Authentik with all their history; they just can't
  sign in to anything until reactivated.
- *Activate* puts them back, group memberships and all.

Steward never deletes users. For a hard delete (e.g. GDPR request),
the sysadmin handles it in Authentik directly.

## Group assignment

Groups are existing Authentik groups -- you don't create them, and the
list you see may be filtered (sysadmins can hide groups Steward
admins shouldn't touch).

On a member's detail page, the **Groups** section shows current
memberships with **remove** buttons, plus a dropdown of groups you can
add them to.

If a group you expect isn't in the dropdown, either it doesn't exist in
Authentik or the filter is hiding it. Ask your sysadmin.

## Password reset

On the member's detail page, **Account actions** → **Send password
reset email**. Steward tells Authentik to send a recovery email; the
email itself comes from Authentik, not Steward.

## MFA device removal

On the member's detail page, **MFA devices** lists every authenticator
enrolled (TOTP app, security key, recovery codes, etc.). The **remove**
button next to a device pulls it immediately -- the member loses that
factor right away. Use this when someone's lost their phone or you need
to re-enroll a key.

## Bulk import

For onboarding many members at once.

1. CSV format (header row required):
   ```
   email,name,x_number
   alice@example.org,Alice Example,X-001
   bob@example.org,Bob Example,
   ```
   `x_number` can be empty per row.

2. Top nav → **Imports** → **+ Upload CSV**, choose your file.

3. Steward parses + dry-runs. The preview marks each row **create**
   (email is new), **update** (email already exists; name + X-Number
   will be overwritten), or **error** (missing email, invalid format).

4. Review. If it looks right, **Apply this import**.

5. Refresh the job page to see progress. Done means every non-error row
   has *yes* under "Applied?".

Imports are *idempotent on email*. Re-uploading the same file is safe;
it just updates existing records.

## Audit log

Top nav → **Audit log**. Every change Steward has made shows up here,
filterable by Action, Target (email), or Actor (the admin who did it).
Each row has a *diff* expander with before/after where applicable.

The log is append-only. You can read it but not edit it.

## When something goes wrong

A red "Authentik refused: ..." banner means Authentik rejected the
request. Common causes:

- Email already in use.
- Service account missing a permission.
- Authentik unreachable.

Show the exact error text to your sysadmin if you can't tell which.
