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
  color_einsatz: "#e53935",
  color_probe: "#1e88e5",
  color_geratehaus: "#43a047",
  label_einsatz: "Einsatz",
  label_probe: "Probe",
  label_geratehaus: "Gerätehaus",
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

function val(hass, entityId) {
  if (!entityId || !hass) return 0;
  const s = hass.states[entityId];
  if (!s || s.state === "unavailable" || s.state === "unknown") return null;
  return Number(s.state);
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
    flex-shrink: 0;
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
  }
  .chips-row {
    display: flex;
    gap: 10px;
    flex-wrap: nowrap;
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
    min-width: 130px;
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
`;

const EDITOR_STYLES = `
  .editor { padding: 8px 0; }
  .section {
    margin-bottom: 16px;
    border: 1px solid var(--divider-color, rgba(128,128,128,0.2));
    border-radius: 12px;
    padding: 12px;
  }
  .section-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--primary-text-color);
    margin-bottom: 8px;
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

  connectedCallback() {
    this._ro.observe(this);
  }

  disconnectedCallback() {
    this._ro.unobserve(this);
  }

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
    if (this._config.layout === "large") this._compact = false;
    if (this._config.layout === "compact") this._compact = true;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  get hass() {
    return this._hass;
  }

  getCardSize() {
    return this._compact ? 3 : 2;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const c = this._config;
    const h = this._hass;

    const einsatz = val(h, c.entity_einsatz);
    const probe = val(h, c.entity_probe);
    const geratehaus = val(h, c.entity_geratehaus);
    const gesamt = val(h, c.entity_gesamt);

    const chips = [];
    if (c.show_einsatz) chips.push({ label: c.label_einsatz, value: einsatz, color: c.color_einsatz });
    if (c.show_probe) chips.push({ label: c.label_probe, value: probe, color: c.color_probe });
    if (c.show_geratehaus) chips.push({ label: c.label_geratehaus, value: geratehaus, color: c.color_geratehaus });

    const valText = (v) => (v !== null ? fmt(v) + " h" : "—");

    let content;
    if (this._compact) {
      const allChips = [...chips];
      if (c.show_total) {
        allChips.push({ label: "Gesamt", value: gesamt, color: null, isVar: true });
      }
      content = `
        ${c.show_header ? `<div class="header compact-header">${c.title}</div>` : ""}
        <div class="content compact">
          <div class="chips-grid">
            ${allChips.map((ch) => `
              <div class="chip-compact" style="
                background: ${ch.isVar ? "rgba(128,128,128,0.08)" : hexToRgba(ch.color, 0.12)};
                border-color: ${ch.isVar ? "rgba(128,128,128,0.22)" : hexToRgba(ch.color, 0.25)};
              ">
                <span class="chip-label-compact" style="color: ${ch.isVar ? "var(--secondary-text-color, #888)" : ch.color};">${ch.label}</span>
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
          ${c.show_total ? `
            <div class="total-section">
              <span class="total-value">${fmt(gesamt)}</span>
              <span class="total-label">Stunden dieses Jahr</span>
            </div>
          ` : ""}
          <div class="chips-row">
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
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
    this._renderEditor();
  }

  set hass(hass) {
    this._hass = hass;
    if (hass && !this._discovered) {
      this._discovered = true;
      this._discoverEntities();
    }
  }

  get hass() {
    return this._hass;
  }

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
        this._updateConfig({
          entry_id: first.entry_id,
          entity_einsatz: first.entity_einsatz,
          entity_probe: first.entity_probe,
          entity_geratehaus: first.entity_geratehaus,
          entity_gesamt: first.entity_gesamt,
        });
      }
      this._renderEditor();
    } catch (e) {
      // Entity registry not available
    }
  }

  _updateConfig(changes) {
    this._config = { ...this._config, ...changes };
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      })
    );
  }

  _renderEditor() {
    const c = this._config;

    const instanceSection = this._entries.length > 1 ? `
      <div class="section">
        <div class="section-title">Instanz</div>
        <div class="row">
          <label>Tracker-Instanz</label>
          <select data-field="entry_id">
            ${this._entries.map((en) =>
              `<option value="${en.entry_id}" ${c.entry_id === en.entry_id ? "selected" : ""}>${en.entity_gesamt || en.entry_id}</option>`
            ).join("")}
          </select>
        </div>
      </div>
    ` : "";

    const catSection = (title, key, color) => `
      <div class="section">
        <div class="section-title">${title}</div>
        <div class="row">
          <label>Anzeigen</label>
          <input type="checkbox" data-toggle="show_${key}" ${c[`show_${key}`] ? "checked" : ""} />
        </div>
        <div class="row">
          <label>Bezeichnung</label>
          <input type="text" data-input="label_${key}" value="${c[`label_${key}`] || ""}" />
        </div>
        <div class="row">
          <label>Farbe</label>
          <div class="color-row">
            <input type="color" data-input="color_${key}" value="${color || "#888888"}" />
            <input type="text" class="color-text" data-input="color_${key}" value="${color || "#888888"}" />
          </div>
        </div>
        <div class="row">
          <label>Entity</label>
          <input type="text" data-input="entity_${key}" value="${c[`entity_${key}`] || ""}" />
        </div>
      </div>
    `;

    this.shadowRoot.innerHTML = `
      <style>${EDITOR_STYLES}</style>
      <div class="editor">
        ${instanceSection}

        <div class="section">
          <div class="section-title">Layout</div>
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
            <input type="text" data-input="title" value="${c.title || ""}" />
          </div>
          <div class="row">
            <label>Titel anzeigen</label>
            <input type="checkbox" data-toggle="show_header" ${c.show_header ? "checked" : ""} />
          </div>
          <div class="row">
            <label>Gesamt anzeigen</label>
            <input type="checkbox" data-toggle="show_total" ${c.show_total ? "checked" : ""} />
          </div>
        </div>

        ${catSection("Einsatz", "einsatz", c.color_einsatz)}
        ${catSection("Probe", "probe", c.color_probe)}
        ${catSection("Gerätehaus", "geratehaus", c.color_geratehaus)}

        <div class="section">
          <div class="section-title">Gesamt</div>
          <div class="row">
            <label>Entity</label>
            <input type="text" data-input="entity_gesamt" value="${c.entity_gesamt || ""}" />
          </div>
        </div>
      </div>
    `;

    // Bind events
    this.shadowRoot.querySelectorAll("[data-input]").forEach((el) => {
      el.addEventListener("input", (e) => {
        this._updateConfig({ [e.target.dataset.input]: e.target.value });
      });
    });
    this.shadowRoot.querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("change", (e) => {
        this._updateConfig({ [e.target.dataset.toggle]: e.target.checked });
      });
    });
    this.shadowRoot.querySelectorAll("[data-field]").forEach((el) => {
      el.addEventListener("change", (e) => {
        const field = e.target.dataset.field;
        if (field === "entry_id") {
          const entry = this._entries.find((en) => en.entry_id === e.target.value);
          if (entry) {
            this._updateConfig({
              entry_id: entry.entry_id,
              entity_einsatz: entry.entity_einsatz,
              entity_probe: entry.entity_probe,
              entity_geratehaus: entry.entity_geratehaus,
              entity_gesamt: entry.entity_gesamt,
            });
          }
        } else {
          this._updateConfig({ [field]: e.target.value });
        }
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
