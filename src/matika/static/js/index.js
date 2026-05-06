// src/frontend/index.ts — public API for @manomatika/matika-frontend
//
// Everything exported here is part of the package's versioned public surface.
// Applug authors import from @manomatika/matika-frontend; they should not
// depend on anything that isn't exported here.
//
// What's NOT exported (internal):
//   admin_permissions.ts, admin_roles.ts, admin_users.ts — matika admin UI
//   main.ts — sidebar navigation and hub-switching logic
//
// TODO(A.3): eyerate currently imports MaintenanceActivityManager and
// ActivityMetadata via an absolute URL (/static/js/maintenance_activity.js).
// Once this package is available via npm, eyerate switches to:
//   import { MaintenanceActivityManager, ActivityMetadata } from '@manomatika/matika-frontend';
// Base class for applug admin maintenance pages (browse + edit panel pattern).
// Extend this class and override getCreateUrl, getUpdateUrl, getDeleteUrl.
export { MaintenanceActivityManager } from './maintenance_activity.js';
// CSRF helpers. Required when an applug submits a form programmatically
// (i.e. calls form.submit() rather than letting the user click a submit button).
// Matika validates the csrf_token field on every authenticated POST.
// getCsrfToken()       — reads the CSRF token from the page's <meta name="csrf-token">.
// injectCsrfToken(form) — inserts a hidden csrf_token input into the form if absent.
export { getCsrfToken, injectCsrfToken } from './csrf.js';
