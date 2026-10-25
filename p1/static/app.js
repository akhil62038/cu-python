const checkoutForm = document.querySelector("#checkout-form");
const checkoutBook = document.querySelector("#checkout-book");
const checkoutError = document.querySelector("#checkout-error");
const notice = document.querySelector("#notice");
const loanRows = document.querySelector("#loan-rows");
const inventoryRows = document.querySelector("#inventory-rows");
const inventorySearch = document.querySelector("#inventory-search");
const inventoryFilter = document.querySelector("#inventory-filter");
const loanSearch = document.querySelector("#loan-search");
const loanFilter = document.querySelector("#loan-filter");
const addDialog = document.querySelector("#add-dialog");
const addForm = document.querySelector("#add-form");
const formError = document.querySelector("#form-error");
const restockDialog = document.querySelector("#restock-dialog");
const restockForm = document.querySelector("#restock-form");
const restockError = document.querySelector("#restock-error");
const paymentDialog = document.querySelector("#payment-dialog");
const paymentForm = document.querySelector("#payment-form");
const paymentDescription = document.querySelector("#payment-description");
const paymentError = document.querySelector("#payment-error");
const bookTypeSelect = document.querySelector("#book-type");
const detailLabel = document.querySelector("#detail-label");
const detailInput = document.querySelector("#detail");

let books = [];
let selectedRestockBook;
let selectedPaymentLoan;
let inventoryTimer;
let loanTimer;

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "The request could not be completed.");
  }
  return data;
}

