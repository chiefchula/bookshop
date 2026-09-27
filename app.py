from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, redirect, url_for, flash, request,
                   abort, session, jsonify)
from flask_login import (LoginManager, login_user, logout_user, login_required,
                         current_user)
from sqlalchemy import func, or_
from config_postgre import Config
from models import (db, User, Category, Item, InventoryCount, StockEntry,
                    Sale, SaleItem, PriceChange, Quotation, QuotationItem)
from forms import (LoginForm, RegisterForm, UserForm, ItemForm, PriceChangeForm,
                   StockEntryForm, CountForm, SaleForm, QuotationForm)

import weasyprint

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_manager:
            abort(403)
        return f(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    if not current_user.is_authenticated:
        return {}
    pending = 0
    if current_user.is_manager:
        try:
            pending = InventoryCount.query.filter_by(status='pending').count()
        except Exception:
            pending = 0
    return {'pending_counts_global': pending}


# ---------- CLI ----------
@app.cli.command('init-db')
def init_db():
    db.create_all()
    if not User.query.filter_by(role='manager').first():
        m = User(username='manager', email='manager@bookshop.local', role='manager',
                 is_approved=True, approved_at=datetime.utcnow())
        m.set_password('changeme123')
        db.session.add(m)
        if not Category.query.first():
            db.session.add_all([Category(name='Fiction'), Category(name='Non-Fiction'),
                                Category(name='Children'), Category(name='Academic')])
        db.session.commit()
        print("Created default manager: manager / changeme123")
    print("Database initialized.")


# ---------- Auth ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.active and user.check_password(form.password.data):
            if not user.is_approved:
                flash('Your account is pending manager approval.', 'warning')
                return render_template('login.html', form=form)
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials or inactive account.', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter((User.username == form.username.data) |
                             (User.email == form.email.data)).first():
            flash('Username or email already taken.', 'danger')
        else:
            u = User(username=form.username.data, email=form.email.data,
                     role='user', is_approved=False)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            flash('Registration submitted. A manager will approve your account shortly.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------- Dashboard ----------
@app.route('/')
@login_required
def dashboard():
    low_stock_all = (Item.query
                     .filter(Item.is_stocked == True)
                     .filter(Item.quantity < Item.reorder_level)
                     .order_by(Item.quantity.asc())
                     .all())
    low_stock = low_stock_all[:10]
    low_stock_total = len(low_stock_all)

    most_bought = (db.session.query(Item, func.sum(SaleItem.quantity).label('total'))
                   .join(SaleItem).group_by(Item.id)
                   .order_by(func.sum(SaleItem.quantity).desc())
                   .limit(5).all())

    total_items = db.session.query(func.sum(Item.quantity)).scalar() or 0
    total_value = db.session.query(func.sum(Item.quantity * Item.price)).scalar() or 0

    today = datetime.utcnow().date()
    today_sales, today_profit = (db.session.query(
                                    func.coalesce(func.sum(Sale.total), 0),
                                    func.coalesce(func.sum(Sale.profit), 0))
                                 .filter(func.date(Sale.created_at) == today)
                                 .first())

    pending_counts = InventoryCount.query.filter_by(status='pending').count()
    pending_items  = (InventoryCount.query
                      .filter_by(status='pending')
                      .order_by(InventoryCount.created_at)
                      .limit(5).all())

    pending_users_count = User.query.filter_by(is_approved=False).count()

    catalogue_total = Item.query.filter_by(is_catalogued=True).count()
    stocked_total   = Item.query.filter_by(is_stocked=True).count()

    return render_template(
        'dashboard.html',
        low_stock=low_stock,
        low_stock_total=low_stock_total,
        most_bought=most_bought,
        total_items=total_items,
        total_value=total_value,
        today_sales=today_sales,
        today_profit=today_profit,
        pending_counts=pending_counts,
        pending_items=pending_items,
        pending_users_count=pending_users_count,
        catalogue_total=catalogue_total,
        stocked_total=stocked_total,
    )


# ---------- Inventory ----------
@app.route('/inventory')
@login_required
def inventory():
    q = request.args.get('q', '').strip()
    low_only = request.args.get('low') == '1'

    query = Item.query.filter(Item.is_stocked == True)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Item.title.ilike(like), Item.brand.ilike(like)))
    if low_only:
        query = query.filter(Item.quantity < Item.reorder_level)

    items = query.order_by(Item.title).all()
    return render_template('inventory.html', items=items, q=q, low_only=low_only)


