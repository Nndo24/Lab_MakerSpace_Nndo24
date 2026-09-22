# Campus MakerSpace Checkout System

**Module:** Introduction to Programming and Databases – BSc (Hons) Software Engineering
**Author:** YOUR NAME (GitHub: YOURUSERNAME)

A menu-driven Python command-line application for a student makerspace. Operators can register members and
equipment, check equipment out and back in, search records and view reports. All data is stored in a
SQLite database (`makerspace.db`) so it persists between runs.

## How to run

Requires Python 3.8+ (no extra packages – `sqlite3` is part of the standard library).

```bash
python main.py
```

The database file `makerspace.db` is created automatically on first run.
To try the app quickly, choose **6. Load sample data** from the main menu (works only on an empty database).

## Features

| Menu | What it does |
|------|--------------|
| Members | Register, list, update, delete (blocked if the member has loan history) |
| Equipment | Register, list, update / change status (available ↔ maintenance), delete (blocked if it has loan history) |
| Loans | Check out (validated), return, view current loans |
| Search | Find members or equipment by name (partial match) or by ID |
| Reports | Currently borrowed items, overdue loans, equipment by category, member loan history |

**Validation and rules:** the member and equipment must exist; equipment must be available; a member can
have at most 3 items on loan; loans are due after 7 days; duplicate emails are rejected; invalid or empty
input shows a clear message instead of crashing.

## Project structure

```
main.py        Menu loop, user input helpers and the MakerSpaceApp class
models.py      Domain classes: Member, Equipment, Loan
services.py    MakerSpaceService – business logic and all SQL queries/reports
database.py    Database class – SQLite connection, schema creation, SQL helpers
```

## Class design

- **Member** – `name`, `email`, `phone`, `joined_date`. Methods: `validate()`, `from_row()`, `to_list()`.
- **Equipment** – `name`, `category`, `status`. Methods: `is_available()`, `mark_borrowed()`,
  `mark_returned()`, `set_status()`, `validate()`.
- **Loan** – `member_id`, `equipment_id`, `loan_date`, `due_date`, `return_date`. Methods: `start()`,
  `is_active()`, `is_overdue()`, `days_overdue()`, `close()`.
- **Database** – opens the connection, creates the tables, runs SQL (`run`, `run_transaction`, `fetch_all`, `fetch_one`).
- **MakerSpaceService** – coordinates the objects and the database (e.g. `checkout()` checks the member and
  equipment, calls `equipment.mark_borrowed()`, creates a `Loan` and saves both changes in one transaction).
- **MakerSpaceApp** – the user interface; it only talks to the service.

## Database design (SQLite)

```
members   (member_id PK, name, email UNIQUE, phone, joined_date)
equipment (equipment_id PK, name, category, status CHECK in available/borrowed/maintenance)
loans     (loan_id PK, member_id FK -> members, equipment_id FK -> equipment,
           loan_date, due_date, return_date NULL = still on loan)
```

Loans link members and equipment through foreign keys, so member and equipment details are never
duplicated in the loans table.

## SQL reports

1. **Currently borrowed items** – `loans JOIN members JOIN equipment WHERE return_date IS NULL`
2. **Overdue loans** – same joins, `WHERE return_date IS NULL AND due_date < today`
3. **Equipment by category** – `GROUP BY category` with `COUNT` / `SUM` of each status
4. **Member loan history** – all loans for one member, newest first

## Generative AI disclosure

I used **[TOOL NAME, e.g. Claude]** to help [describe what it helped with – e.g. plan the class/table design,
write the first version of the code, and debug]. I reviewed, tested and can explain all of the code.
[Edit this section so it honestly reflects how you used AI.]

## References

- Python Software Foundation. (n.d.). *sqlite3 – DB-API 2.0 interface for SQLite databases*. https://docs.python.org/3/library/sqlite3.html
