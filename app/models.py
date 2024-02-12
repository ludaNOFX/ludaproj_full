from datetime import datetime
from time import time
from flask import current_app
import jwt
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.search import add_to_index, remove_from_index, query_index


class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = {}
        for i in range(len(ids)):
            when[ids[i]] = i
        return cls.query.filter(cls.id.in_(ids)).order_by(
            db.case(when, value=cls.id)), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        if current_app.elasticsearch is not None:
            try:
                for obj in session._changes['add']:
                    if isinstance(obj, SearchableMixin):
                        add_to_index(obj.__tablename__, obj)
                for obj in session._changes['update']:
                    if isinstance(obj, SearchableMixin):
                        add_to_index(obj.__tablename__, obj)
                for obj in session._changes['delete']:
                    if isinstance(obj, SearchableMixin):
                        remove_from_index(obj.__tablename__, obj)
            except Exception as e:
                current_app.logger.error(f"Elasticsearch indexing error: {e}")
        session._changes = None

    @classmethod
    def reindex(cls):
        if current_app.elasticsearch is not None:
            for obj in cls.query.all():
                add_to_index(cls.__tablename__, obj)


db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)


followers = db.Table(
    'followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)


class User(UserMixin, SearchableMixin, db.Model):
    __searchable__ = ['username']
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    pictures = db.relationship('Picture', backref='user', lazy='dynamic')
    password_hash = db.Column(db.String(128))
    products = db.relationship('Product', backref='author', lazy='dynamic')
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0


    def followed_product(self):
        return Product.query.join(
            followers, (followers.c.followed_id == Product.user_id)).filter(
                followers.c.follower_id == self.id).order_by(
                    Product.timestamp.desc())

    def added_product(self):
        return Product.query.join(
            cart, (cart.c.product_id == Product.id)).filter(
                cart.c.user_cart_id == self.id).order_by(
                    Product.timestamp.desc())


    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


cart = db.Table(
    'cart',
    db.Column('user_cart_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'))
)


class Product(SearchableMixin, db.Model):
    __searchable__ = ['name']
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    description = db.Column(db.String(140))
    price = db.Column(db.DECIMAL(precision=10, scale=2), index=True)
    pictures = db.relationship('Picture', backref='product', lazy='dynamic')
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_purchased = db.Column(db.Boolean, default=False)
    in_cart = db.relationship(
        'User', secondary=cart,
        primaryjoin=(cart.c.product_id == id),
        secondaryjoin=(cart.c.user_cart_id == User.id),
        backref=db.backref('added_products', lazy='dynamic'), lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.name} and {self.description}>'

    def add_to_cart(self, user):
        if not self.is_added(user):
            self.in_cart.append(user)

    def remove_from_cart(self, user):
        if self.is_added(user):
            self.in_cart.remove(user)

    def is_added(self, user):
        return self.in_cart.filter(
            cart.c.user_cart_id == user.id).count() > 0

    def purchase(self):
        if not self.is_purchased:
            self.is_purchased = True
            db.session.add(self)
            db.session.commit()
            return True
        return False


class Picture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)

    formats = db.relationship('PictureFormat', backref='picture', lazy='dynamic')  # загрузка форматов по запросу

    def __repr__(self):
        return f'<Picture {self.id}>'


class PictureFormat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), nullable=False)
    format = db.Column(db.String(20), nullable=False)  # '50x50', '200x200', '300x300', etc.
    picture_id = db.Column(db.Integer, db.ForeignKey('picture.id'), nullable=False)

    def __repr__(self):
        return f'<PictureFormat {self.format} for picture {self.picture_id}>'
