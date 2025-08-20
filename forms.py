from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from models import User

class RegistrationForm(FlaskForm):
    username = StringField('Username', 
        validators=[
            DataRequired(), 
            Length(min=3, max=50, 
            message='Username must be between 3 and 50 characters')
        ])
    email = StringField('Email', 
        validators=[
            DataRequired(), 
            Email(message='Invalid email address')
        ])
    password = PasswordField('Password', 
        validators=[
            DataRequired(), 
            Length(min=8, message='Password must be at least 8 characters')
        ])
    confirm_password = PasswordField('Confirm Password', 
        validators=[
            DataRequired(), 
            EqualTo('password', message='Passwords must match')
        ])
    profile_picture = FileField('Profile Picture', 
        validators=[
            FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
        ])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email.')

class LoginForm(FlaskForm):
    email = StringField('Email', 
        validators=[
            DataRequired(), 
            Email(message='Invalid email address')
        ])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class BlynkDeviceForm(FlaskForm):
    device_name = StringField('Device Name', validators=[DataRequired(), Length(min=3, max=100)])
    auth_token = StringField('Blynk Authentication Token', validators=[DataRequired(), Length(min=10, max=100)])
    virtual_pin_voltage = StringField('Voltage Pin', default='V0')
    virtual_pin_current = StringField('Current Pin', default='V1')
    virtual_pin_power = StringField('Power Pin', default='V2')
    virtual_pin_energy = StringField('Energy Pin', default='V3')
    submit = SubmitField('Register Device')