@app.route('/items/new', methods=['GET', 'POST'])
@login_required
@manager_required
def item_new():
    form = ItemForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by('name')]
    if form.validate_on_submit():
        item = Item(
            title=form.title.data, author=form.author.data, isbn=form.isbn.data or None,
            category_id=form.category_id.data, cost_price=form.cost_price.data or 0,
            price=form.price.data, quantity=form.quantity.data or 0,
            reorder_level=form.reorder_level.data or 50,
            is_catalogued=True,
            is_stocked=(form.quantity.data or 0) > 0,
        )
        db.session.add(item)
        db.session.commit()
        flash('Item created.', 'success')
        return redirect(url_for('inventory'))
    return render_template('item_form.html', form=form, title='New Item')


@app.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def item_edit(item_id):
    item = db.session.get(Item, item_id) or abort(404)
    form = ItemForm(obj=item)
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by('name')]
    if form.validate_on_submit():
        item.title = form.title.data
        item.author = form.author.data
        item.isbn = form.isbn.data or None
        item.category_id = form.category_id.data
        item.cost_price = form.cost_price.data or 0
        item.price = form.price.data
        item.reorder_level = form.reorder_level.data or 50
        db.session.commit()
        flash('Item updated.', 'success')
        return redirect(url_for('inventory'))
    return render_template('item_form.html', form=form, title='Edit Item')


@app.route('/items/<int:item_id>/price', methods=['GET', 'POST'])
@login_required
@manager_required
def item_price(item_id):
    item = db.session.get(Item, item_id) or abort(404)
    form = PriceChangeForm()
    if form.validate_on_submit():
        pc = PriceChange(item_id=item.id, old_price=item.price,
                         new_price=form.new_price.data, changed_by=current_user.id)
        item.price = form.new_price.data
        db.session.add(pc)
        db.session.commit()
        flash('Price updated.', 'success')
        return redirect(url_for('inventory'))
    return render_template('item_form.html', form=form,
                           title=f'Change Price: {item.title}', single=True)


# ---------- Bulk upload ----------
@app.route('/items/bulk', methods=['GET', 'POST'])
@login_required
@manager_required
def items_bulk():
    if request.method == 'POST':
        import csv, io
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Please choose a CSV file.', 'warning')
            return redirect(url_for('items_bulk'))
        if not file.filename.lower().endswith('.csv'):
            flash('Only .csv files are supported.', 'danger')
            return redirect(url_for('items_bulk'))

        stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
        reader = csv.DictReader(stream)
        required = {'title', 'price'}
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        missing = required - set(headers.keys())
        if missing:
            flash(f'Missing required columns: {", ".join(missing)}', 'danger')
            return redirect(url_for('items_bulk'))

        cat_cache = {c.name.lower(): c for c in Category.query.all()}
        created = updated = skipped = 0
        errors = []

        for lineno, raw in enumerate(reader, start=2):
            try:
                row = {(k or '').strip().lower(): (v.strip() if isinstance(v, str) else v)
                       for k, v in raw.items()}
                title = row.get('title', '').strip()
                if not title:
                    skipped += 1
                    continue
                price = float(row.get('price', 0) or 0)
                cost_price = float(row.get('cost_price', 0) or 0)
                quantity = int(float(row.get('quantity', 0) or 0))
                reorder = int(float(row.get('reorder_level', 50) or 50))
                isbn = row.get('isbn') or None
                author = row.get('author') or None
                brand = (row.get('brand') or '').strip() or None
                unit = (row.get('unit') or 'EACH').strip().upper() or 'EACH'
                cat_name = (row.get('category') or '').strip()

                category = None
                if cat_name:
                    key = cat_name.lower()
                    if key not in cat_cache:
                        c = Category(name=cat_name)
                        db.session.add(c)
                        db.session.flush()
                        cat_cache[key] = c
                    category = cat_cache[key]

                existing = None
                if isbn:
                    existing = Item.query.filter_by(isbn=isbn).first()
                if not existing:
                    q = Item.query.filter(func.upper(Item.title) == title.upper())
                    if category:
                        q = q.filter(Item.category_id == category.id)
                    existing = q.first()

                if existing:
                    existing.quantity += quantity
                    existing.price = price
                    if cost_price:
                        existing.cost_price = cost_price
                    if brand:
                        existing.brand = brand
                    if unit:
                        existing.unit = unit
                    if category:
                        existing.category_id = category.id
                    updated += 1
                else:
                    item = Item(title=title, author=author, isbn=isbn,
                                brand=brand, unit=unit,
                                category_id=category.id if category else None,
                                price=price, cost_price=cost_price,
                                quantity=quantity, reorder_level=reorder,
                                is_catalogued=True,
                                is_stocked=quantity > 0)
                    db.session.add(item)
                    created += 1
            except Exception as e:
                errors.append(f'Row {lineno}: {e}')
                skipped += 1

        db.session.commit()
        flash(f'Bulk upload done — created: {created}, updated: {updated}, '
              f'skipped: {skipped}.', 'success')
        for err in errors[:10]:
            flash(err, 'warning')
        return redirect(url_for('inventory'))

    sample = (
        "title,author,isbn,category,brand,unit,cost_price,price,quantity,reorder_level\n"
        "Things Fall Apart,Chinua Achebe,9780385474542,Fiction,,EACH,450,700,25,10\n"
    )
    return render_template('items_bulk.html', sample=sample)