function localIsoDate(value = new Date()) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDate(value) {
  if (!value) {
    return "—";
  }
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function showNotice(message, isError = false) {
  notice.textContent = message;
  notice.classList.toggle("error", isError);
  notice.hidden = false;
}

function hideNotice() {
  notice.hidden = true;
  notice.classList.remove("error");
}

function addCell(row, content, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  if (content instanceof Node) {
    cell.append(content);
  } else {
    cell.textContent = content;
  }
  row.append(cell);
  return cell;
}

function updateDueDate() {
  const issueDate = document.querySelector("#borrowed-on").value;
  const days = Number(document.querySelector("#loan-days").value);
  if (!issueDate || !Number.isInteger(days)) {
    document.querySelector("#due-on").value = "";
    return;
  }
  const [year, month, day] = issueDate.split("-").map(Number);
  const dueDate = new Date(year, month - 1, day + days);
  document.querySelector("#due-on").value = localIsoDate(dueDate);
}

function showSelectedStock() {
  const book = books.find((item) => String(item.id) === checkoutBook.value);
  const stockCheck = document.querySelector("#stock-check");
  const submit = checkoutForm.querySelector('button[type="submit"]');
  if (!book) {
    stockCheck.textContent = "Choose a title to check availability.";
    stockCheck.className = "stock-check";
    submit.disabled = true;
    return;
  }
  const canIssue = book.available_copies > 0 && book.book_type !== "Reference";
  stockCheck.textContent = book.book_type === "Reference"
    ? "Reference copies are for in-library use and cannot be checked out."
    : book.available_copies > 0
      ? `${book.available_copies} of ${book.total_copies} copies available to issue.`
      : "No copies available. Restock this title or check again after a return.";
  stockCheck.className = `stock-check ${canIssue ? "stock-good" : "stock-low"}`;
  submit.disabled = !canIssue;
}

async function loadBooks() {
  const data = await request("/api/books");
  books = data.books;
  renderCheckoutBooks();
  renderInventory();
  renderAnalytics(data.books);
  showSelectedStock();
}

function renderCheckoutBooks() {
  const currentValue = checkoutBook.value;
  checkoutBook.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose a book from inventory";
  checkoutBook.append(placeholder);
  for (const book of books) {
    const option = document.createElement("option");
    option.value = book.id;
    const stock = book.book_type === "Reference"
      ? "reference only"
      : `${book.available_copies} available`;
    option.textContent = `${book.title} — ${stock}`;
    option.disabled = book.available_copies === 0 || book.book_type === "Reference";
    checkoutBook.append(option);
  }
  if (books.some((book) => String(book.id) === currentValue)) {
    checkoutBook.value = currentValue;
  }
}

function renderInventory() {
  const search = inventorySearch.value.trim().toLocaleLowerCase();
  const filter = inventoryFilter.value;
  const matches = books.filter((book) => {
    const matchesSearch = `${book.title} ${book.author}`.toLocaleLowerCase().includes(search);
    const matchesFilter = filter === "all"
      || (filter === "available" && book.available_copies === book.total_copies)
      || (filter === "borrowed" && book.checked_out > 0 && book.available_copies > 0)
      || (filter === "out" && book.available_copies === 0);
    return matchesSearch && matchesFilter;
  });
  inventoryRows.replaceChildren();
  document.querySelector("#inventory-empty").hidden = matches.length > 0;

  for (const book of matches) {
    const row = document.createElement("tr");
    const identity = document.createElement("div");
    identity.className = "table-book";
    const title = document.createElement("strong");
    title.textContent = book.title;
    const author = document.createElement("span");
    author.textContent = book.author;
    identity.append(title, author);
    addCell(row, identity);
    addCell(row, book.book_type);
    addCell(row, book.total_copies, "number-cell");
    addCell(row, book.available_copies, "number-cell available-cell");
    addCell(row, book.checked_out, "number-cell");

    const status = document.createElement("span");
    const isOut = book.available_copies === 0;
    const isPartial = book.available_copies < book.total_copies && !isOut;
    status.className = `pill ${isOut ? "pill-red" : isPartial ? "pill-amber" : "pill-green"}`;
    status.textContent = isOut ? "Out of stock" : isPartial ? "Partly on loan" : "In stock";
    addCell(row, status);

    const restock = document.createElement("button");
    restock.type = "button";
    restock.className = "text-button";
    restock.textContent = "+ Add copies";
    restock.addEventListener("click", () => openRestockDialog(book));
    addCell(row, restock, "action-cell");
    inventoryRows.append(row);
  }
}

function renderAnalytics(inventory) {
  const total = inventory.reduce((sum, book) => sum + book.total_copies, 0);
  const available = inventory.reduce((sum, book) => sum + book.available_copies, 0);
  const reference = inventory
    .filter((book) => book.book_type === "Reference")
    .reduce((sum, book) => sum + book.total_copies, 0);
  document.querySelector("#metric-total-copies").textContent = total;
  document.querySelector("#metric-available").textContent = available;
  document.querySelector("#metric-availability-rate").textContent =
    `${total ? Math.round((available / total) * 100) : 0}%`;
  document.querySelector("#metric-titles").textContent = inventory.length;
  document.querySelector("#metric-reference").textContent = reference;
}

async function loadLoans() {
  const parameters = new URLSearchParams({
    status: loanFilter.value,
    q: loanSearch.value.trim(),
  });
  const data = await request(`/api/loans?${parameters}`);
  const { summary } = data;
  const onLoan = summary.total_copies - summary.available_copies;
  document.querySelector("#metric-on-loan").textContent = onLoan;
  document.querySelector("#metric-overdue").textContent = summary.overdue;
  document.querySelector("#metric-revenue").textContent = formatMoney(summary.fines_this_month);
  document.querySelector("#metric-revenue-total").textContent = formatMoney(summary.fines_collected);
  document.querySelector("#metric-outstanding").textContent = formatMoney(summary.outstanding_fines);
  document.querySelector("#revenue-week-total").textContent = formatMoney(summary.fines_last_7_days);
  renderRevenueChart(data.daily_revenue);
  renderLoans(data.loans);
}

function renderRevenueChart(revenue) {
  const chart = document.querySelector("#revenue-chart");
  chart.replaceChildren();
  const amounts = new Map(revenue.map((entry) => [entry.paid_on, entry.amount]));
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - (6 - index));
    return { date: localIsoDate(day), label: new Intl.DateTimeFormat("en", { weekday: "short" }).format(day) };
  });
  const maximum = Math.max(1, ...days.map((day) => amounts.get(day.date) || 0));
  for (const day of days) {
    const column = document.createElement("div");
    column.className = "chart-column";
    const value = amounts.get(day.date) || 0;
    const bar = document.createElement("div");
    bar.className = "chart-bar";
    bar.style.height = `${Math.max(4, (value / maximum) * 100)}%`;
    bar.title = `${day.label}: ${formatMoney(value)}`;
    const label = document.createElement("span");
    label.textContent = day.label;
    column.append(bar, label);
    chart.append(column);
  }
}

