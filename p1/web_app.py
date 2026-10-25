"""HTTP server and SQLite API for the library catalog web application."""

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATABASE_PATH = BASE_DIR / "library.db"
HOST = "127.0.0.1"
PORT = 8000
LOAN_PERIOD_DAYS = 14
LATE_FEE_PER_DAY = 2
PAYMENT_METHODS = ("Cash", "UPI", "Card")

SAMPLE_BOOKS = (
    ("Harry Potter", "J.K. Rowling", "Fiction", "Fantasy"),
    ("The Alchemist", "Paulo Coelho", "Fiction", "Novel"),
    ("Wings of Fire", "A.P.J. Abdul Kalam", "Non-Fiction", "Autobiography"),
    ("Sapiens", "Yuval Noah Harari", "Non-Fiction", "History"),
    ("Oxford English Dictionary", "Oxford Press", "Reference", "3rd"),
)


@contextmanager
def connect_database():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with connect_database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL COLLATE NOCASE UNIQUE,
                author TEXT NOT NULL,
                book_type TEXT NOT NULL CHECK (
                    book_type IN ('Fiction', 'Non-Fiction', 'Reference')
                ),
                detail TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
                total_copies INTEGER NOT NULL DEFAULT 1 CHECK (total_copies >= 0),
                available_copies INTEGER NOT NULL DEFAULT 1
                    CHECK (available_copies >= 0)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
                book_title TEXT NOT NULL,
                borrower_name TEXT NOT NULL,
                borrower_phone TEXT NOT NULL DEFAULT '',
                borrower_id TEXT NOT NULL DEFAULT '',
                borrowed_on TEXT NOT NULL,
                due_on TEXT NOT NULL,
                returned_on TEXT,
                days_borrowed INTEGER,
                fine_amount INTEGER NOT NULL DEFAULT 0,
                fine_paid INTEGER NOT NULL DEFAULT 0,
                payment_method TEXT,
                paid_on TEXT,
                CHECK (fine_amount >= 0),
                CHECK (fine_paid IN (0, 1)),
                CHECK (days_borrowed IS NULL OR days_borrowed >= 1)
            )
            """
        )
        book_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(books)").fetchall()
        }
        has_total_copies = "total_copies" in book_columns
        has_available_copies = "available_copies" in book_columns
        if not has_total_copies:
            connection.execute(
                "ALTER TABLE books ADD COLUMN total_copies INTEGER NOT NULL DEFAULT 1"
            )
        if not has_available_copies:
            connection.execute(
                "ALTER TABLE books ADD COLUMN available_copies INTEGER NOT NULL DEFAULT 1"
            )

        loan_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(loans)").fetchall()
        }
        if "borrower_phone" not in loan_columns:
            connection.execute(
                "ALTER TABLE loans ADD COLUMN borrower_phone TEXT NOT NULL DEFAULT ''"
            )
        if "borrower_id" not in loan_columns:
            connection.execute(
                "ALTER TABLE loans ADD COLUMN borrower_id TEXT NOT NULL DEFAULT ''"
            )

        if not has_total_copies or not has_available_copies:
            connection.execute(
                """
                UPDATE books
                SET total_copies = MAX(
                        1,
                        available + (
                            SELECT COUNT(*) FROM loans
                            WHERE loans.book_id = books.id
                              AND loans.returned_on IS NULL
                        )
                    ),
                    available_copies = MAX(0, available)
                """
            )
        connection.execute(
            "UPDATE books SET available = CASE WHEN available_copies > 0 THEN 1 ELSE 0 END"
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO books (
                title, author, book_type, detail, total_copies, available_copies
            ) VALUES (?, ?, ?, ?, 1, 1)
            """,
            SAMPLE_BOOKS,
        )
        connection.execute("DROP INDEX IF EXISTS one_active_loan_per_book")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS active_loans_by_book
            ON loans(book_id, returned_on)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_loan_per_book
            ON loans(book_id) WHERE returned_on IS NULL AND book_id IS NOT NULL
            """
        )


class LibraryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed_url = urlsplit(self.path)
        if parsed_url.path == "/api/books":
            self.handle_list_books(parse_qs(parsed_url.query))
        elif parsed_url.path == "/api/loans":
            self.handle_list_loans(parse_qs(parsed_url.query))
        elif parsed_url.path.startswith("/api/"):
            self.send_json({"error": "API endpoint not found."}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/books":
            self.handle_add_book()
            return

        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[0:2] == ["api", "books"]:
            book_id = self.parse_book_id(parts[2])
            if book_id is None:
                return
            action = parts[3]
            if action == "borrow":
                self.handle_book_action(book_id, borrow=True)
            elif action == "return":
                self.handle_book_action(book_id, borrow=False)
            elif action == "stock":
                self.handle_restock_book(book_id)
            else:
                self.send_json({"error": "API endpoint not found."}, 404)
            return

        if len(parts) == 4 and parts[0:2] == ["api", "loans"]:
            loan_id = self.parse_book_id(parts[2])
            if loan_id is None:
                return
            if parts[3] == "pay":
                self.handle_record_payment(loan_id)
            elif parts[3] == "return":
                self.handle_return_loan(loan_id)
            else:
                self.send_json({"error": "API endpoint not found."}, 404)
            return

        self.send_json({"error": "API endpoint not found."}, 404)

    def do_DELETE(self):
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) != 3 or parts[0:2] != ["api", "books"]:
            self.send_json({"error": "API endpoint not found."}, 404)
            return

        book_id = self.parse_book_id(parts[2])
        if book_id is None:
            return

        with connect_database() as connection:
            active_loan = connection.execute(
                "SELECT 1 FROM loans WHERE book_id = ? AND returned_on IS NULL",
                (book_id,),
            ).fetchone()
            if active_loan is not None:
                self.send_json(
                    {"error": "Return this book before removing it from the catalog."},
                    409,
                )
                return
            cursor = connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
        if cursor.rowcount == 0:
            self.send_json({"error": "Book not found."}, 404)
            return
        self.send_json({"message": "Book removed from the catalog."})

    def handle_list_books(self, query_parameters):
        search = query_parameters.get("q", [""])[0].strip()
        availability = query_parameters.get("availability", ["all"])[0]
        conditions = []
        values = []

        if search:
            conditions.append("(books.title LIKE ? OR books.author LIKE ?)")
            search_term = f"%{search}%"
            values.extend((search_term, search_term))
        if availability == "available":
            conditions.append("books.available_copies > 0")
        elif availability == "borrowed":
            conditions.append("books.available_copies < books.total_copies")
        elif availability == "out":
            conditions.append("books.available_copies = 0")
        elif availability != "all":
            self.send_json({"error": "Invalid availability filter."}, 400)
            return

        sql = """
            SELECT books.*,
                   books.available_copies > 0 AS available,
                   books.total_copies - books.available_copies AS checked_out
            FROM books
        """
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY books.title COLLATE NOCASE"

        with connect_database() as connection:
            books = connection.execute(sql, values).fetchall()
        self.send_json({"books": [dict(book) for book in books]})

    def handle_add_book(self):
        data = self.read_json_body()
        if data is None:
            return

        title = self.string_field(data, "title")
        author = self.string_field(data, "author")
        book_type = self.string_field(data, "book_type")
        detail = self.string_field(data, "detail")
        total_copies = self.positive_int_field(data, "total_copies", default=1)
        if not title or not author:
            self.send_json({"error": "Title and author cannot be empty."}, 400)
            return
        if len(title) > 200 or len(author) > 200 or len(detail) > 100:
            self.send_json({"error": "Book details exceed the allowed length."}, 400)
            return
        if book_type not in ("Fiction", "Non-Fiction", "Reference"):
            self.send_json({"error": "Choose a valid book type."}, 400)
            return
        if total_copies is None or total_copies > 5000:
            self.send_json({"error": "Enter a copy count between 1 and 5000."}, 400)
            return
        if not detail:
            detail = {"Fiction": "Novel", "Non-Fiction": "General", "Reference": "1st"}[
                book_type
            ]

        try:
            with connect_database() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO books (
                        title, author, book_type, detail, total_copies, available_copies
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (title, author, book_type, detail, total_copies, total_copies),
                )
                book = connection.execute(
                    "SELECT * FROM books WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        except sqlite3.IntegrityError:
            self.send_json({"error": "This title is already in the catalog."}, 409)
            return

        self.send_json({"book": dict(book)}, 201)

    def handle_book_action(self, book_id, borrow):
        if not borrow:
            with connect_database() as connection:
                loan = connection.execute(
                    """
                    SELECT id FROM loans
                    WHERE book_id = ? AND returned_on IS NULL
                    ORDER BY borrowed_on, id LIMIT 1
                    """,
                    (book_id,),
                ).fetchone()
            if loan is None:
                self.send_json({"error": "No active checkout exists for this book."}, 409)
                return
            self.handle_return_loan(loan["id"])
            return

        data = self.read_json_body()
        if data is None:
            return
        borrower_name = self.string_field(data, "borrower_name")
        borrower_phone = self.string_field(data, "borrower_phone")
        borrower_id = self.string_field(data, "borrower_id")
        loan_days = self.positive_int_field(data, "loan_days")
        phone_digits = re.sub(r"\D", "", borrower_phone)
        if not borrower_name or len(borrower_name) > 120:
            self.send_json(
                {"error": "Enter a borrower name (up to 120 characters)."}, 400
            )
            return
        if not borrower_phone or not 7 <= len(phone_digits) <= 15:
            self.send_json(
                {"error": "Enter a valid phone number with 7 to 15 digits."}, 400
            )
            return
        if not borrower_id or len(borrower_id) > 60:
            self.send_json(
                {"error": "Enter a library member/customer ID (up to 60 characters)."},
                400,
            )
            return
        if loan_days is None or loan_days > 60:
            self.send_json({"error": "Loan period must be between 1 and 60 days."}, 400)
            return

        today = date.today()
        due_on = today + timedelta(days=loan_days)
        with connect_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            book = connection.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if book is None:
                self.send_json({"error": "Book not found."}, 404)
                return
            if book["book_type"] == "Reference":
                self.send_json({"error": "Reference books cannot be borrowed."}, 400)
                return
            if book["available_copies"] < 1:
                self.send_json(
                    {"error": "No copies are currently available in inventory."}, 409
                )
                return

            connection.execute(
                """
                INSERT INTO loans (
                    book_id, book_title, borrower_name, borrower_phone, borrower_id,
                    borrowed_on, due_on
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    book["title"],
                    borrower_name,
                    borrower_phone,
                    borrower_id,
                    today.isoformat(),
                    due_on.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE books
                SET available_copies = available_copies - 1,
                    available = CASE WHEN available_copies > 1 THEN 1 ELSE 0 END
                WHERE id = ?
                """,
                (book_id,),
            )
            updated_book = connection.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            loan_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]

        self.send_json(
            {
                "book": dict(updated_book),
                "loan_id": loan_id,
                "message": (
                    f"{book['title']} checked out to {borrower_name}. "
                    f"{updated_book['available_copies']} copy/copies remain. "
                    f"Due {due_on.isoformat()}."
                ),
            }
        )

    def handle_restock_book(self, book_id):
        data = self.read_json_body()
        if data is None:
            return
        copies = self.positive_int_field(data, "copies")
        if copies is None or copies > 5000:
            self.send_json({"error": "Enter a copy count between 1 and 5000."}, 400)
            return
        with connect_database() as connection:
            cursor = connection.execute(
                """
                UPDATE books
                SET total_copies = total_copies + ?,
                    available_copies = available_copies + ?,
                    available = 1
                WHERE id = ?
                """,
                (copies, copies, book_id),
            )
            if cursor.rowcount == 0:
                self.send_json({"error": "Book not found."}, 404)
                return
            book = connection.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
        self.send_json({"book": dict(book), "message": f"Added {copies} copy/copies."})

    def handle_return_loan(self, loan_id):
        today = date.today()
        with connect_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            loan = connection.execute(
                "SELECT * FROM loans WHERE id = ?", (loan_id,)
            ).fetchone()
            if loan is None:
                self.send_json({"error": "Checkout record not found."}, 404)
                return
            if loan["returned_on"] is not None:
                self.send_json({"error": "This copy has already been returned."}, 409)
                return

            borrowed_on = date.fromisoformat(loan["borrowed_on"])
            due_on = date.fromisoformat(loan["due_on"])
            days_borrowed = max(1, (today - borrowed_on).days)
            overdue_days = max(0, (today - due_on).days)
            fine_amount = overdue_days * LATE_FEE_PER_DAY
            connection.execute(
                """
                UPDATE loans
                SET returned_on = ?, days_borrowed = ?, fine_amount = ?,
                    fine_paid = ?
                WHERE id = ?
                """,
                (
                    today.isoformat(),
                    days_borrowed,
                    fine_amount,
                    int(fine_amount == 0),
                    loan_id,
                ),
            )
            if loan["book_id"] is not None:
                connection.execute(
                    """
                    UPDATE books
                    SET available_copies = MIN(total_copies, available_copies + 1),
                        available = 1
                    WHERE id = ?
                    """,
                    (loan["book_id"],),
                )
            updated_loan = connection.execute(
                "SELECT * FROM loans WHERE id = ?", (loan_id,)
            ).fetchone()
            book = None
            if loan["book_id"] is not None:
                book = connection.execute(
                    "SELECT * FROM books WHERE id = ?", (loan["book_id"],)
                ).fetchone()

        message = (
            f"{loan['book_title']} returned on {today.isoformat()} after "
            f"{days_borrowed} day(s)."
        )
        if fine_amount:
            message += (
                f" Late fee due: ₹{fine_amount} ({overdue_days} day(s) overdue)."
            )
        self.send_json(
            {
                "loan": dict(updated_loan),
                "book": dict(book) if book else None,
                "message": message,
                "fine_amount": fine_amount,
            }
        )

    def handle_list_loans(self, query_parameters):
        status_filter = query_parameters.get("status", ["all"])[0]
        search = query_parameters.get("q", [""])[0].strip()
        conditions = []
        values = []
        if status_filter == "active":
            conditions.append("loans.returned_on IS NULL")
        elif status_filter == "returned":
            conditions.append("loans.returned_on IS NOT NULL")
        elif status_filter == "overdue":
            conditions.append("loans.returned_on IS NULL AND loans.due_on < ?")
            values.append(date.today().isoformat())
        elif status_filter != "all":
            self.send_json({"error": "Invalid loan status filter."}, 400)
            return
        if search:
            conditions.append(
                """
                (loans.book_title LIKE ? OR loans.borrower_name LIKE ?
                 OR loans.borrower_phone LIKE ? OR loans.borrower_id LIKE ?)
                """
            )
            search_term = f"%{search}%"
            values.extend((search_term,) * 4)

        sql = """
            SELECT loans.*,
                   CASE WHEN returned_on IS NULL THEN 1 ELSE 0 END AS active
            FROM loans
        """
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY loans.id DESC LIMIT 500"

        with connect_database() as connection:
            rows = connection.execute(sql, values).fetchall()
            summary = connection.execute(
                """
                SELECT
                    (SELECT COALESCE(SUM(total_copies), 0) FROM books)
                        AS total_copies,
                    (SELECT COALESCE(SUM(available_copies), 0) FROM books)
                        AS available_copies,
                    (SELECT COUNT(*) FROM loans WHERE returned_on IS NULL)
                        AS active,
                    COUNT(
                        CASE WHEN returned_on IS NULL AND due_on < ? THEN 1 END
                    ) AS overdue,
                    COALESCE(SUM(
                        CASE
                            WHEN returned_on IS NULL AND due_on < ?
                                THEN CAST(julianday(?) - julianday(due_on) AS INTEGER) * ?
                            WHEN returned_on IS NOT NULL AND fine_paid = 0
                                THEN fine_amount
                            ELSE 0
                        END
                    ), 0) AS outstanding_fines,
                    COALESCE(SUM(
                        CASE WHEN fine_paid = 1 THEN fine_amount ELSE 0 END
                    ), 0) AS fines_collected,
                    COALESCE(SUM(
                        CASE
                            WHEN fine_paid = 1 AND paid_on >= ?
                            THEN fine_amount ELSE 0
                        END
                    ), 0) AS fines_this_month,
                    COALESCE(SUM(
                        CASE
                            WHEN fine_paid = 1
                             AND paid_on >= date(?, '-6 days')
                            THEN fine_amount ELSE 0
                        END
                    ), 0) AS fines_last_7_days
                FROM loans
                """,
                (
                    date.today().isoformat(),
                    date.today().isoformat(),
                    date.today().isoformat(),
                    LATE_FEE_PER_DAY,
                    date.today().replace(day=1).isoformat(),
                    date.today().isoformat(),
                ),
            ).fetchone()
        today = date.today()
        loans = []
        for row in rows:
            loan = dict(row)
            borrowed_on = date.fromisoformat(loan["borrowed_on"])
            if loan["returned_on"] is None:
                due_on = date.fromisoformat(loan["due_on"])
                overdue_days = max(0, (today - due_on).days)
                loan["days_borrowed"] = max(1, (today - borrowed_on).days)
                loan["overdue_days"] = overdue_days
                loan["fine_due"] = overdue_days * LATE_FEE_PER_DAY
            else:
                loan["overdue_days"] = max(
                    0,
                    (date.fromisoformat(loan["returned_on"]) -
                     date.fromisoformat(loan["due_on"])).days,
                )
                loan["fine_due"] = loan["fine_amount"]
            loans.append(loan)

        with connect_database() as connection:
            daily_revenue = connection.execute(
                """
                SELECT paid_on, SUM(fine_amount) AS amount
                FROM loans
                WHERE fine_paid = 1 AND paid_on >= date(?, '-6 days')
                GROUP BY paid_on
                ORDER BY paid_on
                """,
                (date.today().isoformat(),),
            ).fetchall()

        self.send_json(
            {
                "loans": loans,
                "summary": {
                    "total_copies": summary["total_copies"],
                    "available_copies": summary["available_copies"],
                    "active": summary["active"],
                    "overdue": summary["overdue"],
                    "outstanding_fines": summary["outstanding_fines"],
                    "fines_collected": summary["fines_collected"],
                    "fines_this_month": summary["fines_this_month"],
                    "fines_last_7_days": summary["fines_last_7_days"],
                },
                "daily_revenue": [dict(row) for row in daily_revenue],
            }
        )

    def handle_record_payment(self, loan_id):
        data = self.read_json_body()
        if data is None:
            return
        method = self.string_field(data, "payment_method")
        if method not in PAYMENT_METHODS:
            self.send_json(
                {"error": "Choose Cash, UPI, or Card as the payment method."}, 400
            )
            return

        with connect_database() as connection:
            connection.execute("BEGIN IMMEDIATE")
            loan = connection.execute(
                "SELECT * FROM loans WHERE id = ?", (loan_id,)
            ).fetchone()
            if loan is None:
                self.send_json({"error": "Loan record not found."}, 404)
                return
            if loan["returned_on"] is None:
                self.send_json(
                    {"error": "A fine can be paid after the book is returned."}, 409
                )
                return
            if loan["fine_amount"] == 0:
                self.send_json({"error": "There is no fine due for this loan."}, 409)
                return
            if loan["fine_paid"]:
                self.send_json({"error": "This fine has already been paid."}, 409)
                return
            connection.execute(
                """
                UPDATE loans
                SET fine_paid = 1, payment_method = ?, paid_on = ?
                WHERE id = ?
                """,
                (method, date.today().isoformat(), loan_id),
            )
            updated_loan = connection.execute(
                "SELECT * FROM loans WHERE id = ?", (loan_id,)
            ).fetchone()

        self.send_json(
            {
                "loan": dict(updated_loan),
                "message": f"₹{loan['fine_amount']} fine payment recorded via {method}.",
            }
        )

    def parse_book_id(self, raw_id):
        try:
            book_id = int(raw_id)
        except ValueError:
            self.send_json({"error": "Invalid book ID."}, 400)
            return None
        if book_id < 1:
            self.send_json({"error": "Invalid book ID."}, 400)
            return None
        return book_id

    def read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "Invalid request body."}, 400)
            return None
        if content_length < 1 or content_length > 100_000:
            self.send_json({"error": "Request body must be between 1 and 100000 bytes."}, 400)
            return None

        try:
            data = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"error": "Request body must contain valid JSON."}, 400)
            return None
        if not isinstance(data, dict):
            self.send_json({"error": "Request body must be a JSON object."}, 400)
            return None
        return data

    @staticmethod
    def string_field(data, field):
        value = data.get(field, "")
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def positive_int_field(data, field, default=None):
        value = data.get(field, default)
        if isinstance(value, bool):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


def main():
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), LibraryRequestHandler)
    print(f"Library Catalog is running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down the Library Catalog.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