# ---------- Catalogue ----------
@app.route('/catalogue')
@login_required
def catalogue():
    q = request.args.get('q', '').strip()
    cat_id = request.args.get('category', type=int)

    query = Item.query.filter(Item.is_catalogued == True)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Item.title.ilike(like), Item.brand.ilike(like)))
    if cat_id:
        query = query.filter(Item.category_id == cat_id)

    items = query.order_by(Item.category_id, Item.title).all()
    categories = Category.query.order_by('name').all()
    return render_template('catalogue.html', items=items, categories=categories,
                           q=q, cat_id=cat_id)


@app.route('/catalogue/<int:item_id>/stock', methods=['POST'])
@login_required
@manager_required
def catalogue_to_stock(item_id):
    item = db.session.get(Item, item_id) or abort(404)
    qty = request.form.get('quantity', type=int) or 0
    cost = request.form.get('cost_price', type=float) or 0

    if qty <= 0:
        flash('Quantity must be greater than zero.', 'warning')
        return redirect(url_for('catalogue'))

    item.quantity += qty
    if cost > 0:
        item.cost_price = cost
    item.is_stocked = True

    db.session.add(StockEntry(item_id=item.id, quantity=qty, unit_cost=cost,
                              supplier='From catalogue',
                              created_by=current_user.id))
    db.session.commit()

    flash(f'Added {qty} × {item.title} to stock. New quantity: {item.quantity}.',
          'success')
    return redirect(url_for('catalogue', q=item.title) + f'#item-{item.id}')


# ---------- Stock purchase ----------
@app.route('/stock/new', methods=['GET', 'POST'])
@login_required
@manager_required
def stock_new():
    form = StockEntryForm()

    if form.validate_on_submit():
        item_id = request.form.get('item_id', type=int)
        if not item_id:
            flash('Please select an item from the search results.', 'danger')
            return render_template('stock_new.html', form=form, preselected=None)

        item = db.session.get(Item, item_id) or abort(404)
        item.quantity += form.quantity.data
        item.cost_price = form.unit_cost.data
        item.is_stocked = True

        db.session.add(StockEntry(
            item_id=item.id,
            quantity=form.quantity.data,
            unit_cost=form.unit_cost.data,
            supplier=form.supplier.data,
            created_by=current_user.id,
        ))
        db.session.commit()

        flash(f'Added {form.quantity.data} × {item.title} to stock. '
              f'New quantity: {item.quantity}.', 'success')
        return redirect(url_for('catalogue', q=item.title) + f'#item-{item.id}')

    preselected = None
    preselect_id = request.args.get('item_id', type=int)
    if preselect_id:
        preselected = db.session.get(Item, preselect_id)

    return render_template('stock_new.html', form=form, preselected=preselected)


