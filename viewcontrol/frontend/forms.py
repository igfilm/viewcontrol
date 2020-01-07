from flask import request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import ValidationError, DataRequired, Length

class AddShow(FlaskForm):
    showname = StringField('Showname', validators=[DataRequired()])
    submit = SubmitField('Neue Show erstellen')
