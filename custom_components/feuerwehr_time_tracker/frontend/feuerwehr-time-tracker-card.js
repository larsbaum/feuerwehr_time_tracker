/* ───────────────────────────────────────────
   DEFAULTS
   ─────────────────────────────────────────── */
const DEFAULTS = {
  title: "Feuerwehr Zeittracker",
  show_header: true,
  layout: "auto",
  show_einsatz: true,
  show_probe: true,
  show_sonstiges: true,
  show_total: true,
  total_display: "prominent",
  color_einsatz: "#e53935",
  color_probe: "#1e88e5",
  color_sonstiges: "#43a047",
  color_gesamt: "#888888",
  label_einsatz: "Einsatz",
  label_probe: "Probe",
  label_sonstiges: "Sonstiges",
  label_gesamt: "Gesamt",
  category_order: ["einsatz", "probe", "sonstiges", "gesamt"],
};

function normalizeCategoryOrder(order) {
  // Drop unknown keys (e.g. legacy "geratehaus" from old stored configs)
  // and append any missing known categories so none silently disappear.
  const known = DEFAULTS.category_order;
  const cleaned = (Array.isArray(order) ? order : []).filter((k) => known.includes(k));
  for (const k of known) {
    if (!cleaned.includes(k)) cleaned.push(k);
  }
  return cleaned;
}

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
  :host { display: block; height: 100%; }
  ha-card {
    padding: 12px 14px;
    box-sizing: border-box;
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .too-small {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    font-size: 11px;
    font-weight: 600;
    color: var(--warning-color, #ff9800);
    text-align: center;
    padding: 4px;
  }
  .hc-row {
    display: flex;
    align-items: center;
    height: 100%;
    gap: 8px;
    overflow: hidden;
    min-width: 0;
  }
  .hc-row-title {
    font-weight: 700;
    color: var(--primary-text-color);
    opacity: 0.95;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 1;
    min-width: 0;
  }
  .hc-total {
    display: flex;
    align-items: baseline;
    gap: 5px;
    flex-shrink: 0;
    white-space: nowrap;
  }
  .hc-total-value {
    font-weight: 800;
    color: var(--primary-text-color);
    line-height: 1;
  }
  .hc-total-label {
    font-weight: 700;
    color: var(--secondary-text-color);
    white-space: nowrap;
  }
  .hc-chips {
    display: flex;
    gap: 6px;
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }
  .hc-chip {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 4px;
    border-radius: 10px;
    border: 1px solid;
    flex: 1;
    min-width: 0;
    box-sizing: border-box;
    overflow: hidden;
  }
  .hc-chip-label {
    font-weight: 700;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 1;
    min-width: 0;
  }
  .hc-chip-value {
    font-weight: 800;
    color: var(--primary-text-color);
    white-space: nowrap;
    flex-shrink: 0;
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
    flex: 1;
    min-height: 0;
  }
  .content.large .total-section {
    align-self: center;
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
    flex: 1 1 0;
    min-width: 0;
    box-sizing: border-box;
  }
  .chip {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: 10px 8px;
    border-radius: 12px;
    border: 1px solid;
    flex: 1 1 0;
    min-width: 0;
    box-sizing: border-box;
    transition: transform 0.15s ease;
    overflow: hidden;
    container-type: inline-size;
  }
  .chip:hover { transform: scale(1.02); }
  .chip-label {
    font-size: clamp(8px, 11cqi, 12px);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }
  .chip-value {
    font-size: clamp(13px, 18cqi, 20px);
    font-weight: 800;
    color: var(--primary-text-color);
    white-space: nowrap;
  }
  .content.compact {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    justify-content: center;
  }
  .chips-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    width: 100%;
    box-sizing: border-box;
  }
  .chips-grid .chip-compact:last-child:nth-child(odd) {
    grid-column: 1 / -1;
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
    overflow: hidden;
    transition: transform 0.15s ease;
    container-type: inline-size;
  }
  .chip-compact:hover { transform: scale(1.03); }
  .chip-label-compact {
    font-size: clamp(7px, 10cqi, 11px);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }
  .chip-value-compact {
    font-size: clamp(10px, 15cqi, 16px);
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
    this._w = 400;
    this._h = 116;
    this._ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = Math.round(entry.contentRect.width);
        const h = Math.round(entry.contentRect.height);
        if (w === this._w && h === this._h) return;
        this._w = w;
        this._h = h;
        if (this._config.layout === "auto") {
          this._compact = w < 400;
        }
        this._render();
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
      entity_sonstiges: find("other_hours"),
      entity_gesamt: find("total_hours"),
    };
  }

  setConfig(config) {
    if (!config.entity_einsatz && !config.entity_probe && !config.entity_sonstiges && !config.entity_gesamt) {
      throw new Error("Bitte mindestens eine Entity konfigurieren.");
    }
    this._config = { ...DEFAULTS, ...config };
    this._config.category_order = normalizeCategoryOrder(this._config.category_order);
    if (this._config.layout === "large") this._compact = false;
    if (this._config.layout === "compact") this._compact = true;
    this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  get hass() { return this._hass; }
  getCardSize() { return this._compact ? 3 : 2; }

  getLayoutOptions() {
    return {
      grid_rows: this._compact ? 3 : 2,
      grid_columns: 4,
      grid_min_rows: 1,
      grid_max_rows: 8,
    };
  }

  _computeLayout(isCompact, chipCount) {
    const w = this._w;
    const h = this._h;
    if (!w || !h) return { tooSmall: false, isRow: false, isCompact, pad: 12, padH: 14, titleSize: 15, chipValSize: 20, chipLblSize: 12, chipPadV: 8, chipPadH: 8, totalValSize: 32, totalLblSize: 14 };
    if (h < 36 || w < 100) return { tooSmall: true };

    const isRow = h < 90;
    // row-mode: minimal padding; col-mode: at least 8 px for visual breathing room
    const pad  = isRow
      ? Math.round(Math.min(8,  Math.max(3, h * 0.07)))
      : Math.round(Math.min(12, Math.max(8, h * 0.09)));
    const padH   = Math.round(Math.min(14, Math.max(8, w * 0.025)));
    const innerH = h - pad * 2;

    let chipSingleH, titleSize;
    if (isRow) {
      titleSize   = Math.round(Math.min(14, Math.max(10, innerH * 0.27)));
      chipSingleH = innerH;
    } else {
      titleSize = Math.round(Math.min(15, Math.max(11, innerH * 0.14)));
      const mb        = Math.max(3, Math.round(pad * 0.4));
      const titleH    = titleSize * 1.5 + mb;
      const chipAreaH = Math.max(20, innerH - titleH);

      if (isCompact) {
        // chips are in a 2-col grid → each chip gets only 1/chipRows of chipAreaH
        const chipRows = Math.max(1, Math.ceil((chipCount || 1) / 2));
        chipSingleH = Math.max(16, (chipAreaH - (chipRows - 1) * 6) / chipRows);
      } else {
        // large mode: chip content is sized to ~75 % of chipAreaH;
        // chips are centered via align-items in _dynStyle
        chipSingleH = chipAreaH;
      }
    }

    const chipValSize  = Math.round(Math.min(32, Math.max(10, chipSingleH * 0.38)));
    const chipLblSize  = Math.round(Math.min(13, Math.max(8,  chipSingleH * 0.17)));
    const chipPadV     = Math.round(Math.min(12, Math.max(2,  chipSingleH * 0.07)));
    const chipPadH     = Math.round(Math.min(12, Math.max(5,  padH * 0.7)));
    const totalValSize = Math.round(Math.min(42, Math.max(14, chipSingleH * 0.52)));
    const totalLblSize = Math.round(Math.min(18, Math.max(9,  chipSingleH * 0.22)));

    if (chipValSize < 9) return { tooSmall: true };
    return { tooSmall: false, isRow, isCompact, pad, padH, titleSize, chipValSize, chipLblSize, chipPadV, chipPadH, totalValSize, totalLblSize };
  }

  _dynStyle({ pad, padH, titleSize, chipValSize, chipLblSize, chipPadV, chipPadH, totalValSize, totalLblSize, isRow, isCompact }) {
    const mb = Math.max(3, Math.round(pad * 0.4));
    // In large mode chips don't stretch; they're centered in the chips-row
    const chipsRowExtra = (!isRow && !isCompact) ? 'align-items: center;' : '';
    return `
      ha-card { padding: ${pad}px ${padH}px; }
      .header { font-size: ${titleSize}px; margin-bottom: ${mb}px; }
      .compact-header { font-size: ${Math.min(11, titleSize)}px; margin-bottom: ${mb}px; }
      .total-value { font-size: ${totalValSize}px; }
      .total-label { font-size: ${totalLblSize}px; }
      .compact-prominent .total-value { font-size: ${Math.round(totalValSize * 0.8)}px; }
      .compact-prominent .total-label { font-size: ${Math.round(totalLblSize * 0.85)}px; }
      .compact-prominent { margin-bottom: ${mb}px; }
      .chip { padding: ${chipPadV}px ${chipPadH}px; }
      .chip-label { font-size: ${chipLblSize}px; }
      .chip-value { font-size: ${chipValSize}px; }
      .chips-row { ${chipsRowExtra} }
      .chip-compact { padding: ${Math.round(chipPadV * 0.8)}px ${Math.round(chipPadH * 0.8)}px; }
      .chip-label-compact { font-size: ${Math.round(chipLblSize * 0.9)}px; }
      .chip-value-compact { font-size: ${Math.round(chipValSize * 0.9)}px; }
      .hc-row-title { font-size: ${titleSize}px; }
      .hc-total-value { font-size: ${Math.round(totalValSize * 0.65)}px; }
      .hc-total-label { font-size: ${Math.round(totalLblSize * 0.75)}px; }
      .hc-chip { padding: ${chipPadV}px ${chipPadH}px; }
      .hc-chip-label { font-size: ${chipLblSize}px; }
      .hc-chip-value { font-size: ${chipValSize}px; }
    `;
  }

  _getChips() {
    const c = this._config;
    const h = this._hass;
    const all = {
      einsatz: { label: c.label_einsatz, value: getVal(h, c.entity_einsatz), color: c.color_einsatz, show: c.show_einsatz },
      probe: { label: c.label_probe, value: getVal(h, c.entity_probe), color: c.color_probe, show: c.show_probe },
      sonstiges: { label: c.label_sonstiges, value: getVal(h, c.entity_sonstiges), color: c.color_sonstiges, show: c.show_sonstiges },
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
    const layout = this._computeLayout(this._compact, chips.length);

    if (layout.tooSmall) {
      this.shadowRoot.innerHTML = `
        <style>${CARD_STYLES}</style>
        <ha-card><div class="too-small">Karte zu klein</div></ha-card>
      `;
      return;
    }

    const dyn = this._dynStyle(layout);
    let content;

    if (layout.isRow) {
      content = `
        <div class="hc-row">
          ${c.show_header ? `<span class="hc-row-title">${c.title}</span>` : ""}
          ${showProminent ? `
            <div class="hc-total">
              <span class="hc-total-value">${fmt(gesamt)}</span>
              <span class="hc-total-label">${c.label_gesamt}</span>
            </div>
          ` : ""}
          <div class="hc-chips">
            ${chips.map((ch) => `
              <div class="hc-chip" style="
                background: ${hexToRgba(ch.color, 0.12)};
                border-color: ${hexToRgba(ch.color, 0.25)};
              ">
                <span class="hc-chip-label" style="color:${ch.color};">${ch.label}</span>
                <span class="hc-chip-value">${valText(ch.value)}</span>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    } else if (this._compact) {
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
      <style>${CARD_STYLES}${dyn}</style>
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
    this._config.category_order = normalizeCategoryOrder(this._config.category_order);
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
        if (e.unique_id?.endsWith("_sonstiges")) grouped[eid].entity_sonstiges = e.entity_id;
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
          entity_sonstiges: first.entity_sonstiges,
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
      const title = { einsatz: "Einsatz", probe: "Probe", sonstiges: "Sonstiges", gesamt: "Gesamt" }[key];
      // Unknown keys (e.g. legacy "geratehaus" from old stored configs) are skipped
      if (!title) return;

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
