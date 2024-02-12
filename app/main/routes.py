import os
from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, current_app, \
    g
from flask_login import current_user, login_required
from app import db
from app.main.forms import EditProfileForm, EmptyForm, ProductForm, EditProductForm, \
    SearchForm
from app.models import User, Product, Picture, PictureFormat
from app.image_helper import save_picture
from app.main import bp


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        g.search_form = SearchForm()


@bp.route('/')
@bp.route('/index')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    products = Product.query.order_by(Product.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.index', page=products.next_num) \
        if products.has_next else None
    prev_url = url_for('main.index', page=products.prev_num) \
        if products.has_prev else None
    return render_template('index.html', title='Home', products=products.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/art_flow')
@login_required
def art_flow():
    page = request.args.get('page', 1, type=int)
    products = current_user.followed_product().paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.art_flow', page=products.next_num) \
        if products.has_next else None
    prev_url = url_for('main.art_flow', page=products.prev_num) \
        if products.has_prev else None
    return render_template("index.html", title='Art Flow', products=products.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    products = user.products.order_by(Product.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.user', username=user.username, page=products.next_num) \
        if products.has_next else None
    prev_url = url_for('main.user', username=user.username, page=products.prev_num) \
        if products.has_prev else None
    form = EmptyForm()
    return render_template('user.html', user=user, form=form, products=products.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/product/<name>')
@login_required
def product(name):
    product = Product.query.filter_by(name=name).first_or_404()
    form = EmptyForm()
    return render_template('product.html', product=product, form=form)


@bp.route('/edit_product/<name>', methods=['GET', 'POST'])
@login_required
def edit_product(name):
    product = Product.query.filter_by(name=name).first()
    form = EditProductForm(product.name)
    if form.validate_on_submit():
        product.name = form.name.data
        product.price = form.price.data
        product.description = form.description.data
        if form.picture.data:
            last_picture = Picture.query.filter_by(product_id=product.id).order_by(Picture.id.desc()).first()
            if last_picture:
                last_formats = PictureFormat.query.filter_by(picture_id=last_picture.id).all()
                files_to_remove = [os.path.join(current_app.root_path, 'static/product_pics', pic_format.filename) for
                                   pic_format in last_formats]
                for pic_format in last_formats:
                    db.session.delete(pic_format)
                db.session.delete(last_picture)
                for file_path in files_to_remove:
                    os.remove(file_path)
            save_picture(form.picture.data, record=product)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.product', name=product.name))
    elif request.method == 'GET':
        form.name.data = product.name
        form.price.data = product.price
        form.description.data = product.description
    return render_template('edit_product.html', title='Edit Product',
                           form=form)


@bp.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(name=form.name.data, price=form.price.data,
                          author=current_user)
        db.session.add(product)
        if form.picture.data:
            save_picture(form.picture.data, record=product)
        if form.description.data:
            product.description = form.description.data
        db.session.commit()
        flash('Your product is now live!')
        return redirect(url_for('main.product', name=product.name))
    return render_template("add_product.html", title='Add Product', form=form)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        if form.picture.data:
            last_picture = Picture.query.filter_by(user_id=current_user.id).order_by(Picture.id.desc()).first()
            if last_picture:
                last_formats = PictureFormat.query.filter_by(picture_id=last_picture.id).all()
                files_to_remove = [os.path.join(current_app.root_path, 'static/profile_pics', pic_format.filename) for
                                   pic_format in last_formats]
                for pic_format in last_formats:
                    db.session.delete(pic_format)
                db.session.delete(last_picture)
                for file_path in files_to_remove:
                    os.remove(file_path)
            save_picture(form.picture.data, record=current_user, category='profile',
                         sizes=((50, 50), (450, 450)))
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/add_to_cart/<product_name>', methods=['POST'])
@login_required
def add_to_cart(product_name):
    form = EmptyForm()
    if form.validate_on_submit():
        product = Product.query.filter_by(name=product_name).first()
        if product is None:
            flash(f'Product {product_name} not found.')
            return redirect(url_for('main.index'))
        if product.user_id == current_user.id:
            flash('You cannot add your own product')
            return redirect(url_for('main.product', name=product_name))
        product.add_to_cart(current_user)
        db.session.commit()
        flash(f'You added product {product_name}.')
        return redirect(url_for('main.product', name=product_name))
    else:
        return redirect(url_for('main.index'))


@bp.route('/remove_from_cart/<product_name>', methods=['POST'])
@login_required
def remove_from_cart(product_name):
    form = EmptyForm()
    if form.validate_on_submit():
        product = Product.query.filter_by(name=product_name).first()
        if product is None:
            flash(f'Product {product_name} not found.')
            return redirect(url_for('main.index'))
        if product.user_id == current_user.id:
            flash('You cannot remove your own product from the cart')
            return redirect(url_for('main.product', name=product_name))
        product.remove_from_cart(current_user)
        db.session.commit()
        flash(f'You removed product {product_name}.')
        return redirect(url_for('main.product', name=product_name))
    else:
        return redirect(url_for('main.index'))

@bp.route('/cart')
@login_required
def cart():
    page = request.args.get('page', 1, type=int)
    products = current_user.added_products.order_by(Product.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.cart', page=products.next_num) \
        if products.has_next else None
    prev_url = url_for('main.cart', page=products.prev_num) \
        if products.has_prev else None
    form = EmptyForm()
    return render_template('index.html', form=form, products=products.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/purchase/<product_name>', methods=['POST'])
@login_required
def purchase(product_name):
    form = EmptyForm()
    if form.validate_on_submit():
        product = Product.query.filter_by(name=product_name).first()
        if product is None:
            flash(f'Product {product_name} not found.')
            return redirect(url_for('main.index'))
        if product.user_id == current_user.id:
            flash('You cannot buy your own product')
            return redirect(url_for('main.product', name=product_name))
        buy = product.purchase()
        if buy:
            db.session.commit()
            flash(f'you purchased the product {product_name}.')
            return redirect(url_for('main.product', name=product_name))
        else:
            flash('You have already purchased this product')
    else:
        return redirect(url_for('main.index'))


@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type=int)
    products, total = Product.search(g.search_form.q.data, page,
                               current_app.config['POSTS_PER_PAGE'])
    next_url = url_for('main.search', q=g.search_form.q.data, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('main.search', q=g.search_form.q.data, page=page - 1) \
        if page > 1 else None
    return render_template('search.html', title='Search', products=products,
                           next_url=next_url, prev_url=prev_url)