# ---------- API: item search ----------
@app.route('/api/items/search')
@login_required
def api_items_search():
    q = request.args.get('q', '').strip()
    only_stocked = request.args.get('stocked') == '1'
    only_qty = request.args.get('in_stock') == '1'

    query = Item.query
    if only_stocked:
        query = query.filter(Item.is_stocked == True)
    if only_qty:
        query = query.filter(Item.quantity > 0)

    if q:
        like = f'%{q}%'
        query = query.filter(or_(Item.title.ilike(like), Item.brand.ilike(like)))

    results = query.order_by(Item.title).limit(20).all()

    return jsonify([
        {
            'id': i.id,
            'title': i.title,
            'brand': i.brand or '',
            'unit': i.unit or 'EACH',
            'price': float(i.price),
            'quantity': i.quantity,
            'stocked': i.is_stocked,
        }
        for i in results
    ])


# ---------- Physical count ----------
@app.route('/count', methods=['GET', 'POST'])
@login_required
def count():
    form = CountForm()
    if form.validate_on_submit():
        item_id = request.form.get('item_id', type=int)
        if not item_id:
            flash('Please select an item from the search results.', 'danger')
            return render_template('count.html', form=form, my_counts=[])
        item = db.session.get(Item, item_id) or abort(404)
        c = InventoryCount(item_id=item.id,
                           counted_quantity=form.counted_quantity.data,
                           system_quantity=item.quantity,
                           note=form.note.data,
                           created_by=current_user.id)
        db.session.add(c)
        db.session.commit()
        flash('Count submitted for manager approval.', 'success')
        return redirect(url_for('count'))

    my_counts = (InventoryCount.query
                 .filter_by(created_by=current_user.id)
                 .order_by(InventoryCount.created_at.desc())
                 .limit(20).all())
    return render_template('count.html', form=form, my_counts=my_counts)


@app.route('/approvals')
@login_required
@manager_required
def approvals():
    pending = InventoryCount.query.filter_by(status='pending').order_by('created_at').all()
    resolved = (InventoryCount.query.filter(InventoryCount.status != 'pending')
                .order_by(InventoryCount.resolved_at.desc()).limit(30).all())
    return render_template('approvals.html', pending=pending, resolved=resolved)



@app.route('/approvals/<int:cid>/<action>', methods=['POST'])
@login_required
@manager_required
def resolve_count(cid, action):
    c = db.session.get(InventoryCount, cid) or abort(404)
    if c.status != 'pending':
        flash('Already resolved.', 'warning')
        return redirect(url_for('approvals'))

    if action == 'approve':
        item = db.session.get(Item, c.item_id)
        delta = c.counted_quantity - c.system_quantity

        # Apply the variance rather than the absolute count
        new_qty = item.quantity + delta
        if new_qty < 0:
            new_qty = 0
        item.quantity = new_qty
        if new_qty > 0:
            item.is_stocked = True

        # Record an adjustment entry so it shows in stock history
        if delta != 0:
            db.session.add(StockEntry(
                item_id=item.id,
                quantity=delta,           # can be negative for shrinkage
                unit_cost=item.cost_price or 0,
                supplier=f'Adjustment (count #{c.id})',
                created_by=current_user.id,
            ))

        c.status = 'approved'
    elif action == 'reject':
        c.status = 'rejected'
    else:
        abort(400)

    c.approved_by = current_user.id
    c.resolved_at = datetime.utcnow()
    db.session.commit()

    if action == 'approve':
        delta = c.counted_quantity - c.system_quantity
        sign = '+' if delta >= 0 else ''
        flash(f'Count approved. Adjustment: {sign}{delta} units for '
              f'{c.item.title}. New quantity: {c.item.quantity}.', 'success')
    else:
        flash('Count rejected. No changes made.', 'info')

    return redirect(url_for('approvals'))


# ---------- Sales ----------
@app.route('/sale', methods=['GET', 'POST'])
@login_required
def sale_new():
    form = SaleForm()
    items = (Item.query
             .filter(Item.is_stocked == True, Item.quantity > 0)
             .order_by('title').all())
    return render_template('sale.html', form=form, items=items,
                           cart=session.get('cart', {}))


