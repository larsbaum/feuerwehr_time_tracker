(async () => {
  // Wait for Lovelace to be loaded before accessing LitElement
  const MAX_WAIT = 15000;
  const start = Date.now();
  while (!customElements.get("ha-panel-lovelace") && Date.now() - start < MAX_WAIT) {
    await new Promise((r) => setTimeout(r, 100));
  }
  if (!customElements.get("ha-panel-lovelace")) return;

  const LitElement = Object.getPrototypeOf(customElements.get("ha-panel-lovelace"));
  const { html, css } = LitElement.prototype.constructor;

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

  /* ═══════════════════════════════════════════
     CARD
     ═══════════════════════════════════════════ */
  class FeuerwehrTimeTrackerCard extends LitElement {
    static get properties() {
      return {
        hass: { attribute: false },
        _config: { state: true },
        _compact: { state: true },
      };
    }

    static getConfigElement() {
      return document.createElement("feuerwehr-time-tracker-card-editor");
    }

    static async getStubConfig(hass) {
      const entities = Object.keys(hass.states).filter((e) =>
        e.startsWith("sensor.") && hass.states[e].attributes?.unit_of_measurement === "h"
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

    constructor() {
      super();
      this._compact = false;
      this._ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const w = entry.contentRect.width;
          const layout = this._config?.layout || "auto";
          if (layout === "auto") {
            this._compact = w < 400;
          }
        }
      });
    }

    connectedCallback() {
      super.connectedCallback();
      this._ro.observe(this);
    }

    disconnectedCallback() {
      super.disconnectedCallback();
      this._ro.unobserve(this);
    }

    setConfig(config) {
      if (
        !config.entity_einsatz &&
        !config.entity_probe &&
        !config.entity_geratehaus &&
        !config.entity_gesamt
      ) {
        throw new Error("Bitte mindestens eine Entity konfigurieren.");
      }
      this._config = { ...DEFAULTS, ...config };
      if (this._config.layout === "large") this._compact = false;
      if (this._config.layout === "compact") this._compact = true;
    }

    getCardSize() {
      return this._compact ? 3 : 2;
    }

    _val(entityId) {
      if (!entityId || !this.hass) return 0;
      const s = this.hass.states[entityId];
      if (!s || s.state === "unavailable" || s.state === "unknown") return null;
      return Number(s.state);
    }

    render() {
      if (!this._config || !this.hass) return html``;
      const c = this._config;

      const einsatz = this._val(c.entity_einsatz);
      const probe = this._val(c.entity_probe);
      const geratehaus = this._val(c.entity_geratehaus);
      const gesamt = this._val(c.entity_gesamt);

      const chips = [];
      if (c.show_einsatz)
        chips.push({ label: c.label_einsatz, value: einsatz, color: c.color_einsatz, icon: "mdi:fire-truck" });
      if (c.show_probe)
        chips.push({ label: c.label_probe, value: probe, color: c.color_probe, icon: "mdi:account-group" });
      if (c.show_geratehaus)
        chips.push({ label: c.label_geratehaus, value: geratehaus, color: c.color_geratehaus, icon: "mdi:home-group" });

      if (this._compact) {
        return this._renderCompact(c, chips, gesamt);
      }
      return this._renderLarge(c, chips, gesamt);
    }

    _renderLarge(c, chips, gesamt) {
      return html`
        <ha-card>
          ${c.show_header
            ? html`<div class="header">${c.title}</div>`
            : ""}
          <div class="content large">
            ${c.show_total
              ? html`
                  <div class="total-section">
                    <span class="total-value">${fmt(gesamt)}</span>
                    <span class="total-label">Stunden dieses Jahr</span>
                  </div>
                `
              : ""}
            <div class="chips-row">
              ${chips.map(
                (ch) => html`
                  <div
                    class="chip"
                    style="
                      background: ${hexToRgba(ch.color, 0.12)};
                      border-color: ${hexToRgba(ch.color, 0.25)};
                    "
                  >
                    <span class="chip-label" style="color: ${ch.color};">${ch.label}</span>
                    <span class="chip-value">${ch.value !== null ? fmt(ch.value) + " h" : "—"}</span>
                  </div>
                `
              )}
            </div>
          </div>
        </ha-card>
      `;
    }

    _renderCompact(c, chips, gesamt) {
      const allChips = [...chips];
      if (c.show_total) {
        allChips.push({
          label: "Gesamt",
          value: gesamt,
          color: "var(--secondary-text-color, #888)",
          icon: "mdi:sigma",
          isVar: true,
        });
      }
      return html`
        <ha-card>
          ${c.show_header
            ? html`<div class="header compact-header">${c.title}</div>`
            : ""}
          <div class="content compact">
            <div class="chips-grid">
              ${allChips.map(
                (ch) => html`
                  <div
                    class="chip-compact"
                    style="
                      background: ${ch.isVar ? "rgba(128,128,128,0.08)" : hexToRgba(ch.color, 0.12)};
                      border-color: ${ch.isVar ? "rgba(128,128,128,0.22)" : hexToRgba(ch.color, 0.25)};
                    "
                  >
                    <span class="chip-label-compact" style="color: ${ch.isVar ? ch.color : ch.color};">${ch.label}</span>
                    <span class="chip-value-compact">${ch.value !== null ? fmt(ch.value) + " h" : "—"}</span>
                  </div>
                `
              )}
            </div>
          </div>
        </ha-card>
      `;
    }

    static get styles() {
      return css`
        :host {
          display: block;
        }
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

        /* Large layout */
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
        .chip:hover {
          transform: scale(1.02);
        }
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

        /* Compact layout */
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
        .chip-compact:hover {
          transform: scale(1.03);
        }
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
    }
  }

  /* ═══════════════════════════════════════════
     EDITOR
     ═══════════════════════════════════════════ */
  class FeuerwehrTimeTrackerCardEditor extends LitElement {
    static get properties() {
      return {
        hass: { attribute: false },
        _config: { state: true },
        _entries: { state: true },
      };
    }

    constructor() {
      super();
      this._config = {};
      this._entries = [];
    }

    setConfig(config) {
      this._config = { ...DEFAULTS, ...config };
    }

    set hass(hass) {
      const old = this._hass;
      this._hass = hass;
      this.requestUpdate("hass", old);
      if (hass && !old) {
        this._discoverEntities();
      }
    }

    get hass() {
      return this._hass;
    }

    async _discoverEntities() {
      try {
        const entities = await this.hass.callWS({ type: "config/entity_registry/list" });
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

        if (
          this._entries.length > 0 &&
          !this._config.entity_einsatz &&
          !this._config.entity_probe
        ) {
          const first = this._entries[0];
          this._updateConfig({
            entry_id: first.entry_id,
            entity_einsatz: first.entity_einsatz,
            entity_probe: first.entity_probe,
            entity_geratehaus: first.entity_geratehaus,
            entity_gesamt: first.entity_gesamt,
          });
        }
      } catch (e) {
        // Entity registry not available in preview
      }
    }

    _updateConfig(changes) {
      this._config = { ...this._config, ...changes };
      const ev = new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      });
      this.dispatchEvent(ev);
    }

    _handleInput(field, e) {
      this._updateConfig({ [field]: e.target.value });
    }

    _handleToggle(field, e) {
      this._updateConfig({ [field]: e.target.checked });
    }

    _handleSelect(field, e) {
      this._updateConfig({ [field]: e.target.value });
    }

    _handleEntry(e) {
      const entryId = e.target.value;
      const entry = this._entries.find((en) => en.entry_id === entryId);
      if (entry) {
        this._updateConfig({
          entry_id: entry.entry_id,
          entity_einsatz: entry.entity_einsatz,
          entity_probe: entry.entity_probe,
          entity_geratehaus: entry.entity_geratehaus,
          entity_gesamt: entry.entity_gesamt,
        });
      }
    }

    render() {
      if (!this.hass || !this._config) return html``;

      return html`
        <div class="editor">
          ${this._entries.length > 1
            ? html`
                <div class="section">
                  <div class="section-title">Instanz</div>
                  <div class="row">
                    <label>Tracker-Instanz</label>
                    <select @change=${this._handleEntry}>
                      ${this._entries.map(
                        (en) => html`
                          <option value=${en.entry_id} ?selected=${this._config.entry_id === en.entry_id}>
                            ${en.entity_gesamt || en.entry_id}
                          </option>
                        `
                      )}
                    </select>
                  </div>
                </div>
              `
            : ""}

          <div class="section">
            <div class="section-title">Layout</div>
            <div class="row">
              <label>Darstellung</label>
              <select
                .value=${this._config.layout}
                @change=${(e) => this._handleSelect("layout", e)}
              >
                <option value="auto">Auto (Responsive)</option>
                <option value="large">Gross</option>
                <option value="compact">Kompakt</option>
              </select>
            </div>
            <div class="row">
              <label>Titel</label>
              <input
                type="text"
                .value=${this._config.title}
                @input=${(e) => this._handleInput("title", e)}
              />
            </div>
            <div class="row">
              <label>Titel anzeigen</label>
              <input
                type="checkbox"
                .checked=${this._config.show_header}
                @change=${(e) => this._handleToggle("show_header", e)}
              />
            </div>
            <div class="row">
              <label>Gesamt anzeigen</label>
              <input
                type="checkbox"
                .checked=${this._config.show_total}
                @change=${(e) => this._handleToggle("show_total", e)}
              />
            </div>
          </div>

          ${this._renderCategorySection("Einsatz", "einsatz", this._config.color_einsatz)}
          ${this._renderCategorySection("Probe", "probe", this._config.color_probe)}
          ${this._renderCategorySection("Gerätehaus", "geratehaus", this._config.color_geratehaus)}

          <div class="section">
            <div class="section-title">Gesamt</div>
            <div class="row">
              <label>Entity</label>
              <input
                type="text"
                .value=${this._config.entity_gesamt || ""}
                @input=${(e) => this._handleInput("entity_gesamt", e)}
              />
            </div>
          </div>
        </div>
      `;
    }

    _renderCategorySection(title, key, color) {
      return html`
        <div class="section">
          <div class="section-title">${title}</div>
          <div class="row">
            <label>Anzeigen</label>
            <input
              type="checkbox"
              .checked=${this._config[`show_${key}`]}
              @change=${(e) => this._handleToggle(`show_${key}`, e)}
            />
          </div>
          <div class="row">
            <label>Bezeichnung</label>
            <input
              type="text"
              .value=${this._config[`label_${key}`]}
              @input=${(e) => this._handleInput(`label_${key}`, e)}
            />
          </div>
          <div class="row">
            <label>Farbe</label>
            <div class="color-row">
              <input
                type="color"
                .value=${color}
                @input=${(e) => this._handleInput(`color_${key}`, e)}
              />
              <input
                type="text"
                class="color-text"
                .value=${color}
                @input=${(e) => this._handleInput(`color_${key}`, e)}
              />
            </div>
          </div>
          <div class="row">
            <label>Entity</label>
            <input
              type="text"
              .value=${this._config[`entity_${key}`] || ""}
              @input=${(e) => this._handleInput(`entity_${key}`, e)}
            />
          </div>
        </div>
      `;
    }

    static get styles() {
      return css`
        .editor {
          padding: 8px 0;
        }
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
        input[type="text"],
        select {
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
})();
