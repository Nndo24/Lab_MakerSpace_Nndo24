"""main.py - menu loop and entry point for the Campus MakerSpace Checkout System.

Run with:  python main.py
"""
import sqlite3

from database import Database
from services import MakerSpaceService


# ----------------------------------------------------------------------
# Small input / output helpers
# ----------------------------------------------------------------------
def ask_text(prompt, required=True, keep=None):
    """Ask for text. If `keep` is given, pressing Enter keeps that value."""
    while True:
        value = input(prompt).strip()
        if value == "" and keep is not None:
            return keep
        if value == "" and required:
            print("  ! This field cannot be empty.")
            continue
        return value


def ask_id(prompt):
    """Ask for an ID. Returns an int, or raises ValueError with a clear message."""
    raw = input(prompt).strip()
    if not raw.isdigit():
        raise ValueError("ID must be a positive whole number.")
    return int(raw)


def print_table(headers, rows):
    """Print rows (lists/tuples) as a simple aligned table."""
    if not rows:
        print("  (no records found)")
        return
    rows = [[str(v) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    line = "  ".join("-" * w for w in widths)
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + line)
    for row in rows:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(row, widths)))


def run_menu(title, options, back_label="Back"):
    """Show a menu and run the chosen action until the user goes back.

    options is a dict like {"1": ("Label", function)}.
    Any ValueError / database error raised by an action is shown as a
    friendly message instead of crashing the program.
    """
    while True:
        print(f"\n=== {title} ===")
        for key, (label, _) in options.items():
            print(f"  {key}. {label}")
        print(f"  0. {back_label}")
        choice = input("Choose an option: ").strip()

        if choice == "0":
            return
        if choice not in options:
            print("  ! Invalid choice. Please pick a number from the menu.")
            continue
        try:
            options[choice][1]()
        except ValueError as error:
            print(f"  ! {error}")
        except sqlite3.Error as error:
            print(f"  ! Database error: {error}")


