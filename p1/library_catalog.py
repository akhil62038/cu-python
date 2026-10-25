"""Core classes for a simple library catalog system."""


class Book:
    """Parent class: common attributes and methods for all books."""

    def __init__(self, title, author, genre, available=True):
        self.title = title
        self.author = author
        self.genre = genre
        self.available = available

    def display_details(self):
        """Print the book's details."""
        status = "Available" if self.available else "Borrowed"
        print(f"  Title  : {self.title}")
        print(f"  Author : {self.author}")
        print(f"  Genre  : {self.genre}")
        print(f"  Type   : {self.book_type()}")
        print(f"  Status : {status}")

    def check_availability(self):
        """Return True if the book can be borrowed."""
        return self.available

    def update_availability(self, status):
        """Set availability to True or False."""
        self.available = status

    def book_type(self):
        return "General Book"

    def can_be_borrowed(self):
        return True


class FictionBook(Book):
    """Fiction book: adds a 'fiction_type' (novel, fantasy, mystery...)."""

    def __init__(self, title, author, fiction_type="Novel", available=True):
        super().__init__(title, author, "Fiction", available)
        self.fiction_type = fiction_type

    def display_details(self):
        super().display_details()
        print(f"  Fiction Type : {self.fiction_type}")

    def book_type(self):
        return "Fiction"


class NonFictionBook(Book):
    """Non-fiction book: adds a 'subject' (history, science...)."""

    def __init__(self, title, author, subject, available=True):
        super().__init__(title, author, "Non-Fiction", available)
        self.subject = subject

    def display_details(self):
        super().display_details()
        print(f"  Subject : {self.subject}")

    def book_type(self):
        return "Non-Fiction"


class ReferenceBook(Book):
    """Reference book (dictionary, encyclopedia): cannot be borrowed."""

    def __init__(self, title, author, edition="1st", available=True):
        super().__init__(title, author, "Reference", available)
        self.edition = edition

    def display_details(self):
        super().display_details()
        print(f"  Edition : {self.edition}")
        print("  Note    : Reference only - cannot be taken home")

    def book_type(self):
        return "Reference"

    def can_be_borrowed(self):
        return False


class LibraryCatalog:
    """Manages the whole collection of books."""

    def __init__(self):
        self.books = []

    def add_book(self, book):
        if self.find_book(book.title):
            print("  This title is already in the catalog.")
            return False
        self.books.append(book)
        print(f"  '{book.title}' added to the catalog.")
        return True

    def remove_book(self, title):
        book = self.find_book(title)
        if book:
            self.books.remove(book)
            print(f"  '{book.title}' removed from the catalog.")
            return True
        print("  Book not found.")
        return False

    def find_book(self, title):
        """Exact (case-insensitive) title match."""
        for book in self.books:
            if book.title.lower() == title.lower():
                return book
        return None

    def search_by_title(self, keyword):
        return [book for book in self.books if keyword.lower() in book.title.lower()]

    def search_by_author(self, keyword):
        return [book for book in self.books if keyword.lower() in book.author.lower()]

    def display_available_books(self):
        available = [book for book in self.books if book.check_availability()]
        if not available:
            print("  No books are available right now.")
        for book in available:
            book.display_details()
            print("  " + "-" * 30)

    def display_all_books(self):
        if not self.books:
            print("  The catalog is empty.")
        for book in self.books:
            book.display_details()
            print("  " + "-" * 30)

    def borrow_book(self, title):
        book = self.find_book(title)
        if book is None:
            print("  Book not found.")
        elif not book.can_be_borrowed():
            print("  Reference books cannot be borrowed.")
        elif not book.check_availability():
            print("  Sorry, this book is already borrowed.")
        else:
            book.update_availability(False)
            print(f"  You borrowed '{book.title}'. Enjoy reading!")

    def return_book(self, title):
        book = self.find_book(title)
        if book is None:
            print("  Book not found.")
        elif book.check_availability():
            print("  This book was not borrowed.")
        else:
            book.update_availability(True)
            print(f"  Thank you! '{book.title}' has been returned.")
