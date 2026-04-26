export {};

import { getCsrfToken, injectCsrfToken } from "./csrf.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// Discriminated union — only "item" entries are selectable and activate a hub.
type SelectorEntry =
  | { type: "item"; id: string; label: string }
  | { type: "separator" }
  | { type: "header"; label: string };

interface MenuItem {
  type: "Link" | "Menu" | "Separator";
  label?: string;
  href?: string;
  open_new_tab?: boolean;
  items?: MenuItem[];
}

interface MenusData {
  selector: SelectorEntry[];
  hubs: Record<string, MenuItem[]>;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let menusData: MenusData | null = null;
let activeHubId = "__default__";
let selectorOpen = false;

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  const raw = document.getElementById("matika-menus");
  if (raw) {
    try {
      menusData = JSON.parse(raw.textContent ?? "{}") as MenusData;
    } catch {
      menusData = null;
    }
  }

  // Set active hub to the first selectable item (always "__default__")
  if (menusData) {
    const first = menusData.selector.find(
      (e): e is { type: "item"; id: string; label: string } => e.type === "item"
    );
    if (first) activeHubId = first.id;
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

function initSelector(): void {
  const trigger = document.getElementById("menu-selector-trigger");
  trigger?.addEventListener("click", (e) => {
    e.stopPropagation();
    selectorOpen = !selectorOpen;
    applyPanelState();
  });
}

function applyPanelState(): void {
  const panel = document.getElementById("menu-selector-panel");
  const trigger = document.getElementById("menu-selector-trigger");
  panel?.classList.toggle("open", selectorOpen);
  trigger?.setAttribute("aria-expanded", String(selectorOpen));
}

export function renderTrigger(): void {
  const trigger = document.getElementById("menu-selector-trigger");
  if (!trigger) return;
  trigger.textContent = "";

  let label = "Menu";
  if (menusData) {
    const activeEntry = menusData.selector.find(
      (e): e is { type: "item"; id: string; label: string } =>
        e.type === "item" && e.id === activeHubId
    );
    label = activeEntry?.label ?? "Menu";
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

export function renderSelectorList(): void {
  const list = document.getElementById("menu-selector-list");
  if (!list) return;
  list.textContent = "";
  if (!menusData) return;

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

function selectHub(hubId: string): void {
  activeHubId = hubId;
  selectorOpen = false;
  applyPanelState();
  renderTrigger();
  renderSelectorList();
  renderHub();
}

// ---------------------------------------------------------------------------
// Hub — active menu items
// ---------------------------------------------------------------------------

export function renderHub(): void {
  const container = document.getElementById("menu-hub-items");
  if (!container) return;
  closeAllHubDropdowns();
  container.textContent = "";
  if (!menusData) return;

  const items = menusData.hubs[activeHubId] ?? [];
  items.forEach((item) => container.appendChild(buildHubEntry(item)));
}

function buildHubEntry(item: MenuItem): HTMLElement {
  if (item.type === "Link") {
    const el = document.createElement("div");
    el.className = "hub-item hub-link";
    el.textContent = item.label ?? "";
    el.addEventListener("click", () => navigate(item.href!, item.open_new_tab));
    return el;
  }

  if (item.type === "Menu") {
    const el = document.createElement("div");
    el.className = "hub-item hub-menu";

    const labelSpan = document.createElement("span");
    labelSpan.className = "hub-item-label";
    labelSpan.textContent = item.label ?? "";
    const chevron = document.createElement("span");
    chevron.className = "selector-chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.textContent = " ▾";
    el.appendChild(labelSpan);
    el.appendChild(chevron);

    const dropdown = document.createElement("div");
    dropdown.className = "hub-dropdown";
    (item.items ?? []).forEach((child) => dropdown.appendChild(buildDropdownEntry(child)));
    el.appendChild(dropdown);

    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = el.classList.contains("open");
      closeAllHubDropdowns();
      if (!isOpen) el.classList.add("open");
    });
    return el;
  }

  // Top-level Separator (edge case)
  const sep = document.createElement("div");
  sep.className = "hub-item-sep";
  sep.style.cssText = "width:1px;background:#555;margin:8px 4px;flex-shrink:0;";
  return sep;
}

function buildDropdownEntry(item: MenuItem): HTMLElement {
  if (item.type === "Separator") {
    const el = document.createElement("div");
    el.className = "hub-dd-separator";
    return el;
  }

  if (item.type === "Menu") {
    const el = document.createElement("div");
    el.className = "hub-dd-submenu";

    const header = document.createElement("div");
    header.className = "hub-dd-item-row";
    header.textContent = item.label ?? "";
    const arrow = document.createElement("span");
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "▶";
    header.appendChild(arrow);
    el.appendChild(header);

    const sub = document.createElement("div");
    sub.className = "hub-submenu";
    (item.items ?? []).forEach((c) => sub.appendChild(buildDropdownEntry(c)));
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
  el.textContent = item.label ?? "";
  if (item.href) el.addEventListener("click", () => navigate(item.href!, item.open_new_tab));
  return el;
}

function closeAllHubDropdowns(): void {
  document.querySelectorAll(".hub-item.open").forEach((el) => el.classList.remove("open"));
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

export function navigate(href: string, openNewTab?: boolean): void {
  if (!href) return;
  if (openNewTab) {
    window.open(href, "_blank", "noopener,noreferrer");
  } else {
    window.location.href = href;
  }
}

// ---------------------------------------------------------------------------
// CSRF — auto-inject token into every form on submit
// ---------------------------------------------------------------------------

function wireCsrfForms(): void {
    document.addEventListener("submit", (e: SubmitEvent) => {
        const form = e.target as HTMLFormElement | null;
        if (!form || form.method.toLowerCase() !== "post") return;
        injectCsrfToken(form);
    });
}

// ---------------------------------------------------------------------------
// User zone — hover-based dropdown, wired via click handlers
// ---------------------------------------------------------------------------

function wireUserZone(): void {
  document.querySelectorAll(".menu-zone-user [data-href]").forEach((el) => {
    el.addEventListener("click", () => {
      const href = el.getAttribute("data-href");
      const target = el.getAttribute("data-target");
      const action = el.getAttribute("data-action");
      if (action === "reload") {
        location.reload();
      } else if (href) {
        navigate(href, target === "_blank");
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Global click — close selector panel and hub dropdowns on outside click
// ---------------------------------------------------------------------------

function handleGlobalClick(e: MouseEvent): void {
  const target = e.target as Node;

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