function renderLoans(loans) {
  loanRows.replaceChildren();
  document.querySelector("#loans-empty").hidden = loans.length > 0;
  for (const loan of loans) {
    const row = document.createElement("tr");
    const book = document.createElement("div");
    book.className = "table-book";
    const bookTitle = document.createElement("strong");
    bookTitle.textContent = loan.book_title;
    const loanId = document.createElement("span");
    loanId.textContent = `Loan #${String(loan.id).padStart(4, "0")}`;
    book.append(bookTitle, loanId);
    addCell(row, book);

    const customer = document.createElement("div");
    customer.className = "table-book customer-cell";
    const name = document.createElement("strong");
    name.textContent = loan.borrower_name;
    const contact = document.createElement("span");
    contact.textContent = [loan.borrower_phone, loan.borrower_id && `ID ${loan.borrower_id}`]
      .filter(Boolean).join(" · ") || "Legacy checkout · details not recorded";
    customer.append(name, contact);
    addCell(row, customer);
    addCell(row, formatDate(loan.borrowed_on));
    addCell(row, loan.active ? formatDate(loan.due_on) : `Returned ${formatDate(loan.returned_on)}`);
    addCell(row, loan.active
      ? `${loan.days_borrowed} day(s)`
      : `${loan.days_borrowed || 1} day(s)`, "number-cell");

    const statusCell = document.createElement("div");
    statusCell.className = "loan-status";
    const status = document.createElement("span");
    status.className = `pill ${loan.active && loan.overdue_days > 0 ? "pill-red" : loan.active ? "pill-blue" : "pill-green"}`;
    status.textContent = loan.active
      ? loan.overdue_days > 0 ? `${loan.overdue_days}d overdue` : "On loan"
      : "Returned";
    statusCell.append(status);
    if (loan.active && loan.overdue_days > 0) {
      const fine = document.createElement("small");
      fine.textContent = `${formatMoney(loan.fine_due)} accruing`;
      statusCell.append(fine);
    } else if (!loan.active && loan.fine_amount > 0) {
      const fine = document.createElement("small");
      fine.textContent = loan.fine_paid
        ? `${formatMoney(loan.fine_amount)} paid`
        : `${formatMoney(loan.fine_amount)} due`;
      statusCell.append(fine);
    }
    addCell(row, statusCell);

    const actionCell = document.createElement("div");
    actionCell.className = "row-actions";
    if (loan.active) {
      const returnButton = document.createElement("button");
      returnButton.type = "button";
      returnButton.className = "small-button";
      returnButton.textContent = "Check in";
      returnButton.addEventListener("click", () => returnLoan(loan));
      actionCell.append(returnButton);
    } else if (loan.fine_amount > 0 && !loan.fine_paid) {
      const payButton = document.createElement("button");
      payButton.type = "button";
      payButton.className = "small-button";
      payButton.textContent = "Record fine";
      payButton.addEventListener("click", () => openPaymentDialog(loan));
      actionCell.append(payButton);
    } else {
      actionCell.textContent = "—";
      actionCell.classList.add("muted-cell");
    }
    addCell(row, actionCell);
    loanRows.append(row);
  }
}