# ----------------------------------------------------------------------
# The application
# ----------------------------------------------------------------------
class MakerSpaceApp:
    MEMBER_HEADERS = ["ID", "Name", "Email", "Phone", "Joined"]
    EQUIPMENT_HEADERS = ["ID", "Name", "Category", "Status"]

    def __init__(self, service):
        self.service = service

    # ---------------- Members ----------------
    def add_member(self):
        name = ask_text("Full name: ")
        email = ask_text("Email: ")
        phone = ask_text("Phone (optional): ", required=False)
        member = self.service.add_member(name, email, phone)
        print(f"  Member registered with ID {member.member_id}.")

    def list_members(self):
        members = self.service.list_members()
        print_table(self.MEMBER_HEADERS, [m.to_list() for m in members])

    def update_member(self):
        member = self.service.get_member(ask_id("Member ID to update: "))
        if member is None:
            raise ValueError("No member found with that ID.")
        print(f"  Editing {member.name} (press Enter to keep the current value)")
        member.name = ask_text(f"Name [{member.name}]: ", keep=member.name)
        member.email = ask_text(f"Email [{member.email}]: ", keep=member.email).lower()
        member.phone = ask_text(f"Phone [{member.phone or '-'}]: ", required=False, keep=member.phone)
        self.service.update_member(member)
        print("  Member updated.")

    def delete_member(self):
        self.service.delete_member(ask_id("Member ID to delete: "))
        print("  Member deleted.")

    def members_menu(self):
        run_menu("MEMBERS", {
            "1": ("Register member", self.add_member),
            "2": ("List members", self.list_members),
            "3": ("Update member", self.update_member),
            "4": ("Delete member", self.delete_member),
        })

    # ---------------- Equipment ----------------
    def add_equipment(self):
        name = ask_text("Equipment name: ")
        category = ask_text("Category (e.g. Electronics, Cameras): ")
        item = self.service.add_equipment(name, category)
        print(f"  Equipment registered with ID {item.equipment_id}.")

    def list_equipment(self):
        items = self.service.list_equipment()
        print_table(self.EQUIPMENT_HEADERS, [i.to_list() for i in items])

    def update_equipment(self):
        item = self.service.get_equipment(ask_id("Equipment ID to update: "))
        if item is None:
            raise ValueError("No equipment found with that ID.")
        print(f"  Editing {item.name} (press Enter to keep the current value)")
        item.name = ask_text(f"Name [{item.name}]: ", keep=item.name)
        item.category = ask_text(f"Category [{item.category}]: ", keep=item.category).title()
        new_status = ask_text(f"Status [{item.status}] (available/maintenance): ", keep=item.status)
        if new_status.lower() != item.status:
            item.set_status(new_status)   # model enforces the status rules
        self.service.update_equipment(item)
        print("  Equipment updated.")

    def delete_equipment(self):
        self.service.delete_equipment(ask_id("Equipment ID to delete: "))
        print("  Equipment deleted.")

    def equipment_menu(self):
        run_menu("EQUIPMENT", {
            "1": ("Register equipment", self.add_equipment),
            "2": ("List equipment", self.list_equipment),
            "3": ("Update equipment / change status", self.update_equipment),
            "4": ("Delete equipment", self.delete_equipment),
        })

    # ---------------- Loans ----------------
    def checkout(self):
        member_id = ask_id("Member ID: ")
        equipment_id = ask_id("Equipment ID: ")
        loan, member, item = self.service.checkout(member_id, equipment_id)
        print(f"  Loan {loan.loan_id} created: {member.name} borrowed '{item.name}'. "
              f"Due back on {loan.due_date}.")

    def return_item(self):
        print("  Items currently on loan:")
        self.show_current_loans()
        loan, item, was_overdue, days_late = self.service.return_loan(ask_id("Loan ID to return: "))
        print(f"  '{item.name}' returned and is available again.")
        if was_overdue:
            print(f"  Note: this item was {days_late} day(s) overdue.")

    def loans_menu(self):
        run_menu("LOANS", {
            "1": ("Check out equipment", self.checkout),
            "2": ("Return equipment", self.return_item),
            "3": ("View current loans", self.show_current_loans),
        })

    # ---------------- Search ----------------
    def search_members(self):
        term = ask_text("Enter member name or ID: ")
        results = self.service.search_members(term)
        print_table(self.MEMBER_HEADERS, [m.to_list() for m in results])

    def search_equipment(self):
        term = ask_text("Enter equipment name or ID: ")
        results = self.service.search_equipment(term)
        print_table(self.EQUIPMENT_HEADERS, [i.to_list() for i in results])

    def search_menu(self):
        run_menu("SEARCH", {
            "1": ("Search members", self.search_members),
            "2": ("Search equipment", self.search_equipment),
        })

    # ---------------- Reports ----------------
    def show_current_loans(self):
        rows = self.service.report_current_loans()
        print_table(["Loan", "Member", "Equipment", "Borrowed", "Due"], [tuple(r) for r in rows])

    def show_overdue_loans(self):
        rows = self.service.report_overdue_loans()
        print_table(["Loan", "Member", "Email", "Equipment", "Was due", "Days late"],
                    [tuple(r) for r in rows])

    def show_equipment_by_category(self):
        rows = self.service.report_equipment_by_category()
        print_table(["Category", "Total", "Available", "Borrowed", "Maintenance"],
                    [tuple(r) for r in rows])

    def show_member_history(self):
        member = self.service.get_member(ask_id("Member ID: "))
        if member is None:
            raise ValueError("No member found with that ID.")
        print(f"  Loan history for {member.name}:")
        rows = self.service.report_member_history(member.member_id)
        print_table(["Loan", "Equipment", "Borrowed", "Due", "Returned", "Status"],
                    [tuple(r) for r in rows])

    def reports_menu(self):
        run_menu("REPORTS", {
            "1": ("Currently borrowed items", self.show_current_loans),
            "2": ("Overdue loans", self.show_overdue_loans),
            "3": ("Equipment by category", self.show_equipment_by_category),
            "4": ("Member loan history", self.show_member_history),
        })

    # ---------------- Sample data ----------------
    def load_sample_data(self):
        self.service.load_sample_data()
        print("  Sample data loaded (4 members, 8 items, 3 loans).")

    # ---------------- Main menu ----------------
    def run(self):
        print("Welcome to the Campus MakerSpace Checkout System")
        run_menu("MAIN MENU", {
            "1": ("Members", self.members_menu),
            "2": ("Equipment", self.equipment_menu),
            "3": ("Loans (checkout / return)", self.loans_menu),
            "4": ("Search", self.search_menu),
            "5": ("Reports", self.reports_menu),
            "6": ("Load sample data (empty database only)", self.load_sample_data),
        }, back_label="Exit")
        print("Goodbye!")


def main():
    db = Database("makerspace.db")
    try:
        MakerSpaceApp(MakerSpaceService(db)).run()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
