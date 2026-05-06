/** Returns the CSRF token from the page's <meta name="csrf-token"> tag. */
export function getCsrfToken() {
    var _a, _b;
    return ((_b = (_a = document.querySelector('meta[name="csrf-token"]')) === null || _a === void 0 ? void 0 : _a.content) !== null && _b !== void 0 ? _b : "");
}
/**
 * Injects a hidden csrf_token input into a form if one is not already present.
 * Call this before any programmatic form.submit() call.
 */
export function injectCsrfToken(form) {
    if (form.querySelector('input[name="csrf_token"]'))
        return;
    const token = getCsrfToken();
    if (!token)
        return;
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "csrf_token";
    input.value = token;
    form.appendChild(input);
}
