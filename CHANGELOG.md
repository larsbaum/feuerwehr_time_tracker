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
