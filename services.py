"""services.py - business operations that connect the model classes to SQLite.

main.py talks to MakerSpaceService; the service uses the models for the rules
and the Database class to run the SQL.
"""
import sqlite3
from datetime import date, timedelta

from models import (DATE_FORMAT, MAX_ACTIVE_LOANS, Equipment, Loan, Member,
                    today_str)


class MakerSpaceService:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # MEMBERS (Create / Read / Update / Delete)
    # ------------------------------------------------------------------
    def add_member(self, name, email, phone=""):
        member = Member(name, email, phone)
        member.validate()
        try:
            cursor = self.db.run(
                "INSERT INTO members (name, email, phone, joined_date) VALUES (?, ?, ?, ?)",
                (member.name, member.email, member.phone, member.joined_date))
        except sqlite3.IntegrityError:
            raise ValueError("A member with that email already exists.")
        member.member_id = cursor.lastrowid
        return member

    def get_member(self, member_id):
        row = self.db.fetch_one("SELECT * FROM members WHERE member_id = ?", (member_id,))
        return Member.from_row(row) if row else None

    def list_members(self):
        rows = self.db.fetch_all("SELECT * FROM members ORDER BY name")
        return [Member.from_row(r) for r in rows]

    def update_member(self, member):
        member.validate()
        try:
            self.db.run("UPDATE members SET name = ?, email = ?, phone = ? WHERE member_id = ?",
                        (member.name, member.email, member.phone, member.member_id))
        except sqlite3.IntegrityError:
            raise ValueError("Another member already uses that email.")

    def delete_member(self, member_id):
        if self.get_member(member_id) is None:
            raise ValueError(f"No member found with ID {member_id}.")
        history = self.db.fetch_one("SELECT COUNT(*) AS n FROM loans WHERE member_id = ?", (member_id,))
        if history["n"] > 0:
            raise ValueError("This member has loan history and cannot be deleted.")
        self.db.run("DELETE FROM members WHERE member_id = ?", (member_id,))

    def search_members(self, term):
        """Search by ID (if term is a number) or by name (partial match)."""
        if term.isdigit():
            rows = self.db.fetch_all("SELECT * FROM members WHERE member_id = ?", (int(term),))
        else:
            rows = self.db.fetch_all("SELECT * FROM members WHERE name LIKE ? ORDER BY name",
                                     (f"%{term}%",))
        return [Member.from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # EQUIPMENT (Create / Read / Update / Delete)
    # ------------------------------------------------------------------
    def add_equipment(self, name, category):
        item = Equipment(name, category)
        item.validate()
        cursor = self.db.run("INSERT INTO equipment (name, category, status) VALUES (?, ?, ?)",
                             (item.name, item.category, item.status))
        item.equipment_id = cursor.lastrowid
        return item

    def get_equipment(self, equipment_id):
        row = self.db.fetch_one("SELECT * FROM equipment WHERE equipment_id = ?", (equipment_id,))
        return Equipment.from_row(row) if row else None

    def list_equipment(self):
        rows = self.db.fetch_all("SELECT * FROM equipment ORDER BY category, name")
        return [Equipment.from_row(r) for r in rows]

    def update_equipment(self, item):
        item.validate()
        self.db.run("UPDATE equipment SET name = ?, category = ?, status = ? WHERE equipment_id = ?",
                    (item.name, item.category, item.status, item.equipment_id))

    def delete_equipment(self, equipment_id):
        if self.get_equipment(equipment_id) is None:
            raise ValueError(f"No equipment found with ID {equipment_id}.")
        history = self.db.fetch_one("SELECT COUNT(*) AS n FROM loans WHERE equipment_id = ?", (equipment_id,))
        if history["n"] > 0:
            raise ValueError("This item has loan history and cannot be deleted. "
                             "Set its status to 'maintenance' instead.")
        self.db.run("DELETE FROM equipment WHERE equipment_id = ?", (equipment_id,))

    def search_equipment(self, term):
        """Search by ID (if term is a number) or by name (partial match)."""
        if term.isdigit():
            rows = self.db.fetch_all("SELECT * FROM equipment WHERE equipment_id = ?", (int(term),))
        else:
            rows = self.db.fetch_all("SELECT * FROM equipment WHERE name LIKE ? ORDER BY name",
                                     (f"%{term}%",))
        return [Equipment.from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # LOANS
    # ------------------------------------------------------------------
    def get_loan(self, loan_id):
        row = self.db.fetch_one("SELECT * FROM loans WHERE loan_id = ?", (loan_id,))
        return Loan.from_row(row) if row else None

    def count_active_loans(self, member_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM loans WHERE member_id = ? AND return_date IS NULL",
            (member_id,))
        return row["n"]

    def checkout(self, member_id, equipment_id):
        """Create a loan after checking every rule. Raises ValueError if invalid."""
        member = self.get_member(member_id)
        if member is None:
            raise ValueError(f"No member found with ID {member_id}.")
        equipment = self.get_equipment(equipment_id)
        if equipment is None:
            raise ValueError(f"No equipment found with ID {equipment_id}.")
        if self.count_active_loans(member_id) >= MAX_ACTIVE_LOANS:
            raise ValueError(f"{member.name} already has {MAX_ACTIVE_LOANS} items on loan (the maximum).")

        equipment.mark_borrowed()   # raises ValueError if not available
        loan = Loan.start(member_id, equipment_id)

        # Both statements succeed together or not at all
        loan.loan_id = self.db.run_transaction([
            ("INSERT INTO loans (member_id, equipment_id, loan_date, due_date) VALUES (?, ?, ?, ?)",
             (loan.member_id, loan.equipment_id, loan.loan_date, loan.due_date)),
            ("UPDATE equipment SET status = ? WHERE equipment_id = ?",
             (equipment.status, equipment.equipment_id)),
        ])
        return loan, member, equipment

    def return_loan(self, loan_id):
        """Close a loan and make the equipment available again."""
        loan = self.get_loan(loan_id)
        if loan is None:
            raise ValueError(f"No loan found with ID {loan_id}.")
        equipment = self.get_equipment(loan.equipment_id)

        was_overdue = loan.is_overdue()
        days_late = loan.days_overdue()
        loan.close()                # raises ValueError if already returned
        equipment.mark_returned()

        self.db.run_transaction([
            ("UPDATE loans SET return_date = ? WHERE loan_id = ?", (loan.return_date, loan.loan_id)),
            ("UPDATE equipment SET status = ? WHERE equipment_id = ?",
             (equipment.status, equipment.equipment_id)),
        ])
        return loan, equipment, was_overdue, days_late

    # ------------------------------------------------------------------
    # REPORTS (SQL queries with JOINs / GROUP BY)
    # ------------------------------------------------------------------
    def report_current_loans(self):
        """Report 1: every item that is currently borrowed."""
        return self.db.fetch_all("""
            SELECT l.loan_id, m.name AS member, e.name AS equipment,
                   l.loan_date, l.due_date
            FROM loans l
            JOIN members m   ON m.member_id = l.member_id
            JOIN equipment e ON e.equipment_id = l.equipment_id
            WHERE l.return_date IS NULL
            ORDER BY l.due_date
        """)

    def report_overdue_loans(self):
        """Report 2: loans not returned and past their due date."""
        return self.db.fetch_all("""
            SELECT l.loan_id, m.name AS member, m.email, e.name AS equipment,
                   l.due_date,
                   CAST(julianday(?) - julianday(l.due_date) AS INTEGER) AS days_overdue
            FROM loans l
            JOIN members m   ON m.member_id = l.member_id
            JOIN equipment e ON e.equipment_id = l.equipment_id
            WHERE l.return_date IS NULL AND l.due_date < ?
            ORDER BY days_overdue DESC
        """, (today_str(), today_str()))

    def report_equipment_by_category(self):
        """Report 3: how many items per category and their status counts."""
        return self.db.fetch_all("""
            SELECT category,
                   COUNT(*) AS total,
                   SUM(status = 'available')   AS available,
                   SUM(status = 'borrowed')    AS borrowed,
                   SUM(status = 'maintenance') AS maintenance
            FROM equipment
            GROUP BY category
            ORDER BY category
        """)

    def report_member_history(self, member_id):
        """Report 4: every loan a member has ever made."""
        return self.db.fetch_all("""
            SELECT l.loan_id, e.name AS equipment, l.loan_date, l.due_date,
                   COALESCE(l.return_date, '-') AS returned,
                   CASE WHEN l.return_date IS NULL THEN 'On loan' ELSE 'Returned' END AS state
            FROM loans l
            JOIN equipment e ON e.equipment_id = l.equipment_id
            WHERE l.member_id = ?
            ORDER BY l.loan_date DESC, l.loan_id DESC
        """, (member_id,))

    # ------------------------------------------------------------------
    # SAMPLE DATA
    # ------------------------------------------------------------------
    def load_sample_data(self):
        """Insert demo data (only if the database is empty)."""
        if self.db.fetch_one("SELECT COUNT(*) AS n FROM members")["n"] > 0 or \
           self.db.fetch_one("SELECT COUNT(*) AS n FROM equipment")["n"] > 0:
            raise ValueError("Sample data can only be loaded into an empty database.")

        for name, email, phone in [
            ("Amina Okafor", "amina@example.com", "+250788111222"),
            ("Brian Mensah", "brian@example.com", "0788333444"),
            ("Chloe Dubois", "chloe@example.com", ""),
            ("David Ncube", "david@example.com", "0788555666"),
        ]:
            self.add_member(name, email, phone)

        for name, category in [
            ("Soldering Kit", "Electronics"), ("Arduino Starter Kit", "Electronics"),
            ("Raspberry Pi 4 Kit", "Electronics"), ("Canon DSLR Camera", "Cameras"),
            ("GoPro Hero", "Cameras"), ("Dell Laptop", "Laptops"),
            ("3D Printer Nozzle Set", "3D Printing"), ("PLA Filament Bundle", "3D Printing"),
        ]:
            self.add_equipment(name, category)

        # A few loans with fixed dates so every report has something to show
        today = date.today()
        fmt = lambda days: (today + timedelta(days=days)).strftime(DATE_FORMAT)
        self.db.run_transaction([   # overdue loan: Amina has the Dell Laptop
            ("INSERT INTO loans (member_id, equipment_id, loan_date, due_date) VALUES (1, 6, ?, ?)",
             (fmt(-10), fmt(-3))),
            ("UPDATE equipment SET status = 'borrowed' WHERE equipment_id = 6", ()),
        ])
        self.db.run_transaction([   # active loan, not overdue
            ("INSERT INTO loans (member_id, equipment_id, loan_date, due_date) VALUES (2, 4, ?, ?)",
             (fmt(-2), fmt(5))),
            ("UPDATE equipment SET status = 'borrowed' WHERE equipment_id = 4", ()),
        ])
        self.db.run(   # returned loan (history)
            "INSERT INTO loans (member_id, equipment_id, loan_date, due_date, return_date) "
            "VALUES (3, 1, ?, ?, ?)", (fmt(-14), fmt(-7), fmt(-8)))
        self.db.run("UPDATE equipment SET status = 'maintenance' WHERE equipment_id = 7")
