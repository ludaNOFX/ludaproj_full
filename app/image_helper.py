import os
from app import db
from PIL import Image
from flask import current_app
from wtforms.validators import ValidationError
import secrets
from app.models import Picture, User, Product, PictureFormat


class FileSize(object):
    def __init__(self, max_size):
        self.max_size = max_size

    def __call__(self, form, field):
        file = field.data
        if file is not None:
            if file.filename == "":
                raise ValidationError('File must be selected')
            if len(file.read()) > self.max_size:
                raise ValidationError('File size exceeds limit')


def save_picture(form_picture, record, category='product', sizes=((300, 300), (500, 500))):
    random_hex = secrets.token_hex(8)
    _, file_extension = os.path.splitext(form_picture.filename)
    picture = Picture(user=record if isinstance(record, User) else None,
                      product=record if isinstance(record, Product) else None)
    db.session.add(picture)
    db.session.commit()
    for size in sizes:
        picture_filename = f"{random_hex}_{size[0]}x{size[1]}{file_extension}"
        picture_path = os.path.join(current_app.root_path, 'static', category + '_pics', picture_filename)

        i = Image.open(form_picture)
        i.thumbnail(size)
        i.save(picture_path)

        picture_format = PictureFormat(filename=picture_filename, format=f"{size[0]}x{size[1]}",
                                       picture_id=picture.id)
        db.session.add(picture_format)

    db.session.commit()

    return picture