async function refreshDashboard() {
  try {
    await Promise.all([loadBooks(), loadLoans()]);
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function returnLoan(loan) {
  const confirmed = window.confirm(
    `Check in "${loan.book_title}" from ${loan.borrower_name}?\nThe return date will be recorded as today.`,
  );
  if (!confirmed) {
    return;
  }
  try {
    const data = await request(`/api/loans/${loan.id}/return`, { method: "POST" });
    showNotice(data.message);
    await refreshDashboard();
  } catch (error) {
    showNotice(error.message, true);
  }
}

function openRestockDialog(book) {
  selectedRestockBook = book;
  restockForm.reset();
  restockError.hidden = true;
  document.querySelector("#restock-title").textContent = `Add copies · ${book.title}`;
  restockDialog.showModal();
}

function openPaymentDialog(loan) {
  selectedPaymentLoan = loan;
  paymentForm.reset();
  paymentError.hidden = true;
  paymentDescription.textContent =
    `${loan.borrower_name} owes ${formatMoney(loan.fine_amount)} for ` +
    `"${loan.book_title}". Record the method after receiving payment.`;
  paymentDialog.showModal();
}

function updateDetailField() {
  const labels = {
    Fiction: ["Fiction type", "e.g. Novel, Fantasy"],
    "Non-Fiction": ["Subject", "e.g. History, Science"],
    Reference: ["Edition", "e.g. 2nd"],
  };
  const [label, placeholder] = labels[bookTypeSelect.value];
  detailLabel.textContent = label;
  detailInput.placeholder = placeholder;
}

document.querySelector("#today-label").textContent = new Intl.DateTimeFormat("en-IN", {
  weekday: "short", day: "numeric", month: "short", year: "numeric",
}).format(new Date());
document.querySelector("#borrowed-on").value = localIsoDate();
updateDueDate();
document.querySelector("#loan-days").addEventListener("change", updateDueDate);
checkoutBook.addEventListener("change", showSelectedStock);
document.querySelector("#top-checkout").addEventListener("click", () => {
  document.querySelector("#checkout").scrollIntoView({ behavior: "smooth" });
  checkoutBook.focus({ preventScroll: true });
});

checkoutForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  checkoutError.hidden = true;
  const formData = new FormData(checkoutForm);
  const payload = Object.fromEntries(formData);
  payload.loan_days = Number(payload.loan_days);
  try {
    const data = await request(`/api/books/${payload.book_id}/borrow`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showNotice(data.message);
    checkoutForm.reset();
    document.querySelector("#borrowed-on").value = localIsoDate();
    updateDueDate();
    showSelectedStock();
    await refreshDashboard();
  } catch (error) {
    checkoutError.textContent = error.message;
    checkoutError.hidden = false;
  }
});

document.querySelector("#open-add").addEventListener("click", () => {
  addForm.reset();
  formError.hidden = true;
  updateDetailField();
  addDialog.showModal();
});

addForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;
  const formData = new FormData(addForm);
  const payload = Object.fromEntries(formData);
  payload.total_copies = Number(payload.total_copies);
  try {
    const data = await request("/api/books", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    addDialog.close();
    showNotice(`"${data.book.title}" added to inventory.`);
    await refreshDashboard();
  } catch (error) {
    formError.textContent = error.message;
    formError.hidden = false;
  }
});

restockForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  restockError.hidden = true;
  if (!selectedRestockBook) {
    return;
  }
  try {
    const data = await request(`/api/books/${selectedRestockBook.id}/stock`, {
      method: "POST",
      body: JSON.stringify({ copies: Number(restockForm.elements.copies.value) }),
    });
    restockDialog.close();
    showNotice(data.message);
    await refreshDashboard();
  } catch (error) {
    restockError.textContent = error.message;
    restockError.hidden = false;
  }
});

paymentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  paymentError.hidden = true;
  if (!selectedPaymentLoan) {
    return;
  }
  try {
    const data = await request(`/api/loans/${selectedPaymentLoan.id}/pay`, {
      method: "POST",
      body: JSON.stringify({ payment_method: paymentForm.elements.payment_method.value }),
    });
    paymentDialog.close();
    showNotice(data.message);
    await loadLoans();
  } catch (error) {
    paymentError.textContent = error.message;
    paymentError.hidden = false;
  }
});

document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector(`#${button.dataset.closeDialog}`).close();
  });
});
bookTypeSelect.addEventListener("change", updateDetailField);
inventorySearch.addEventListener("input", () => {
  window.clearTimeout(inventoryTimer);
  inventoryTimer = window.setTimeout(renderInventory, 150);
});
inventoryFilter.addEventListener("change", renderInventory);
loanFilter.addEventListener("change", loadLoans);
loanSearch.addEventListener("input", () => {
  window.clearTimeout(loanTimer);
  loanTimer = window.setTimeout(() => {
    loadLoans().catch((error) => showNotice(error.message, true));
  }, 180);
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});

refreshDashboard();