@app.route('/sale/add', methods=['POST'])
@login_required
def sale_add():
    item_id = request.form.get('item_id', type=int)
    qty = request.form.get('quantity', type=int) or 0
    if not item_id or qty < 1:
        flash('Please pick an item and quantity.', 'warning')
        return redirect(url_for('sale_new'))

    item = db.session.get(Item, item_id) or abort(404)
    cart = session.get('cart', {})
    key = str(item_id)
    current = cart.get(key, {}).get('qty', 0)
    if current + qty > item.quantity:
        flash(f'Only {item.quantity - current} left in stock.', 'danger')
        return redirect(url_for('sale_new'))
    cart[key] = {'qty': current + qty, 'price': float(item.price),
                 'title': item.title, 'cost': float(item.cost_price or 0)}
    session['cart'] = cart
    return redirect(url_for('sale_new'))


@app.route('/sale/remove/<item_id>', methods=['POST'])
@login_required
def sale_remove(item_id):
    cart = session.get('cart', {})
    cart.pop(str(item_id), None)
    session['cart'] = cart
    return redirect(url_for('sale_new'))


@app.route('/sale/clear', methods=['POST'])
@login_required
def sale_clear():
    session['cart'] = {}
    return redirect(url_for('sale_new'))


@app.route('/sale/complete', methods=['POST'])
@login_required
def sale_complete():
    cart = session.get('cart', {})
    if not cart:
        flash('Cart is empty.', 'warning')
        return redirect(url_for('sale_new'))
    customer = request.form.get('customer_name', '').strip() or 'Walk-in'

    ref = f'S{datetime.utcnow().strftime("%Y%m%d%H%M%S")}{current_user.id}'
    s = Sale(reference=ref, customer_name=customer, cashier_id=current_user.id,
             total=0, profit=0)
    db.session.add(s)
    db.session.flush()

    total = 0
    profit = 0
    for item_id, row in cart.items():
        item = db.session.get(Item, int(item_id)) or abort(404)
        if row['qty'] > item.quantity:
            flash(f'Insufficient stock for {item.title}. Sale cancelled.', 'danger')
            db.session.rollback()
            return redirect(url_for('sale_new'))
        item.quantity -= row['qty']
        line_total = float(item.price) * row['qty']
        line_cost = float(item.cost_price or 0) * row['qty']
        total += line_total
        profit += (line_total - line_cost)
        si = SaleItem(sale_id=s.id, item_id=item.id, quantity=row['qty'],
                      unit_price=item.price, unit_cost=item.cost_price or 0)
        db.session.add(si)

    s.total = total
    s.profit = profit
    db.session.commit()
    session['cart'] = {}
    flash(f'Sale completed: {ref}', 'success')
    return redirect(url_for('receipt', sale_id=s.id))


@app.route('/receipt/<int:sale_id>')
@login_required
def receipt(sale_id):
    s = db.session.get(Sale, sale_id) or abort(404)
    return render_template('receipt.html', sale=s)


@app.route('/sales')
@login_required
@manager_required
def sales_report():
    start = request.args.get('start')
    end = request.args.get('end')
    query = Sale.query
    if start:
        query = query.filter(Sale.created_at >= datetime.fromisoformat(start))
    if end:
        query = query.filter(Sale.created_at <= datetime.fromisoformat(end + 'T23:59:59'))
    sales = query.order_by(Sale.created_at.desc()).limit(200).all()

    totals = (db.session.query(func.coalesce(func.sum(Sale.total), 0),
                               func.coalesce(func.sum(Sale.profit), 0))
              .filter(*( [Sale.created_at >= datetime.fromisoformat(start)] if start else [] ))
              .first())

    by_item = (db.session.query(Item.title,
                                func.sum(SaleItem.quantity),
                                func.sum(SaleItem.quantity * SaleItem.unit_price),
                                func.sum(SaleItem.quantity * (SaleItem.unit_price - SaleItem.unit_cost)))
               .join(SaleItem).group_by(Item.title)
               .order_by(func.sum(SaleItem.quantity).desc()).limit(20).all())

    by_category = (db.session.query(Category.name,
                                    func.sum(SaleItem.quantity),
                                    func.sum(SaleItem.quantity * SaleItem.unit_price),
                                    func.sum(SaleItem.quantity * (SaleItem.unit_price - SaleItem.unit_cost)))
                   .join(Item, Item.category_id == Category.id)
                   .join(SaleItem, SaleItem.item_id == Item.id)
                   .group_by(Category.name).all())

    return render_template('sales_report.html', sales=sales, totals=totals,
                           by_item=by_item, by_category=by_category,
                           start=start, end=end)


