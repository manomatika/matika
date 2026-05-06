import { injectCsrfToken } from "./csrf.js";
// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let menusData = null;
let activeHubId = "__default__";
let selectorOpen = false;
// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    var _a, _b, _c, _d, _e, _f;
    const raw = document.getElementById("matika-menus");
    if (raw) {
        try {
            menusData = JSON.parse((_a = raw.textContent) !== null && _a !== void 0 ? _a : "{}");
        }
        catch (_g) {
            menusData = null;
        }
    }
    // Restore the selector choice, honouring this priority order:
    //   1. sessionStorage  — user navigated within this session (per-user key)
    //   2. user-default-menu meta — user's saved preference (from User Settings)
    //   3. First item in the selector list (Default)
    //
    // Per-user keying prevents two users sharing a browser tab from seeing
    // each other's last selection.
    if (menusData) {
        const selectorItems = menusData.selector.filter((e) => e.type === "item");
        const storageKey = getHubStorageKey();
        const freshLogin = ((_b = document.querySelector('meta[name="fresh-login"]')) === null || _b === void 0 ? void 0 : _b.content) === "true";
        if (freshLogin) {
            sessionStorage.removeItem(storageKey);
        }
        const stored = sessionStorage.getItem(storageKey);
        const userPref = (_d = (_c = document.querySelector('meta[name="user-default-menu"]')) === null || _c === void 0 ? void 0 : _c.content) !== null && _d !== void 0 ? _d : "";
        const validStored = stored && selectorItems.some((e) => e.id === stored);
        const validPref = userPref && selectorItems.some((e) => e.id === userPref);
        activeHubId = validStored
            ? stored
            : validPref
                ? userPref
                : ((_f = (_e = selectorItems[0]) === null || _e === void 0 ? void 0 : _e.id) !== null && _f !== void 0 ? _f : "__default__");
    }
    initSelector();
    renderTrigger();
    renderSelectorList();
    renderHub();
    wireUserZone();
    wireCsrfForms();
    document.addEventListener("click", handleGlobalClick);
});
// ---------------------------------------------------------------------------
// Selector — trigger and panel
// ---------------------------------------------------------------------------
function initSelector() {
    const trigger = document.getElementById("menu-selector-trigger");
    trigger === null || trigger === void 0 ? void 0 : trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        selectorOpen = !selectorOpen;
        applyPanelState();
    });
}
function applyPanelState() {
    const panel = document.getElementById("menu-selector-panel");
    const trigger = document.getElementById("menu-selector-trigger");
    panel === null || panel === void 0 ? void 0 : panel.classList.toggle("open", selectorOpen);
    trigger === null || trigger === void 0 ? void 0 : trigger.setAttribute("aria-expanded", String(selectorOpen));
}
export function renderTrigger() {
    var _a;
    const trigger = document.getElementById("menu-selector-trigger");
    if (!trigger)
        return;
    trigger.textContent = "";
    let label = "Menu";
    if (menusData) {
        const activeEntry = menusData.selector.find((e) => e.type === "item" && e.id === activeHubId);
        label = (_a = activeEntry === null || activeEntry === void 0 ? void 0 : activeEntry.label) !== null && _a !== void 0 ? _a : "Menu";
    }
    const labelSpan = document.createElement("span");
    labelSpan.textContent = label;
    const chevron = document.createElement("span");
    chevron.className = "selector-chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.textContent = "▾";
    trigger.appendChild(labelSpan);
    trigger.appendChild(chevron);
}
export function renderSelectorList() {
    const list = document.getElementById("menu-selector-list");
    if (!list)
        return;
    list.textContent = "";
    if (!menusData)
        return;
    menusData.selector.forEach((entry) => {
        if (entry.type === "separator") {
            const el = document.createElement("div");
            el.className = "menu-selector-divider";
            list.appendChild(el);
            return;
        }
        if (entry.type === "header") {
            const el = document.createElement("div");
            el.className = "menu-selector-section-header";
            el.textContent = entry.label;
            list.appendChild(el);
            return;
        }
        // type === "item"
        const el = document.createElement("div");
        el.className = "menu-selector-item" + (entry.id === activeHubId ? " active" : "");
        el.textContent = entry.label;
        el.setAttribute("role", "option");
        el.setAttribute("aria-selected", String(entry.id === activeHubId));
        el.addEventListener("click", () => selectHub(entry.id));
        list.appendChild(el);
    });
}
function getHubStorageKey() {
    var _a, _b;
    const uid = (_b = (_a = document.querySelector('meta[name="user-id"]')) === null || _a === void 0 ? void 0 : _a.content) !== null && _b !== void 0 ? _b : "";
    return uid ? `matika_active_hub_${uid}` : "matika_active_hub";
}
function selectHub(hubId) {
    activeHubId = hubId;
    sessionStorage.setItem(getHubStorageKey(), hubId);
    selectorOpen = false;
    applyPanelState();
    renderTrigger();
    renderSelectorList();
    renderHub();
}
// ---------------------------------------------------------------------------
// Hub — active menu items
// ---------------------------------------------------------------------------
export function renderHub() {
    var _a;
    const container = document.getElementById("menu-hub-items");
    if (!container)
        return;
    closeAllHubDropdowns();
    container.textContent = "";
    if (!menusData)
        return;
    const items = (_a = menusData.hubs[activeHubId]) !== null && _a !== void 0 ? _a : [];
    items.forEach((item) => container.appendChild(buildHubEntry(item)));
}
function buildHubEntry(item) {
    var _a, _b, _c;
    if (item.type === "Link") {
        const el = document.createElement("div");
        el.className = "hub-item hub-link";
        el.textContent = (_a = item.label) !== null && _a !== void 0 ? _a : "";
        el.addEventListener("click", () => navigate(item.href, item.open_new_tab));
        return el;
    }
    if (item.type === "Menu") {
        const el = document.createElement("div");
        el.className = "hub-item hub-menu";
        const labelSpan = document.createElement("span");
        labelSpan.className = "hub-item-label";
        labelSpan.textContent = (_b = item.label) !== null && _b !== void 0 ? _b : "";
        const chevron = document.createElement("span");
        chevron.className = "selector-chevron";
        chevron.setAttribute("aria-hidden", "true");
        chevron.textContent = " ▾";
        el.appendChild(labelSpan);
        el.appendChild(chevron);
        const dropdown = document.createElement("div");
        dropdown.className = "hub-dropdown";
        ((_c = item.items) !== null && _c !== void 0 ? _c : []).forEach((child) => dropdown.appendChild(buildDropdownEntry(child)));
        el.appendChild(dropdown);
        el.addEventListener("click", (e) => {
            e.stopPropagation();
            const isOpen = el.classList.contains("open");
            closeAllHubDropdowns();
            if (!isOpen)
                el.classList.add("open");
        });
        return el;
    }
    // Top-level Separator (edge case)
    const sep = document.createElement("div");
    sep.className = "hub-item-sep";
    sep.style.cssText = "width:1px;background:#555;margin:8px 4px;flex-shrink:0;";
    return sep;
}
function buildDropdownEntry(item) {
    var _a, _b, _c, _d;
    if (item.type === "Separator") {
        const el = document.createElement("div");
        el.className = "hub-dd-separator";
        return el;
    }
    if (item.type === "SectionHeader") {
        const el = document.createElement("div");
        el.className = "hub-dd-section-header";
        el.textContent = (_a = item.label) !== null && _a !== void 0 ? _a : "";
        return el;
    }
    if (item.type === "Menu") {
        const el = document.createElement("div");
        el.className = "hub-dd-submenu";
        const header = document.createElement("div");
        header.className = "hub-dd-item-row";
        header.textContent = (_b = item.label) !== null && _b !== void 0 ? _b : "";
        const arrow = document.createElement("span");
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "▶";
        header.appendChild(arrow);
        el.appendChild(header);
        const sub = document.createElement("div");
        sub.className = "hub-submenu";
        ((_c = item.items) !== null && _c !== void 0 ? _c : []).forEach((c) => sub.appendChild(buildDropdownEntry(c)));
        el.appendChild(sub);
        header.addEventListener("click", (e) => {
            e.stopPropagation();
            el.classList.toggle("open");
        });
        return el;
    }
    // Link
    const el = document.createElement("div");
    el.className = "hub-dd-item";
    el.textContent = (_d = item.label) !== null && _d !== void 0 ? _d : "";
    if (item.href)
        el.addEventListener("click", () => navigate(item.href, item.open_new_tab));
    return el;
}
function closeAllHubDropdowns() {
    document.querySelectorAll(".hub-item.open").forEach((el) => el.classList.remove("open"));
}
// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
export function navigate(href, openNewTab) {
    if (!href)
        return;
    if (openNewTab) {
        window.open(href, "_blank", "noopener,noreferrer");
    }
    else {
        window.location.href = href;
    }
}
// ---------------------------------------------------------------------------
// CSRF — auto-inject token into every form on submit
// ---------------------------------------------------------------------------
function wireCsrfForms() {
    document.addEventListener("submit", (e) => {
        const form = e.target;
        if (!form || form.method.toLowerCase() !== "post")
            return;
        injectCsrfToken(form);
    });
}
// ---------------------------------------------------------------------------
// User zone — hover-based dropdown, wired via click handlers
// ---------------------------------------------------------------------------
function wireUserZone() {
    document.querySelectorAll(".menu-zone-user [data-href]").forEach((el) => {
        el.addEventListener("click", () => {
            const href = el.getAttribute("data-href");
            const target = el.getAttribute("data-target");
            const action = el.getAttribute("data-action");
            if (action === "reload") {
                location.reload();
            }
            else if (href) {
                navigate(href, target === "_blank");
            }
        });
    });
}
// ---------------------------------------------------------------------------
// Global click — close selector panel and hub dropdowns on outside click
// ---------------------------------------------------------------------------
function handleGlobalClick(e) {
    const target = e.target;
    const selectorEl = document.getElementById("menu-selector");
    if (selectorOpen && selectorEl && !selectorEl.contains(target)) {
        selectorOpen = false;
        applyPanelState();
    }
    const hubEl = document.getElementById("menu-hub-items");
    if (hubEl && !hubEl.contains(target)) {
        closeAllHubDropdowns();
    }
}
