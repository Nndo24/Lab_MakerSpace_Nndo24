"""models.py - domain classes for the Campus MakerSpace Checkout System.

Each class holds its own data and the rules about that data
(validation, availability, overdue checks, etc.).
"""
from datetime import date, datetime, timedelta

DATE_FORMAT = "%Y-%m-%d"
LOAN_DAYS = 7          # default loan length
MAX_ACTIVE_LOANS = 3   # max items one member can borrow at once


def today_str():
    return date.today().strftime(DATE_FORMAT)


class Member:
    """A makerspace member who can borrow equipment."""

    def __init__(self, name, email, phone="", joined_date=None, member_id=None):
        self.member_id = member_id
        self.name = name.strip()
        self.email = email.strip().lower()
        self.phone = phone.strip()
        self.joined_date = joined_date or today_str()

    @classmethod
    def from_row(cls, row):
        """Build a Member from a database row."""
        return cls(row["name"], row["email"], row["phone"] or "",
                   row["joined_date"], row["member_id"])

    def validate(self):
        """Raise ValueError with a clear message if the data is invalid."""
        if len(self.name) < 2:
            raise ValueError("Name must be at least 2 characters long.")
        local, _, domain = self.email.partition("@")
        if not local or "." not in domain or " " in self.email:
            raise ValueError("Please enter a valid email (e.g. name@example.com).")
        if self.phone:
            digits_only = self.phone.replace("+", "").replace("-", "").replace(" ", "")
            if not digits_only.isdigit() or len(digits_only) < 7:
                raise ValueError("Phone must have at least 7 digits (only digits, +, - and spaces).")

    def to_list(self):
        return [self.member_id, self.name, self.email, self.phone or "-", self.joined_date]


class Equipment:
    """An item that can be borrowed."""

    STATUSES = ("available", "borrowed", "maintenance")

    def __init__(self, name, category, status="available", equipment_id=None):
        self.equipment_id = equipment_id
        self.name = name.strip()
        self.category = category.strip().title()
        self.status = status.strip().lower()

    @classmethod
    def from_row(cls, row):
        return cls(row["name"], row["category"], row["status"], row["equipment_id"])

    def validate(self):
        if len(self.name) < 2:
            raise ValueError("Equipment name must be at least 2 characters long.")
        if not self.category:
            raise ValueError("Category cannot be empty.")
        if self.status not in self.STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(self.STATUSES)}.")

    def is_available(self):
        return self.status == "available"

    def mark_borrowed(self):
        if not self.is_available():
            raise ValueError(f"'{self.name}' cannot be borrowed (status: {self.status}).")
        self.status = "borrowed"

    def mark_returned(self):
        self.status = "available"

    def set_status(self, new_status):
        """Manually change status (available <-> maintenance only)."""
        new_status = new_status.strip().lower()
        if new_status not in self.STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(self.STATUSES)}.")
        if self.status == "borrowed":
            raise ValueError("This item is on loan. Return it first before changing its status.")
        if new_status == "borrowed":
            raise ValueError("Use the checkout option to borrow an item.")
        self.status = new_status

    def to_list(self):
        return [self.equipment_id, self.name, self.category, self.status]


class Loan:
    """A record of one member borrowing one piece of equipment."""

    def __init__(self, member_id, equipment_id, loan_date, due_date,
                 return_date=None, loan_id=None):
        self.loan_id = loan_id
        self.member_id = member_id
        self.equipment_id = equipment_id
        self.loan_date = loan_date
        self.due_date = due_date
        self.return_date = return_date

    @classmethod
    def start(cls, member_id, equipment_id, days=LOAN_DAYS):
        """Create a new loan that starts today and is due in `days` days."""
        due = date.today() + timedelta(days=days)
        return cls(member_id, equipment_id, today_str(), due.strftime(DATE_FORMAT))

    @classmethod
    def from_row(cls, row):
        return cls(row["member_id"], row["equipment_id"], row["loan_date"],
                   row["due_date"], row["return_date"], row["loan_id"])

    def is_active(self):
        return self.return_date is None

    def is_overdue(self, today=None):
        today = today or date.today()
        due = datetime.strptime(self.due_date, DATE_FORMAT).date()
        return self.is_active() and due < today

    def days_overdue(self, today=None):
        today = today or date.today()
        if not self.is_overdue(today):
            return 0
        return (today - datetime.strptime(self.due_date, DATE_FORMAT).date()).days

    def close(self):
        """Mark the loan as returned today."""
        if not self.is_active():
            raise ValueError(f"Loan {self.loan_id} was already returned on {self.return_date}.")
        self.return_date = today_str()
