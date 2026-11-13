# AgentDesk Support FAQ (sample corpus — original)

## Password reset
Users who forget their password can request a reset link from the sign-in page; the link stays valid for 30 minutes and can be used only once. If the email does not arrive, ask the user to check spam and to confirm the address on the account, because reset mail goes to the account address, not an alias. Support agents cannot set a password on a user's behalf.

## Billing and invoices
Invoices are generated on the first day of each month and are available from the billing page for the previous twelve months. A failed card payment triggers three automatic retries over five days before the workspace is paused. Refunds for annual plans are prorated when a workspace is cancelled within the first 60 days.

## Workspace roles and permissions
Every workspace has three roles: owner, admin, and member. Owners control billing and can delete the workspace; admins manage members and integrations; members can create and edit their own content but cannot change workspace settings. Only an owner can transfer ownership, and the transfer completes when the new owner accepts the invitation email.

## API rate limits
The public API allows 600 requests per minute per API key, measured on a rolling window. Responses that exceed the limit return HTTP 429 with a Retry-After header telling the client how many seconds to wait. Batch endpoints count each item in the body as one request against the limit.

## Data export
Workspace owners and admins can export all workspace data as a ZIP archive from the settings page. The export contains documents, comments, and file attachments, and a download link is emailed when the archive is ready, usually within one hour. Exports do not include deleted items, which are purged permanently thirty days after deletion.

## Single sign-on
Single sign-on with SAML is available on the Enterprise plan and is configured from the security settings page. After SSO is enforced, password sign-in is disabled for everyone except workspace owners, who keep it as a break-glass option. The identity provider must supply an email attribute, because AgentDesk matches users by email address.

## Service status and incidents
Current service status is published on the public status page, which shows component-level availability and active incidents. During an incident, support response targets are paused and updates are posted at least every 60 minutes. Historical uptime for the previous 90 days is visible on the same page without signing in.
