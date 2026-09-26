# ZABACH ENTERPRISES — Inventory & Sales Management

A Flask-based web application for managing inventory, sales, quotations, and
customer orders for ZABACH ENTERPRISES LIMITED — a supplier of laboratory
equipment, stationery, exercise books, textbooks, and institutional supplies
based in Kilifi, Kenya.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Roles & Permissions](#roles--permissions)
- [Data Model](#data-model)
- [Catalogue vs Inventory](#catalogue-vs-inventory)
- [Installation (Local)](#installation-local)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Importing the Price List](#importing-the-price-list)
- [Running the App](#running-the-app)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Default Accounts](#default-accounts)
- [Roadmap](#roadmap)

---

## Overview

ZABACH ENTERPRISES supplies institutions (schools, colleges, laboratories) with
a wide range of items — from laboratory chemicals and glassware to stationery,
exercise books, and textbooks. The business model is quote-driven: a customer
requests a quotation, ZABACH procures the items, and delivers them.

This app reflects that workflow:

- **Catalogue** — everything ZABACH can supply (~1,440 items imported from the
  master price list), even if not physically in stock
- **Inventory** — the subset of items currently on the shelf, with quantities
- **Quotations** — generated from the catalogue for institutional customers
- **Sales** — POS-style transactions for stocked items, with printed receipts

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web framework | Flask 3.x |
| ORM | SQLAlchemy 2.x (via Flask-SQLAlchemy) |
| Database | PostgreSQL 15+ |
| Auth | Flask-Login + Werkzeug password hashing |
| Forms | Flask-WTF + WTForms |
| Frontend | Bootstrap 5.3 + vanilla JS |
| Deployment target | PythonAnywhere |

---

## Features

### Inventory & Stock

- [x] Add new items (manager only)
- [x] Edit item details — title, author, brand, category, price, reorder level
- [x] Change individual item prices with full audit trail (`PriceChange`)
- [x] Bulk CSV upload of items (manager only)
- [x] Track physical stock quantity per item
- [x] Configurable reorder level per item
- [x] Record stock purchases with supplier and unit cost (`StockEntry`)
- [x] Mark items as stocked/unstocked independently of catalogue status

### Catalogue

- [x] Import entire master price list (~1,440 items) via a cleaning script
- [x] Search by title or brand
- [x] Filter by category
- [x] One-click "Add to stock" from catalogue
- [x] Distinguishes "we can supply this" from "we have this in stock"

### Sales (POS)

- [x] Session-based shopping cart
- [x] Add / remove / clear line items
- [x] Stock validation before adding to cart
- [x] Automatic inventory deduction on sale completion
- [x] Print-ready receipt with ZABACH letterhead
- [x] Auto-generated receipt reference numbers
- [x] Records unit cost at time of sale for accurate profit calculation

### Quotations

- [x] Create quotations for institutional customers
- [x] Add line items from the catalogue
- [x] Custom pricing per line item
- [x] Print-ready quotation with letterhead
- [x] Terms & conditions section
- [x] Convert a quotation into a sale with one click
- [x] Track quotation status (draft / sent / accepted / expired)
- [x] Optional validity date

### Physical Inventory Count

- [x] Users submit counted quantities for approval
- [x] System quantity captured at submission time
- [x] Manager reviews and approves or rejects
- [x] Approved counts update the system quantity
- [x] Full audit trail (who submitted, who approved, when)
- [x] Pending counts badge on dashboard

### Reporting & Dashboard

- [x] Total items in stock, stock value
- [x] Today's sales and profit
- [x] Low-stock alerts (below reorder level)
- [x] Most-bought items (top 5)
- [x] Catalogue vs stocked item counts
- [x] Sales report with date range filter
- [x] Profit by item (top 20)
- [x] Profit by category
- [x] Recent sales list

### User Management

- [x] Self-registration with manager approval workflow
- [x] Manager can create users directly (auto-approved)
- [x] Manager can approve/reject pending registrations
- [x] Deactivate / reactivate users
- [x] Two roles: `user` and `manager`
- [x] Role-based access control on routes
- [x] Pending user count badge on dashboard

### UI / UX

- [x] Branded navbar with ZABACH ENTERPRISES
- [x] Active tab highlighting
- [x] Search-as-you-type autocomplete for item selection
- [x] Flash messages for all user actions
- [x] Print-friendly receipts and quotations
- [x] Custom letterhead (HTML, no image dependency)

---

## Roles & Permissions

| Action | User | Manager |
|---|:---:|:---:|
| Log in, log out | ✅ | ✅ |
| Register (pending approval) | ✅ | ✅ |
| View dashboard | ✅ | ✅ |
| View catalogue | ✅ | ✅ |
| View inventory | ✅ | ✅ |
| Record a sale / print receipt | ✅ | ✅ |
| Create a quotation | ✅ | ✅ |
| Submit a physical count | ✅ | ✅ |
| **Add stock (purchase entry)** | ❌ | ✅ |
| **Add / edit items** | ❌ | ✅ |
| **Change prices** | ❌ | ✅ |
| **Bulk upload items (CSV)** | ❌ | ✅ |
| **Approve inventory counts** | ❌ | ✅ |
| **Approve new user registrations** | ❌ | ✅ |
| **Create users directly** | ❌ | ✅ |
| **View sales & profit reports** | ❌ | ✅ |
| **Add stock from catalogue** | ❌ | ✅ |

---

## Data Model
