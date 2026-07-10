# 🚒 Feuerwehr Zeit-Tracker

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.x+-blue.svg)](https://www.home-assistant.io/)

**AKTUELL BEFINDET SICH DIE INTEGRATION NOCH IN DER ENTWICKLUNG!**
Ich kann daher nicht garantieren, dass keine Probleme bestehen, die euer System beeinträchtigen. Ich freue mich über jeden Hinweis.

---
Eine Home-Assistant-Integration zum automatischen Tracken von Stunden bei der **Freiwilligen Feuerwehr** – perfekt in zusammenarbeit mit Integrationen wie Divera o.ä.

---

## ✨ Features

### 🚨 Einsatz

Erfasst automatisch alle Stunden rund um einen aktiven Alarm.

- **Auf der Wache bei Alarm:** Solange der Alarm-Sensor (zum Beispiel von der Divera-Intergration) aktiv ist und du dich in der Gerätehaus-Zone befindest, werden die Minuten als Einsatz gezählt.
- **Wache verlassen bei Alarm:** Wenn du die Zone bei aktivem Alarm verlässt (z.B. zum Einsatzort fährst), wird ein Zeitstempel gesetzt. Sobald du zurückkehrst, wird die gesamte Abwesenheitszeit als Einsatz-Minuten addiert.
- **Nicht am Gerätehaus bei Alarm:** Wenn du bei einem aktiven Alarm gar nicht zum Gerätehaus kommst (z.B. daheim bleibst), werden keine Einsatz-Minuten gezählt.

### 🧑‍🚒 Probe / Übung

Erfasst automatisch Übungsstunden – flexibel per festem Wochentag, Kalender oder beidem.

Du kannst zwischen drei Modi wählen:

| Modus | Probe aktiv wenn… |
|-------|-------------------|
| **Tag & Zeit** | Konfigurierter Wochentag + Zeitfenster (klassisch) |
| **Kalender** | Ein Kalender-Ereignis aktiv ist, das ein Schlagwort enthält |
| **Beides** | Tag & Zeit **oder** Kalender – eines von beiden reicht aus |

#### Tag & Zeit (klassisch)

- **Anwesenheit im Gerätehaus:** Innerhalb des Probe-Zählfensters (z.B. 19:00–23:00) werden Minuten in der Zone als Probe gezählt – sofern kein Alarm aktiv ist.
- **Abwesenheit während der Probe:** Verlässt du die Zone innerhalb eines festgelegten Probe-Zeitfensters (z.B. 17:00–23:59) ohne aktiven Alarm, wird die Abwesenheitszeit beim Zurückkommen als Probe-Minuten addiert (z.B. für Übungen außerhalb des Gerätehauses).

#### Kalender

- Statt eines festen Wochentags wird eine **Kalender-Entität** überwacht (z.B. ein Google- oder CalDAV-Kalender).
- Du gibst **Schlagwörter** ein (kommagetrennt, z.B. `Probe,Übung,Training`). Sobald ein Kalender-Ereignis aktiv ist, dessen Titel eines der Schlagwörter enthält, wird Probe-Tracking aktiviert.
- Ohne Schlagwörter zählt **jedes** aktive Ereignis.
- Vorteil: Unregelmäßige oder verschobene Proben werden automatisch erkannt.

#### Beides (Tag & Zeit + Kalender)

- Kombiniert beide Methoden. Die feste Probe am Wochentag wird **immer** getrackt, zusätzlich greifen Kalender-Ereignisse für Sondertermine.

### 🧰 Sonstiges

Erfasst alle sonstigen Stunden, die du im Gerätehaus verbringst (vormals Kategorie „Gerätehaus").

- Jede Minute, die du in der Zone bist und **kein** Alarm aktiv ist und **kein** Probe-Zeitfenster greift, wird als Sonstiges-Stunde gezählt.
- Typische Beispiele: Fahrzeugpflege, Gerätewartung, Kameradschaftsabende außerhalb des Probe-Tags.

#### Sonstige Kalender-Termine außerhalb des Gerätehauses *(optional)*

Nutzt du einen Kalender, in dem **ausschließlich Feuerwehr-Termine** stehen, kannst
du im Kalender-Modus den Schalter **„Sonstige Kalender-Termine als Sonstiges-Zeit
tracken"** aktivieren. Dann wird auch Zeit *außerhalb* des Gerätehauses als
Sonstiges erfasst, wenn der Termin **keine** Übung ist:

- Ein Kalender-Termin ist aktiv, dessen Titel **keines** der Übungs-Schlagwörter
  enthält (z. B. Sitzung, Lehrgang, Dienst außer Haus). Verlässt du dafür das
  Gerätehaus, wird die Abwesenheit beim Zurückkommen als Sonstiges-Minuten addiert
  – dieselbe Logik wie bei Einsatz/Probe.
- **Wichtig:** Ein aktiver Kalender-Termin ist zwingende Voraussetzung. Verlässt du
  die Zone ohne passenden Termin (z. B. zum Einkaufen), wird **nichts** gezählt.
- Die Dauer wird durch den Regler **„Max. Sonstige-Termin-Dauer"** begrenzt (gekappt,
  nicht verworfen). Anders als bei Proben gibt es hier **keinen** Tagesgrenzen-Schutz
  – ein Termin darf über Mitternacht laufen.
- Ist der Schalter aus, bleibt alles wie bisher (nur Übungen werden getrackt).

### 📊 Gesamt

Zeigt die Summe aller drei Kategorien (Einsatz + Probe + Sonstiges) als Gesamtstunden an.

### 🗓️ Automatischer Jahreswechsel

Am 1. Januar werden alle Zähler automatisch auf 0 zurückgesetzt – so zählen die Sensoren immer nur das laufende Jahr.

- Die Vorjahreswerte gehen **nicht** verloren: Sie werden vor dem Reset gespeichert und sind im Sensor-Attribut `previous_years` einsehbar.
- Jeder Kategorie-Sensor trägt seine eigenen Jahreswerte, der Gesamt-Sensor zusätzlich die volle Aufschlüsselung aller Kategorien pro Jahr.
- Es werden keine neuen Entities angelegt – Dashboards und Automationen funktionieren unverändert weiter.

___

### 💡 Vorteile

- Keine manuellen Helfer (`input_number`, `input_datetime`) nötig
- Keine manuellen Automationen nötig
- Vollständig über die HA-Oberfläche konfigurierbar
- Flexible Probe-Erkennung: fester Wochentag, Kalender oder beides
- Optional: Push-Benachrichtigung bei Einsatzende / Probe-Ende
- Services zum Zurücksetzen oder manuellen Korrigieren

### ❗️ Voraussetzungen
- Sensor der einen aktiven Alarm anzeigt (z.B. über Divera-Integration)
- Standorterkennung über Zonen (Gerätehaus-Zone)
- *Für Kalender-Modus:* Eine Kalender-Integration in Home Assistant (z.B. Google Calendar, CalDAV, Local Calendar)

---

## 📦 Installation via HACS

1. HACS in Home Assistant öffnen
2. **Integrationen** → Drei-Punkte-Menü → **Benutzerdefiniertes Repository hinzufügen**
3. URL eingeben: `https://github.com/larsbaum/feuerwehr_time_tracker`
4. Kategorie: **Integration**
5. Auf **Hinzufügen** klicken, dann die Integration installieren
6. Home Assistant neu starten

---

## ⚙️ Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Nach *Feuerwehr Zeit-Tracker* suchen
3. Den Assistenten durchlaufen:

### Schritt 1 – Entities
| Feld | Beispiel |
|------|---------|
| Person | `person.max_mustermann` |
| Zone (Gerätehaus) | `zone.feuerwehrgeratehaus` |
| Aktiver Alarm Sensor | `binary_sensor.aktiver_alarm` |

### Schritt 2 – Probe-Modus wählen

| Modus | Beschreibung |
|-------|-------------|
| Tag & Zeit | Fester Wochentag mit Zeitfenstern (klassisch) |
| Kalender | Kalender-Entität mit Schlagwörtern |
| Beides | Tag & Zeit + Kalender kombiniert |

### Schritt 3a – Tag & Zeit *(nur bei „Tag & Zeit" oder „Beides")*
| Feld | Beschreibung | Standard |
|------|-------------|---------|
| Wochentag | Dienstag | `tue` |
| Zeitfenster Start | Ab wann gilt Abwesenheit als Probe | `17:00` |
| Zeitfenster Ende | Bis wann gilt Abwesenheit als Probe | `23:59` |
| Minuten-Zähler Start | Ab wann werden Minuten im Gerätehaus als Probe gezählt | `19:00` |
| Minuten-Zähler Ende | Bis wann | `23:00` |

### Schritt 3b – Kalender *(nur bei „Kalender" oder „Beides")*
| Feld | Beschreibung | Beispiel / Standard |
|------|-------------|---------|
| Kalender-Entität | Die zu überwachende Kalender-Entität | `calendar.feuerwehr` |
| Schlagwörter | Kommagetrennte Begriffe, die im Event-Titel vorkommen müssen | `Probe,Übung,Training` |
| Sonstige Kalender-Termine als Sonstiges-Zeit tracken | Termine ohne Schlagwort außerhalb des Gerätehauses als Sonstiges erfassen | `aus` |
| Max. Sonstige-Termin-Dauer | Obergrenze der Abwesenheit für sonstige Termine (Stunden) | `6` |

### Schritt 4 – Einsatz & Benachrichtigungen
| Feld | Beschreibung | Standard |
|------|-------------|---------|
| Max. Einsatzdauer | Zeitfenster für gültige Rückkehr (Stunden) | `10` |
| Max. Proben-Dauer | Obergrenze der Abwesenheit während einer Probe (Stunden) | `6` |
| Notify Service | z.B. `notify.mobile_app_iphone` (leer = keine Benachrichtigung) | – |

---

## 📊 Erstellte Entities

Nach der Einrichtung erstellt die Integration automatisch:

| Entity | Beschreibung | Einheit |
|--------|-------------|---------|
| `sensor.alarm_hours` | Gesamt-Einsatzstunden | h |
| `sensor.training_hours` | Gesamt-Probestunden | h |
| `sensor.other_hours` | Sonstige Stunden | h |
| `sensor.total_hours` | Gesamtstunden (Summe aller Kategorien) | h |

Alle Sensoren haben zusätzlich ein `minutes`-Attribut für präzise Auswertungen
sowie ein `previous_years`-Attribut mit den archivierten Werten abgeschlossener
Jahre (siehe [Automatischer Jahreswechsel](#%EF%B8%8F-automatischer-jahreswechsel)).

---

## 🔧 Services

### `feuerwehr_time_tracker.reset`
Setzt eine oder alle Kategorien auf 0 zurück.

```yaml
service: feuerwehr_time_tracker.reset
data:
  category: einsatz   # einsatz | probe | sonstiges | all
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

## 💡 Dashboard-Karte

Die Integration bringt eine eigene Dashboard-Karte mit, die direkt über den visuellen Editor konfiguriert werden kann – kein YAML nötig.

### Karte hinzufügen

1. Dashboard öffnen → **Karte hinzufügen**
2. Nach **„Feuerwehr Zeittracker"** suchen
3. Karte auswählen und über den Editor konfigurieren

### Konfigurierbare Optionen

| Option | Beschreibung |
|--------|-------------|
| Layout | Automatisch (responsive), Groß oder Kompakt |
| Kategorien | Einsatz, Probe, Sonstiges und Gesamt einzeln ein-/ausblenden |
| Bezeichnungen | Eigene Labels pro Kategorie |
| Farben | Individuelle Farbe pro Kategorie |
| Reihenfolge | Kategorien per Pfeil-Buttons umsortieren |
| Gesamt-Anzeige | Prominent (große Zahl), als Kachel oder versteckt |
| Entities | Entities können manuell überschrieben werden |
