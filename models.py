from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')

    # approval workflow
    is_approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)

    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    approver = db.relationship('User', remote_side=[id], foreign_keys=[approved_by])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_manager(self):
        return self.role == 'manager'


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    items = db.relationship('Item', backref='category', lazy=True)


class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(150))       # keep for books; nullable for others
    isbn = db.Column(db.String(20), unique=True)  # keep; nullable
    brand = db.Column(db.String(100))        # NEW
    unit = db.Column(db.String(20), default='EACH')  # NEW
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    cost_price = db.Column(db.Numeric(10, 2), default=0)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=50)
    is_catalogued = db.Column(db.Boolean, default=True)   # NEW
    is_stocked = db.Column(db.Boolean, default=False)     # NEW
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sale_items = db.relationship('SaleItem', backref='item', lazy=True)


class InventoryCount(db.Model):
    """Physical count pending manager approval."""
    __tablename__ = 'inventory_counts'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    counted_quantity = db.Column(db.Integer, nullable=False)
    system_quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    item = db.relationship('Item')
    creator = db.relationship('User', foreign_keys=[created_by])
    approver = db.relationship('User', foreign_keys=[approved_by])


class StockEntry(db.Model):
    """New stock purchases (increases inventory)."""
    __tablename__ = 'stock_entries'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)
    supplier = db.Column(db.String(150))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('Item')
    user = db.relationship('User')


class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(30), unique=True, nullable=False)
    customer_name = db.Column(db.String(150))
    total = db.Column(db.Numeric(12, 2), default=0)
    profit = db.Column(db.Numeric(12, 2), default=0)
    cashier_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cashier = db.relationship('User')
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2), default=0)


class PriceChange(db.Model):
    """Record of price changes for audit."""
    __tablename__ = 'price_changes'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    old_price = db.Column(db.Numeric(10, 2))
    new_price = db.Column(db.Numeric(10, 2))
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('Item')
    user = db.relationship('User')


class Quotation(db.Model):
    __tablename__ = 'quotations'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(30), unique=True, nullable=False)
    customer_name = db.Column(db.String(150), nullable=False)
    customer_contact = db.Column(db.String(150))
    total = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(20), default='draft')  # draft/sent/accepted/expired
    valid_until = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by_user = db.relationship('User')
    items = db.relationship('QuotationItem', backref='quotation', cascade='all, delete-orphan')


class QuotationItem(db.Model):
    __tablename__ = 'quotation_items'
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    item = db.relationship('Item')

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(30), unique=True, nullable=False)
    customer_name = db.Column(db.String(150), nullable=False)
    customer_contact = db.Column(db.String(150))
    customer_address = db.Column(db.Text)
    customer_pin = db.Column(db.String(20))          # KRA PIN for VAT
    total = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(db.String(20), default='issued')   # issued/paid/cancelled
    due_date = db.Column(db.DateTime)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotations.id'))
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by_user = db.relationship('User')
    items = db.relationship('InvoiceItem', backref='invoice',
                            cascade='all, delete-orphan')


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    description = db.Column(db.String(255))          # snapshot of title at time of issue
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    item = db.relationship('Item')