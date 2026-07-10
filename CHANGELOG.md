# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/) so weit
sinnvoll für eine HACS-Integration.

> **Hinweis:** Änderungen vor Version 0.2.7 wurden nicht in einem Changelog
> geführt. Die Historie ist über `git log` und die vorhandenen Git-Tags
> (`git tag`) einsehbar, die Commit-Messages sind dort allerdings größtenteils
> unspezifisch ("bugfix").

## [Unreleased]

### Added
- **Sonstige Kalender-Termine als Abwesenheit tracken:** Neuer Toggle
  „Sonstige Kalender-Termine als Sonstiges-Zeit tracken" (nur in den Modi
  „Kalender"/„Beides"). Ist er aktiv, werden **aktive Kalender-Termine, deren
  Titel keines der Übungs-Schlagwörter enthält**, beim Verlassen des Gerätehauses
  als **Sonstiges**-Abwesenheit erfasst (Verlassen startet den Timer, Rückkehr
  addiert die verstrichene Zeit) — ideal für einen Kalender, in dem ausschließlich
  Feuerwehr-Termine stehen (Sitzungen, Lehrgänge, Dienste außer Haus). Ein aktiver
  Kalender-Termin ist zwingender Filter, damit nicht jedes beliebige Verlassen der
  Zone zählt. Ist der Toggle aus, bleibt alles wie bisher.
  - Anders als bei Proben gibt es **keinen** Tagesgrenzen-Schutz: ein sonstiger
    Termin darf über Mitternacht laufen; einziges Limit ist der neue Regler.
- **Zwei getrennte Zeitregler** zur Begrenzung der Abwesenheit:
  - „Max. Proben-Dauer (Stunden)" (Default 6) — begrenzt die Proben-Abwesenheit.
  - „Max. Sonstige-Termin-Dauer (Stunden)" (Default 6) — begrenzt die neue
    Sonstiges-Termin-Abwesenheit.
- Neue Tests: Sonstiges-Termin-Abwesenheit (getrackt/aus, Keyword=Probe,
  Deckelung, Über-Nacht) und Deckelung der Proben-Abwesenheit.

### Changed
- **Proben-Abwesenheit wird jetzt gedeckelt:** Bisher war die beim Verlassen
  während einer Probe gezählte Abwesenheit nur durch die Tagesgrenze begrenzt.
  Neu wird sie zusätzlich auf „Max. Proben-Dauer" gekappt (Standard 6 h;
  **gekappt, nicht verworfen** — im Unterschied zum Einsatz).

### ⚠️ BREAKING CHANGES
- Kategorie „Gerätehaus" wurde vollständig in „Sonstiges" umbenannt:
  - **Entity:** `sensor.station_hours` → `sensor.other_hours` (Name: „Other
    Hours"). Bestehende Installationen werden beim ersten Start automatisch
    migriert (Entity-Registry-Eintrag inkl. `unique_id` wird umgeschrieben,
    Zählerstände bleiben vollständig erhalten – kein Datenverlust).
    **Dashboards und Automationen, die `sensor.station_hours` referenzieren,
    müssen einmalig auf `sensor.other_hours` umgestellt werden.** Die
    HA-Langzeitstatistik läuft unter der neuen Entity-ID neu an; die
    Historie der alten ID bleibt in der Datenbank erhalten.
  - **Service-Kategoriewert:** `category: geratehaus` → `category: sonstiges`
    (betrifft `feuerwehr_time_tracker.reset` und
    `feuerwehr_time_tracker.add_minutes`). **Automationen/Skripte mit
    `category: geratehaus` müssen angepasst werden** (werden sonst mit
    Validierungsfehler abgelehnt).
  - **Dashboard-Karte:** Die Config-Schlüssel `show_geratehaus`,
    `color_geratehaus`, `label_geratehaus`, `entity_geratehaus` sowie der
    Eintrag `geratehaus` in `category_order` heißen jetzt `…sonstiges`.
    **Bestehende Karten-Anpassungen für diese Kategorie müssen einmalig neu
    gesetzt werden.** Die Karte crasht mit alten Configs nicht: unbekannte
    Schlüssel werden ignoriert (Defaults greifen) und die Kategorie-Reihenfolge
    wird automatisch bereinigt/ergänzt.
  - **Storage:** Gespeicherte Zählerstände werden beim ersten Start
    automatisch migriert (`geratehaus_minutes` → `sonstiges_minutes`),
    es gehen keine Daten verloren.

### Added
- **Automatischer Jahreswechsel-Reset:** Am 1. Januar werden die drei
  Stundenzähler (Einsatz/Probe/Sonstiges) automatisch auf 0 zurückgesetzt,
  sodass die Sensoren immer nur das laufende Jahr zählen. Die Vorjahreswerte
  gehen nicht verloren: Sie werden **vor** dem Reset persistent archiviert
  (crash-sicher – das Archiv wird zuerst gespeichert, erst danach werden die
  Zähler genullt) und sind im neuen Sensor-Attribut `previous_years`
  einsehbar (pro Kategorie-Sensor der eigene Jahreswert in Minuten/Stunden,
  am Gesamt-Sensor die volle Aufschlüsselung aller Kategorien). Es werden
  keine neuen Entities angelegt und keine bestehenden Entities umbenannt.
  Funktioniert auch, wenn Home Assistant über den Jahreswechsel offline war
  (Reset wird beim nächsten Start nachgeholt).
- Neue Tests: Storage-Migration, Entity-Registry-Migration (inkl.
  Kollisionsfall bei mehreren Instanzen) und Jahreswechsel-Logik
  (Archivierung, Idempotenz, Offline-Lücke, Save-vor-Reset-Reihenfolge).

## [0.2.7] - 2026-07-10

### Added
- `LICENSE` (MIT).
- `SPEC.md` (lokal, gitignored) mit vollständiger technischer Projektbeschreibung.
- `CHANGELOG.md` (diese Datei).
- Testsuite (`tests/`) auf Basis von `pytest-homeassistant-custom-component`.
- CI-Workflow (`.github/workflows/ci.yml`): hassfest-Validierung, HACS-Validierung
  und Testlauf bei Push/PR.
- `codeowners` in `manifest.json` gesetzt (`@larsbaum`).

### Changed
- `.gitignore` überarbeitet (OS-Dateien, Python-Artefakte, venvs, Editoren, `.env`,
  Test-/Coverage-Ordner, `SPEC.md`).
- Versionierung vereinheitlicht: `manifest.json` (`version`) ist jetzt die
  alleinige Versionsquelle. `const.CARD_VERSION` wird zur Laufzeit daraus
  gelesen statt separat gepflegt zu werden.

### Removed
- Versehentlich getrackte `.DS_Store`-Dateien aus dem Repository entfernt.
