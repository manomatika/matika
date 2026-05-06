/** Returns the CSRF token from the page's <meta name="csrf-token"> tag. */
export declare function getCsrfToken(): string;
/**
 * Injects a hidden csrf_token input into a form if one is not already present.
 * Call this before any programmatic form.submit() call.
 */
export declare function injectCsrfToken(form: HTMLFormElement): void;
//# sourceMappingURL=csrf.d.ts.map