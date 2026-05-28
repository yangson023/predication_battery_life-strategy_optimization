# Dashboard MVP

This module contains a static MVP for tracking battery research development advice.

## Files

- `index.html`: page structure
- `styles.css`: visual design, responsive layout, current-flow effects, and electron sparkle effects
- `app.js`: seeded advice data, filters, status toggles, and local persistence
- `assets/battery-lab-character.png`: local character image used in the hero panel

## Usage

Open `index.html` directly in a browser:

```powershell
start .\modules\dashboard\index.html
```

The interface stores status changes in browser `localStorage`, so marked items remain
available on the same browser profile after refresh.

## Notes

- Entries are grouped by date.
- Each entry has `P0`, `P1`, or `P2` priority.
- Status can be toggled between `todo` and `done`.
- The operation log input can auto-complete matching todo entries based on keywords.
