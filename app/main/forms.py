from flask_wtf import FlaskForm
from flask import request
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, TextAreaField, \
    DecimalField
from wtforms.validators import ValidationError, DataRequired, Length
from app.models import User, Product
from app.image_helper import FileSize


class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    about_me = TextAreaField('About me', validators=[Length(min=0, max=140)])
    picture = FileField('Upload Profile Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png']),
                                                              FileSize(max_size=1024 * 1024)])
    submit = SubmitField('Submit')

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError('Please use a different username.')


class EditProductForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    price = DecimalField('Price', validators=[DataRequired()])
    description = TextAreaField('Say something', validators=[Length(max=140)])
    picture = FileField('Upload Product Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png']),
                                                              FileSize(max_size=1024 * 1024)])
    submit = SubmitField('Submit')

    def __init__(self, original_name, *args, **kwargs):
        super(EditProductForm, self).__init__(*args, **kwargs)
        self.original_name = original_name


class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')


class ProductForm(FlaskForm):
    name = StringField('Product name', validators=[DataRequired()])
    picture = FileField('Upload Product Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png']),
                                                              FileSize(max_size=1024 * 1024)])
    description = TextAreaField('Say something', validators=[Length(max=140)])
    price = DecimalField('Price', validators=[DataRequired()])
    submit = SubmitField('Submit')


class SearchForm(FlaskForm):
    q = StringField('Search', validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'meta' not in kwargs:
            kwargs['meta'] = {'csrf': False}
        super(SearchForm, self).__init__(*args, **kwargs)
