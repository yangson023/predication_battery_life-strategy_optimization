# Dashboard MVP

This module contains a static MVP for tracking battery research development advice.

## Files

- `index.html`: page structure
- `styles.css`: visual design, responsive layout, and original energy-lab mascot
- `app.js`: seeded advice data, filters, status toggles, and local persistence

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
