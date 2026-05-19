/* ───────────────────────────────────────────
   DEFAULTS
   ─────────────────────────────────────────── */
const DEFAULTS = {
  title: "Feuerwehr Zeittracker",
  show_header: true,
  layout: "auto",
  show_einsatz: true,
  show_probe: true,
  show_geratehaus: true,
  show_total: true,
  total_display: "prominent",
  color_einsatz: "#e53935",
  color_probe: "#1e88e5",
  color_geratehaus: "#43a047",
  color_gesamt: "#888888",
  label_einsatz: "Einsatz",
  label_probe: "Probe",
  label_geratehaus: "Gerätehaus",
  label_gesamt: "Gesamt",
  category_order: ["einsatz", "probe", "geratehaus", "gesamt"],
};

function hexToRgba(hex, alpha) {
  if (!hex || typeof hex !== "string" || !hex.startsWith("#") || hex.length < 7) {
    return `rgba(128,128,128,${alpha})`;
  }
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function fmt(v) {
  const n = Number(v);
  return isFinite(n) ? n.toFixed(2) : "0.00";
}

function getVal(hass, entityId) {
  if (!entityId || !hass) return 0;
  const s = hass.states[entityId];
  if (!s || s.state === "unavailable" || s.state === "unknown") return null;
  return Number(s.state);
}

function valText(v) {
  return v !== null ? fmt(v) + " h" : "—";
}

/* ───────────────────────────────────────────
   CSS
   ─────────────────────────────────────────── */
const CARD_STYLES = `
  :host { display: block; }
  ha-card {
    padding: 12px 14px;
    box-sizing: border-box;
    height: 100%;
    overflow: hidden;
  }
  .header {
    font-size: 15px;
    font-weight: 700;
    color: var(--primary-text-color);
    opacity: 0.95;
    margin-bottom: 8px;
  }
  .compact-header {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.7;
  }
  .content.large {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .total-section {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-shrink: 1;
    min-width: 0;
  }
  .total-value {
    font-size: 35px;
    font-weight: 800;
    color: var(--primary-text-color);
    line-height: 1;
  }
  .total-label {
    font-size: 17px;
    font-weight: 700;
    color: var(--secondary-text-color);
    white-space: nowrap;
  }
  .chips-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-left: auto;
    width: 100%;
    box-sizing: border-box;
  }
  .chips-row.has-prominent {
    width: auto;
    margin-left: auto;
  }
  .chip {
    display: flex;
    gap: 8px;
    align-items: baseline;
    justify-content: space-between;
    padding: 8px 10px;
    border-radius: 12px;
    border: 1px solid;
    flex: 1 1 0;
    min-width: 0;
    box-sizing: border-box;
    transition: transform 0.15s ease;
  }
  .chip:hover { transform: scale(1.02); }
  .chip-label {
    font-size: 13px;
    font-weight: 700;
    white-space: nowrap;
  }
  .chip-value {
    font-size: 16px;
    font-weight: 800;
    color: var(--primary-text-color);
    white-space: nowrap;
  }
  .content.compact {
    display: flex;
    flex-direction: column;
  }
  .chips-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    width: 100%;
    box-sizing: border-box;
  }
  .chip-compact {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: 7px 6px;
    border-radius: 10px;
    border: 1px solid;
    box-sizing: border-box;
    transition: transform 0.15s ease;
  }
  .chip-compact:hover { transform: scale(1.03); }
  .chip-label-compact {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }
  .chip-value-compact {
    font-size: 14px;
    font-weight: 800;
    color: var(--primary-text-color);
  }
  .compact-prominent {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 8px;
  }
  .compact-prominent .total-value {
    font-size: 28px;
  }
  .compact-prominent .total-label {
    font-size: 13px;
  }
`;

const EDITOR_STYLES = `
  .editor { padding: 8px 0; }
  .section {
    margin-bottom: 16px;
    border: 1px solid var(--divider-color, rgba(128,128,128,0.2));
    border-radius: 12px;
    padding: 12px;
  }
  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .section-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--primary-text-color);
  }
  .order-buttons {
    display: flex;
    gap: 4px;
  }
  .order-btn {
    width: 28px;
    height: 28px;
    border: 1px solid var(--divider-color, rgba(128,128,128,0.3));
    border-radius: 6px;
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    padding: 0;
  }
  .order-btn:hover {
    background: var(--divider-color, rgba(128,128,128,0.15));
  }
  .order-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0;
    gap: 12px;
  }
  label {
    font-size: 13px;
    color: var(--primary-text-color);
    flex-shrink: 0;
  }
  input[type="text"], select {
    flex: 1;
    max-width: 200px;
    padding: 6px 8px;
    border: 1px solid var(--divider-color, rgba(128,128,128,0.3));
    border-radius: 8px;
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    font-size: 13px;
    outline: none;
  }
  input[type="text"]:focus, select:focus {
    border-color: var(--primary-color, #03a9f4);
    box-shadow: 0 0 0 1px var(--primary-color, #03a9f4);
  }
  input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: var(--primary-color, #03a9f4);
  }
  .color-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    max-width: 200px;
    justify-content: flex-end;
  }
  input[type="color"] {
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    padding: 0;
  }
  .color-text {
    width: 80px !important;
    flex: 0 !important;
  }
`;

/* ═══════════════════════════════════════════
   CARD
   ═══════════════════════════════════════════ */
class FeuerwehrTimeTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._compact = false;
    this._ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (this._config.layout === "auto") {
          const wasCompact = this._compact;
          this._compact = entry.contentRect.width < 400;
          if (wasCompact !== this._compact) this._render();
        }
      }
    });
  }

  connectedCallback() { this._ro.observe(this); }
  disconnectedCallback() { this._ro.unobserve(this); }

  static getConfigElement() {
    return document.createElement("feuerwehr-time-tracker-card-editor");
  }

  static async getStubConfig(hass) {
    const entities = Object.keys(hass.states).filter(
      (e) => e.startsWith("sensor.") && hass.states[e].attributes?.unit_of_measurement === "h"
    );
    const find = (suffix) => entities.find((e) => e.includes(suffix)) || "";
    return {
      ...DEFAULTS,
      entity_einsatz: find("alarm_hours"),
      entity_probe: find("training_hours"),
      entity_geratehaus: find("station_hours"),
      entity_gesamt: find("total_hours"),
    };
  }

  setConfig(config) {
    if (!config.entity_einsatz && !config.entity_probe && !config.entity_geratehaus && !config.entity_gesamt) {
      throw new Error("Bitte mindestens eine Entity konfigurieren.");
    }
    this._config = { ...DEFAULTS, ...config };
    if (!Array.isArray(this._config.category_order)) {
      this._config.category_order = [...DEFAULTS.category_order];
    }
    if (this._config.layout === "large") this._compact = false;
    if (this._config.layout === "compact") this._compact = true;
    this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  get hass() { return this._hass; }
  getCardSize() { return this._compact ? 3 : 2; }

  _getChips() {
    const c = this._config;
    const h = this._hass;
    const all = {
      einsatz: { label: c.label_einsatz, value: getVal(h, c.entity_einsatz), color: c.color_einsatz, show: c.show_einsatz },
      probe: { label: c.label_probe, value: getVal(h, c.entity_probe), color: c.color_probe, show: c.show_probe },
      geratehaus: { label: c.label_geratehaus, value: getVal(h, c.entity_geratehaus), color: c.color_geratehaus, show: c.show_geratehaus },
      gesamt: { label: c.label_gesamt, value: getVal(h, c.entity_gesamt), color: c.color_gesamt, show: c.show_total && c.total_display === "chip" },
    };
    const order = c.category_order || DEFAULTS.category_order;
    return order.filter((k) => all[k]?.show).map((k) => all[k]);
  }

  _render() {
    if (!this._config || !this._hass) return;
    const c = this._config;
    const h = this._hass;
    const gesamt = getVal(h, c.entity_gesamt);
    const chips = this._getChips();
    const showProminent = c.show_total && c.total_display === "prominent";

    let content;
    if (this._compact) {
      content = `
        ${c.show_header ? `<div class="header compact-header">${c.title}</div>` : ""}
        <div class="content compact">
          ${showProminent ? `
            <div class="compact-prominent">
              <span class="total-value">${fmt(gesamt)}</span>
              <span class="total-label">${c.label_gesamt}</span>
            </div>
          ` : ""}
          <div class="chips-grid">
            ${chips.map((ch) => `
              <div class="chip-compact" style="
                background: ${hexToRgba(ch.color, 0.12)};
                border-color: ${hexToRgba(ch.color, 0.25)};
              ">
                <span class="chip-label-compact" style="color: ${ch.color};">${ch.label}</span>
                <span class="chip-value-compact">${valText(ch.value)}</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    } else {
      content = `
        ${c.show_header ? `<div class="header">${c.title}</div>` : ""}
        <div class="content large">
          ${showProminent ? `
            <div class="total-section">
              <span class="total-value">${fmt(gesamt)}</span>
              <span class="total-label">${c.label_gesamt}</span>
            </div>
          ` : ""}
          <div class="chips-row ${showProminent ? "has-prominent" : ""}">
            ${chips.map((ch) => `
              <div class="chip" style="
                background: ${hexToRgba(ch.color, 0.12)};
                border-color: ${hexToRgba(ch.color, 0.25)};
              ">
                <span class="chip-label" style="color: ${ch.color};">${ch.label}</span>
                <span class="chip-value">${valText(ch.value)}</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    }

    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLES}</style>
      <ha-card>${content}</ha-card>
    `;
  }
}

/* ═══════════════════════════════════════════
   EDITOR
   ═══════════════════════════════════════════ */
class FeuerwehrTimeTrackerCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._entries = [];
    this._discovered = false;
    this._built = false;
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
    if (!Array.isArray(this._config.category_order)) {
      this._config.category_order = [...DEFAULTS.category_order];
    }
    if (!this._built) {
      this._buildEditor();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (hass && !this._discovered) {
      this._discovered = true;
      this._discoverEntities();
    }
  }

  get hass() { return this._hass; }

  async _discoverEntities() {
    try {
      const entities = await this._hass.callWS({ type: "config/entity_registry/list" });
      const mine = entities.filter((e) => e.platform === "feuerwehr_time_tracker");
      const grouped = {};
      for (const e of mine) {
        const eid = e.config_entry_id;
        if (!grouped[eid]) grouped[eid] = {};
        if (e.unique_id?.endsWith("_einsatz")) grouped[eid].entity_einsatz = e.entity_id;
        if (e.unique_id?.endsWith("_probe")) grouped[eid].entity_probe = e.entity_id;
        if (e.unique_id?.endsWith("_geratehaus")) grouped[eid].entity_geratehaus = e.entity_id;
        if (e.unique_id?.endsWith("_gesamt")) grouped[eid].entity_gesamt = e.entity_id;
      }
      this._entries = Object.entries(grouped).map(([id, ents]) => ({ entry_id: id, ...ents }));

      if (this._entries.length > 0 && !this._config.entity_einsatz && !this._config.entity_probe) {
        const first = this._entries[0];
        this._config = {
          ...this._config,
          entry_id: first.entry_id,
          entity_einsatz: first.entity_einsatz,
          entity_probe: first.entity_probe,
          entity_geratehaus: first.entity_geratehaus,
          entity_gesamt: first.entity_gesamt,
        };
        this._fireChanged();
        this._buildEditor();
      }
    } catch (e) {}
  }

  _fireChanged() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: { ...this._config } },
        bubbles: true,
        composed: true,
      })
    );
  }

  _buildEditor() {
    this._built = true;
    const c = this._config;
    const order = c.category_order || DEFAULTS.category_order;

    this.shadowRoot.innerHTML = `
      <style>${EDITOR_STYLES}</style>
      <div class="editor">
        <div class="section" id="sec-layout">
          <div class="section-header"><span class="section-title">Layout</span></div>
          <div class="row">
            <label>Darstellung</label>
            <select data-field="layout">
              <option value="auto" ${c.layout === "auto" ? "selected" : ""}>Auto (Responsive)</option>
              <option value="large" ${c.layout === "large" ? "selected" : ""}>Gross</option>
              <option value="compact" ${c.layout === "compact" ? "selected" : ""}>Kompakt</option>
            </select>
          </div>
          <div class="row">
            <label>Titel</label>
            <input type="text" data-input="title" value="${this._esc(c.title)}" />
          </div>
          <div class="row">
            <label>Titel anzeigen</label>
            <input type="checkbox" data-toggle="show_header" ${c.show_header ? "checked" : ""} />
          </div>
        </div>
        <div id="category-sections"></div>
      </div>
    `;

    this._renderCategorySections();
    this._bindGlobalEvents();
  }

  _esc(str) {
    return (str || "").replace(/"/g, "&quot;");
  }

  _renderCategorySections() {
    const container = this.shadowRoot.getElementById("category-sections");
    if (!container) return;
    container.innerHTML = "";
    const order = this._config.category_order || DEFAULTS.category_order;

    order.forEach((key, idx) => {
      const section = document.createElement("div");
      section.className = "section";
      section.dataset.category = key;

      const isGesamt = key === "gesamt";
      const showKey = isGesamt ? "show_total" : `show_${key}`;
      const labelKey = `label_${key}`;
      const colorKey = `color_${key}`;
      const entityKey = `entity_${key}`;
      const title = { einsatz: "Einsatz", probe: "Probe", geratehaus: "Gerätehaus", gesamt: "Gesamt" }[key];

      let extraRows = "";
      if (isGesamt) {
        extraRows = `
          <div class="row">
            <label>Darstellung</label>
            <select data-field="total_display">
              <option value="prominent" ${this._config.total_display === "prominent" ? "selected" : ""}>Prominent (grosse Zahl)</option>
              <option value="chip" ${this._config.total_display === "chip" ? "selected" : ""}>Als Kachel</option>
              <option value="hidden" ${this._config.total_display === "hidden" ? "selected" : ""}>Versteckt</option>
            </select>
          </div>
        `;
      }

      section.innerHTML = `
        <div class="section-header">
          <span class="section-title">${title}</span>
          <div class="order-buttons">
            <button class="order-btn" data-move="up" data-key="${key}" ${idx === 0 ? "disabled" : ""}>&#9650;</button>
            <button class="order-btn" data-move="down" data-key="${key}" ${idx === order.length - 1 ? "disabled" : ""}>&#9660;</button>
          </div>
        </div>
        <div class="row">
          <label>Anzeigen</label>
          <input type="checkbox" data-toggle="${showKey}" ${this._config[showKey] ? "checked" : ""} />
        </div>
        ${extraRows}
        <div class="row">
          <label>Bezeichnung</label>
          <input type="text" data-input="${labelKey}" value="${this._esc(this._config[labelKey])}" />
        </div>
        <div class="row">
          <label>Farbe</label>
          <div class="color-row">
            <input type="color" data-input="${colorKey}" value="${this._config[colorKey] || "#888888"}" />
            <input type="text" class="color-text" data-input="${colorKey}" value="${this._config[colorKey] || "#888888"}" />
          </div>
        </div>
        <div class="row">
          <label>Entity</label>
          <input type="text" data-input="${entityKey}" value="${this._esc(this._config[entityKey])}" />
        </div>
      `;

      container.appendChild(section);
    });

    this._bindCategoryEvents(container);
  }

  _bindGlobalEvents() {
    const root = this.shadowRoot;
    root.getElementById("sec-layout").querySelectorAll("[data-input]").forEach((el) => {
      el.addEventListener("input", (e) => {
        this._config[e.target.dataset.input] = e.target.value;
        this._fireChanged();
      });
    });
    root.getElementById("sec-layout").querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("change", (e) => {
        this._config[e.target.dataset.toggle] = e.target.checked;
        this._fireChanged();
      });
    });
    root.getElementById("sec-layout").querySelectorAll("[data-field]").forEach((el) => {
      el.addEventListener("change", (e) => {
        this._config[e.target.dataset.field] = e.target.value;
        this._fireChanged();
      });
    });
  }

  _bindCategoryEvents(container) {
    container.querySelectorAll("[data-input]").forEach((el) => {
      el.addEventListener("input", (e) => {
        this._config[e.target.dataset.input] = e.target.value;
        this._fireChanged();
        // Sync paired color inputs
        if (e.target.dataset.input.startsWith("color_")) {
          const section = e.target.closest(".section");
          section.querySelectorAll(`[data-input="${e.target.dataset.input}"]`).forEach((sibling) => {
            if (sibling !== e.target) sibling.value = e.target.value;
          });
        }
      });
    });
    container.querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("change", (e) => {
        this._config[e.target.dataset.toggle] = e.target.checked;
        this._fireChanged();
      });
    });
    container.querySelectorAll("[data-field]").forEach((el) => {
      el.addEventListener("change", (e) => {
        this._config[e.target.dataset.field] = e.target.value;
        this._fireChanged();
      });
    });
    container.querySelectorAll("[data-move]").forEach((el) => {
      el.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-move]");
        const key = btn.dataset.key;
        const dir = btn.dataset.move;
        const order = [...(this._config.category_order || DEFAULTS.category_order)];
        const idx = order.indexOf(key);
        if (dir === "up" && idx > 0) {
          [order[idx - 1], order[idx]] = [order[idx], order[idx - 1]];
        } else if (dir === "down" && idx < order.length - 1) {
          [order[idx], order[idx + 1]] = [order[idx + 1], order[idx]];
        }
        this._config.category_order = order;
        this._fireChanged();
        this._renderCategorySections();
      });
    });
  }
}

/* ═══════════════════════════════════════════
   REGISTRATION
   ═══════════════════════════════════════════ */
customElements.define("feuerwehr-time-tracker-card", FeuerwehrTimeTrackerCard);
customElements.define("feuerwehr-time-tracker-card-editor", FeuerwehrTimeTrackerCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "feuerwehr-time-tracker-card",
  name: "Feuerwehr Zeittracker",
  description: "Zeigt die erfassten Stunden der Feuerwehr nach Kategorien an.",
  preview: true,
  documentationURL: "https://github.com/larsbaum/feuerwehr_time_tracker",
});