# ---------- Users ----------
@app.route('/users', methods=['GET', 'POST'])
@login_required
@manager_required
def users():
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter((User.username == form.username.data) |
                             (User.email == form.email.data)).first():
            flash('Username or email already exists.', 'danger')
        else:
            u = User(
                username=form.username.data,
                email=form.email.data,
                role=form.role.data,
                is_approved=True,
                approved_by=current_user.id,
                approved_at=datetime.utcnow(),
                active=True,
            )
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            flash(f'User {u.username} created and approved.', 'success')
            return redirect(url_for('users'))

    all_users = User.query.order_by(User.created_at.desc()).all()
    pending_users  = [u for u in all_users if not u.is_approved]
    approved_users = [u for u in all_users if u.is_approved]

    return render_template('users.html', form=form,
                           users=approved_users, pending_users=pending_users)


@app.route('/users/<int:uid>/approve', methods=['POST'])
@login_required
@manager_required
def user_approve(uid):
    u = db.session.get(User, uid) or abort(404)
    if u.is_approved:
        flash('User already approved.', 'warning')
    else:
        u.is_approved = True
        u.approved_by = current_user.id
        u.approved_at = datetime.utcnow()
        db.session.commit()
        flash(f'Approved {u.username}.', 'success')
    return redirect(url_for('users'))


@app.route('/users/<int:uid>/reject', methods=['POST'])
@login_required
@manager_required
def user_reject(uid):
    u = db.session.get(User, uid) or abort(404)
    if u.id == current_user.id:
        flash("You can't reject yourself.", 'warning')
        return redirect(url_for('users'))
    db.session.delete(u)
    db.session.commit()
    flash(f'Rejected and removed {u.username}.', 'success')
    return redirect(url_for('users'))


@app.route('/users/<int:uid>/toggle', methods=['POST'])
@login_required
@manager_required
def user_toggle(uid):
    u = db.session.get(User, uid) or abort(404)
    if u.id == current_user.id:
        flash("You can't deactivate yourself.", 'warning')
    else:
        u.active = not u.active
        db.session.commit()
    return redirect(url_for('users'))


# ---------- Quotations ----------
@app.route('/quotations')
@login_required
def quotations():
    quotes = Quotation.query.order_by(Quotation.created_at.desc()).all()
    return render_template('quotation.html', quotes=quotes, mode='list')


@app.route('/quotations/new', methods=['GET', 'POST'])
@login_required
def quotation_new():
    form = QuotationForm()
    if form.validate_on_submit():
        ref = f'Q{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
        q = Quotation(reference=ref, customer_name=form.customer_name.data,
                      customer_contact=form.customer_contact.data,
                      created_by=current_user.id)
        if form.valid_until.data:
            q.valid_until = datetime.combine(form.valid_until.data, datetime.min.time())
        db.session.add(q)
        db.session.commit()
        return redirect(url_for('quotation_edit', qid=q.id))
    return render_template('quotation.html', form=form, mode='new')


@app.route('/quotations/<int:qid>', methods=['GET', 'POST'])
@login_required
def quotation_edit(qid):
    q = db.session.get(Quotation, qid) or abort(404)
    if request.method == 'POST':
        if 'add_line' in request.form:
            item_id = request.form.get('item_id', type=int)
            qty = request.form.get('quantity', type=int) or 1
            if item_id:
                item = db.session.get(Item, item_id) or abort(404)
                qi = QuotationItem(quotation_id=q.id, item_id=item.id,
                                   quantity=qty, unit_price=item.price)
                db.session.add(qi)
                db.session.flush()
                q.total = sum(float(x.unit_price) * x.quantity for x in q.items)
                db.session.commit()
        elif 'remove_line' in request.form:
            qi = db.session.get(QuotationItem, int(request.form['line_id']))
            if qi and qi.quotation_id == q.id:
                db.session.delete(qi)
                db.session.commit()
                q.total = sum(float(x.unit_price) * x.quantity for x in q.items)
                db.session.commit()
        elif 'convert' in request.form:
            cart = {str(li.item_id): {'qty': li.quantity,
                                      'price': float(li.unit_price),
                                      'title': li.item.title,
                                      'cost': float(li.item.cost_price or 0)}
                    for li in q.items}
            session['cart'] = cart
            return redirect(url_for('sale_new'))
        return redirect(url_for('quotation_edit', qid=q.id))

    items = Item.query.filter(Item.is_catalogued == True).order_by('title').all()
    return render_template('quotation.html', q=q, items=items, mode='edit')


