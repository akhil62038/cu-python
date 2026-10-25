"""Command-line interface for the library catalog system."""

from library_catalog import (
    FictionBook,
    LibraryCatalog,
    NonFictionBook,
    ReferenceBook,
)


def print_results(results):
    if not results:
        print("  No matching books found.")
    for book in results:
        book.display_details()
        print("  " + "-" * 30)


def add_book_menu(catalog):
    print("  Book type: 1) Fiction  2) Non-Fiction  3) Reference")
    choice = input("  Choose (1-3): ").strip()
    title = input("  Title : ").strip()
    author = input("  Author: ").strip()
    if not title or not author:
        print("  Title and author cannot be empty.")
        return

    if choice == "1":
        fiction_type = input("  Fiction type (e.g. Novel, Fantasy): ").strip() or "Novel"
        catalog.add_book(FictionBook(title, author, fiction_type))
    elif choice == "2":
        subject = input("  Subject (e.g. History, Science): ").strip() or "General"
        catalog.add_book(NonFictionBook(title, author, subject))
    elif choice == "3":
        edition = input("  Edition (e.g. 2nd): ").strip() or "1st"
        catalog.add_book(ReferenceBook(title, author, edition))
    else:
        print("  Invalid book type.")


def load_sample_books(catalog):
    """Pre-load a few books so the menu has something to show."""
    catalog.books.extend([
        FictionBook("Harry Potter", "J.K. Rowling", "Fantasy"),
        FictionBook("The Alchemist", "Paulo Coelho", "Novel"),
        NonFictionBook("Wings of Fire", "A.P.J. Abdul Kalam", "Autobiography"),
        NonFictionBook("Sapiens", "Yuval Noah Harari", "History"),
        ReferenceBook("Oxford English Dictionary", "Oxford Press", "3rd"),
    ])


MENU = """
===== LIBRARY CATALOG SYSTEM =====
1. Add a new book
2. Remove a book
3. Search by title
4. Search by author
5. Check availability of a book
6. Display available books
7. Display all books
8. Borrow a book
9. Return a book
0. Exit
===================================
"""


def main():
    catalog = LibraryCatalog()
    load_sample_books(catalog)

    while True:
        print(MENU)
        choice = input("Enter your choice: ").strip()

        if choice == "1":
            add_book_menu(catalog)
        elif choice == "2":
            catalog.remove_book(input("  Title to remove: ").strip())
        elif choice == "3":
            print_results(catalog.search_by_title(input("  Title keyword: ").strip()))
        elif choice == "4":
            print_results(catalog.search_by_author(input("  Author keyword: ").strip()))
        elif choice == "5":
            book = catalog.find_book(input("  Book title: ").strip())
            if book is None:
                print("  Book not found.")
            elif book.check_availability():
                print("  Yes, this book is available.")
            else:
                print("  No, this book is currently borrowed.")
        elif choice == "6":
            catalog.display_available_books()
        elif choice == "7":
            catalog.display_all_books()
        elif choice == "8":
            catalog.borrow_book(input("  Title to borrow: ").strip())
        elif choice == "9":
            catalog.return_book(input("  Title to return: ").strip())
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("  Invalid choice, please try again.")


if __name__ == "__main__":
    main()
