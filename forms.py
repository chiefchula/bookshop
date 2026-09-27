from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, IntegerField, DecimalField,
                     SelectField, SubmitField, TextAreaField, DateField)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, EqualTo


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm Password',
                            validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')


class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm Password',
                            validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('user', 'User'), ('manager', 'Manager')])
    submit = SubmitField('Create User')


class ItemForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(1, 200)])
    author = StringField('Author', validators=[Optional(), Length(max=150)])
    isbn = StringField('ISBN', validators=[Optional(), Length(max=20)])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    cost_price = DecimalField('Cost Price', validators=[Optional(), NumberRange(min=0)])
    price = DecimalField('Selling Price', validators=[DataRequired(), NumberRange(min=0)])
    quantity = IntegerField('Opening Quantity', validators=[Optional(), NumberRange(min=0)])
    reorder_level = IntegerField('Reorder Level', validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Save')


class PriceChangeForm(FlaskForm):
    new_price = DecimalField('New Price', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Update Price')


# NOTE: item_id is NOT a form field — it comes via request.form['item_id']
# from the hidden input in the template. This avoids duplicate field bugs.
class StockEntryForm(FlaskForm):
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1)])
    unit_cost = DecimalField('Unit Cost', validators=[DataRequired(), NumberRange(min=0)])
    supplier = StringField('Supplier', validators=[Optional(), Length(max=150)])
    submit = SubmitField('Add Stock')


# NOTE: item_id is NOT a form field — comes via request.form['item_id']
class CountForm(FlaskForm):
    counted_quantity = IntegerField('Counted Quantity',
                                    validators=[DataRequired(), NumberRange(min=0)])
    note = TextAreaField('Note', validators=[Optional()])
    submit = SubmitField('Submit for Approval')


class SaleForm(FlaskForm):
    customer_name = StringField('Customer Name', validators=[Optional(), Length(max=150)])
    submit = SubmitField('Complete Sale')


class QuotationForm(FlaskForm):
    customer_name = StringField('Customer Name', validators=[DataRequired(), Length(max=150)])
    customer_contact = StringField('Contact', validators=[Optional(), Length(max=150)])
    valid_until = DateField('Valid Until', validators=[Optional()])
    submit = SubmitField('Create Quotation')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm New Password',
                            validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')