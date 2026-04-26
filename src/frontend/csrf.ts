/** Returns the CSRF token from the page's <meta name="csrf-token"> tag. */
export function getCsrfToken(): string {
    return (
        document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
            ?.content ?? ""
    );
}

/**
 * Injects a hidden csrftoken input into a form if one is not already present.
 * Call this before any programmatic form.submit() call.
 */
export function injectCsrfToken(form: HTMLFormElement): void {
    if (form.querySelector('input[name="csrftoken"]')) return;
    const token = getCsrfToken();
    if (!token) return;
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "csrftoken";
    input.value = token;
    form.appendChild(input);
}