# ---------- Error handlers ----------
@app.errorhandler(403)
def forbidden(e):
    return render_template('base.html', error='403 Forbidden — manager access required'), 403


@app.errorhandler(404)
def notfound(e):
    return render_template('base.html', error='404 Not Found'), 404

from flask import make_response

@app.route('/catalogue.pdf')
@login_required
def catalogue_pdf():
    # Optional filters — mirror the /catalogue page
    q = request.args.get('q', '').strip()
    cat_id = request.args.get('category', type=int)

    query = Item.query.filter(Item.is_catalogued == True)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Item.title.ilike(like), Item.brand.ilike(like)))
    if cat_id:
        query = query.filter(Item.category_id == cat_id)

    items = query.order_by(Item.category_id, Item.title).all()

    # Group by category for the PDF
    grouped = {}
    for it in items:
        cat_name = it.category.name if it.category else 'UNCATEGORISED'
        grouped.setdefault(cat_name, []).append(it)

    html = render_template(
        'catalogue_pdf.html',
        grouped=grouped,
        generated_at=datetime.utcnow(),
        q=q,
        cat_id=cat_id,
    )

    pdf = weasyprint.HTML(string=html, base_url=request.url_root).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    fname = f'ZABACH-price-list-{datetime.utcnow().strftime("%Y%m%d")}.pdf'
    response.headers['Content-Disposition'] = f'inline; filename="{fname}"'
    return response

@app.route('/items/price-bulk', methods=['GET', 'POST'])
@login_required
@manager_required
def items_price_bulk():
    if request.method == 'POST':
        import csv, io
        file = request.files.get('file')
        if not file or not file.filename.lower().endswith('.csv'):
            flash('Please choose a .csv file.', 'warning')
            return redirect(url_for('items_price_bulk'))

        stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
        reader = csv.DictReader(stream)

        headers = {(h or '').strip().lower() for h in (reader.fieldnames or [])}
        if not {'title', 'new_price'}.issubset(headers):
            flash('CSV must have "title" and "new_price" columns.', 'danger')
            return redirect(url_for('items_price_bulk'))

        updated = 0
        skipped = 0
        changes = []

        for raw in reader:
            row = {(k or '').strip().lower(): (v.strip() if isinstance(v, str) else v)
                   for k, v in raw.items()}
            title = row.get('title', '')
            try:
                new_price = float(row.get('new_price') or 0)
            except ValueError:
                skipped += 1
                continue
            if not title or new_price <= 0:
                skipped += 1
                continue

            q = Item.query.filter(func.upper(Item.title) == title.upper())
            cat_name = (row.get('category') or '').strip()
            if cat_name:
                q = q.join(Category).filter(func.upper(Category.name) == cat_name.upper())

            item = q.first()
            if not item:
                skipped += 1
                continue

            if float(item.price) != new_price:
                db.session.add(PriceChange(
                    item_id=item.id,
                    old_price=item.price,
                    new_price=new_price,
                    changed_by=current_user.id,
                ))
                changes.append((item.title, float(item.price), new_price))
                item.price = new_price
                updated += 1

        db.session.commit()
        flash(f'Price update done — updated: {updated}, skipped: {skipped}.', 'success')
        for t, old, new in changes[:10]:
            flash(f'{t}: {old:.2f} → {new:.2f}', 'info')
        return redirect(url_for('catalogue'))

    # GET — show the upload form
    sample = 'title,category,new_price\nBEAKER 100ML,LABORATORY,450\n'
    return render_template('items_bulk.html', sample=sample)


if __name__ == '__main__':
    app.run(debug=True)