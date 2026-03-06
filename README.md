# 🚒 Feuerwehr Zeit-Tracker

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.x+-blue.svg)](https://www.home-assistant.io/)

AKTUELL BEFINDET SICH DIE INTEGRATION NOCH IN DER ENTWICKLUNG!
Ich kann daher nicht garantieren, dass keine Probleme bestehen, die euer System beeinträchtigen. Ich freue mich über jeden Hinweis.


Eine Home-Assistant-Integration zum automatischen Tracken von Stunden bei der **Freiwilligen Feuerwehr** – ohne manuelle Helfer oder Automationen.

---

## ✨ Features

| Kategorie | Tracking-Methode |
|-----------|-----------------|
| 🚨 **Einsatz** | Alarm aktiv + in der Zone → Einsatz-Minuten. Zone verlassen bei aktivem Alarm → Zeit beim Zurückkommen addieren |
| 🧑‍🚒 **Probe / Übung** | Wöchentlicher Tag + Zeitfenster (außerhalb und innerhalb der Zone) |
| 🏠 **Gerätehaus** | Minuten-Zähler bei Anwesenheit (alle anderen Zeiten, kein aktiver Alarm) |
| 📊 **Gesamt** | Summe aus Einsatz + Probe + Gerätehaus |

- Keine manuellen Helfer (`input_number`, `input_datetime`) nötig
- Keine manuellen Automationen nötig
- Vollständig über die HA-Oberfläche konfigurierbar
- Persistente Speicherung (übersteht HA-Neustarts)
- Optional: Push-Benachrichtigung bei Einsatzende / Probe-Ende
- Services zum Zurücksetzen oder manuellen Korrigieren

---

## 📦 Installation via HACS

1. HACS in Home Assistant öffnen
2. **Integrationen** → Drei-Punkte-Menü → **Benutzerdefiniertes Repository hinzufügen**
3. URL eingeben: `https://github.com/your-username/feuerwehr_time_tracker`
4. Kategorie: **Integration**
5. Auf **Hinzufügen** klicken, dann die Integration installieren
6. Home Assistant neu starten

---

## ⚙️ Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Nach *Feuerwehr Zeit-Tracker* suchen
3. Den 3-Schritt-Assistenten durchlaufen:

### Schritt 1 – Entities
| Feld | Beispiel |
|------|---------|
| Person | `person.max_mustermann` |
| Zone (Gerätehaus) | `zone.feuerwehrgeratehaus` |
| Aktiver Alarm Sensor | `binary_sensor.aktiver_alarm` |

### Schritt 2 – Probe / Übung
| Feld | Beschreibung | Standard |
|------|-------------|---------|
| Wochentag | Dienstag | `tue` |
| Zeitfenster Start | Ab wann gilt Abwesenheit als Probe | `17:00` |
| Zeitfenster Ende | Bis wann gilt Abwesenheit als Probe | `23:59` |
| Minuten-Zähler Start | Ab wann werden Minuten im Gerätehaus als Probe gezählt | `19:00` |
| Minuten-Zähler Ende | Bis wann | `23:00` |

### Schritt 3 – Einsatz & Benachrichtigungen
| Feld | Beschreibung | Standard |
|------|-------------|---------|
| Max. Einsatzdauer | Zeitfenster für gültige Rückkehr (Stunden) | `10` |
| Notify Service | z.B. `notify.mobile_app_iphone` (leer = keine Benachrichtigung) | – |

---

## 📊 Erstellte Entities

Nach der Einrichtung erstellt die Integration automatisch:

| Entity | Beschreibung | Einheit |
|--------|-------------|---------|
| `sensor.alarm_hours` | Gesamt-Einsatzstunden | h |
| `sensor.training_hours` | Gesamt-Probestunden | h |
| `sensor.station_hours` | Sonstige Gerätehaus-Stunden | h |
| `sensor.total_hours` | Gesamtstunden (Summe aller Kategorien) | h |

Alle Sensoren haben zusätzlich ein `minutes`-Attribut für präzise Auswertungen.

---

## 🔧 Services

### `feuerwehr_time_tracker.reset`
Setzt eine oder alle Kategorien auf 0 zurück.

```yaml
service: feuerwehr_time_tracker.reset
data:
  category: einsatz   # einsatz | probe | geratehaus | all
```

### `feuerwehr_time_tracker.add_minutes`
Fügt Minuten manuell hinzu oder zieht sie ab (z.B. zur Korrektur).

```yaml
service: feuerwehr_time_tracker.add_minutes
data:
  category: probe
  minutes: 60    # negativ zum Abziehen
```

---

## 💡 Beispiel: Dashboard-Karte

```yaml
type: entities
title: Feuerwehr Stunden
entities:
  - entity: sensor.alarm_hours
    name: 🚨 Einsatz
  - entity: sensor.training_hours
    name: 🧑‍🚒 Probe
  - entity: sensor.station_hours
    name: 🏠 Gerätehaus
  - entity: sensor.total_hours
    name: 📊 Gesamt
```

