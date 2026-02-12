# Client Gifting Assistant

A working web app for relationship-driven professionals (lawyers, accountants, bankers, etc.) to automate client gifting workflows.

## Features

- Professional profile setup with payment metadata (`card_token`, `card_last4`)
- Client management with birthday, shipping address, budget, and preference tags
- Custom occasion tracking
- Gift recommendations (up to 10 options), budget-aware and preference-scored
- Order confirmation with budget enforcement
- Dashboard metrics (clients, orders, total budget, total order value, upcoming occasions)

## Tech Stack

- Backend: Python WSGI + SQLite (`sqlite3`)
- Frontend: Vanilla HTML/CSS/JS
- Tests: Python `unittest`

## Run

```bash
python -m app.main
```

Open: `http://localhost:8000`

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
