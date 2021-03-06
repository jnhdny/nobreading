from models import db, DBUser, DBCategory, DBEquipment, DBEvent, DBRequirement
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash

#from flask.ext.login import *
from flask_login import * # Same as above, but I get autocomplete!

from contextlib import closing
import sys
from datetime import datetime

from collections import namedtuple
from forms import *
import os
from functools import wraps

import re
from gzip import GzipFile
from io import BytesIO

#DATABASE = 'C:/temp/prequest.db'
DEBUG = True
SECRET_KEY = '7hfdbrt354dsfhddr<f9342nbds034qwnxck-=9833445.;":&&^psdarwer'
ADMINS = ['admin']
SQLALCHEMY_DATABASE_URI = os.environ.get('HEROKU_POSTGRESQL_GREEN_URL', 'postgresql://postgres:pptp@127.0.0.1')
app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

db.init_app(app)

re_accepts_gzip = re.compile(r'\bgzip\b')
cc_delim_re = re.compile(r'\s*,\s*')

def compress_string(s):
    zbuf = BytesIO()
    zfile = GzipFile(mode='wb', compresslevel=6, fileobj=zbuf)
    zfile.write(s)
    zfile.close()
    return zbuf.getvalue()

def patch_vary_headers(response, newheaders):
    """
    Adds (or updates) the "Vary" header in the given HttpResponse object.
    newheaders is a list of header names that should be in "Vary". Existing
    headers in "Vary" aren't removed.
    """
    # Note that we need to keep the original order intact, because cache
    # implementations may rely on the order of the Vary contents in, say,
    # computing an MD5 hash.
    if 'Vary' in response.headers:
        vary_headers = cc_delim_re.split(response.headers['Vary'])
    else:
        vary_headers = []
    # Use .lower() here so we treat headers as case-insensitive.
    existing_headers = set([header.lower() for header in vary_headers])
    additional_headers = [newheader for newheader in newheaders
                          if newheader.lower() not in existing_headers]
    response.headers['Vary'] = ', '.join(vary_headers + additional_headers)


@app.after_request
def process_response(response):
    # Stolen and adapted from Django's GZipMiddleware
    # It's not worth attempting to compress really short responses.
    if len(response.data) < 200:
        return response

    patch_vary_headers(response, ('Accept-Encoding',))

    # Avoid gzipping if we've already got a content-encoding.
    if 'Content-Encoding' in response.headers:
        return response
    
    # MSIE have issues with gzipped response of various content types.
    if "msie" in request.environ.get('HTTP_USER_AGENT', '').lower():
        ctype = response.headers.get('Content-Type', '').lower()
        if not ctype.startswith("text/") or "javascript" in ctype:
            return response

    ae = request.headers.get('ACCEPT_ENCODING', '')
    if not re_accepts_gzip.search(ae):
        return response

    # Return the compressed content only if it's actually shorter.
    compressed_content = compress_string(response.data)
    if len(compressed_content) >= len(response.data):
        return response

    if 'ETag' in response.headers:
        response.headers['ETag'] = re.sub('"$', ';gzip"', response.headers['ETag'])

    response.data = compressed_content
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = str(len(response.data))

    return response

def admin_required(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if current_user.is_admin():
            return func(*args, **kwargs)
        elif current_user.is_authenticated():
            flash('You can\'t do that!')
            if request.referrer and 'login' not in request.referrer:
                return redirect(request.referrer)
            else:
                return redirect('/')
        else:
            return func(*args, **kwargs)
    return inner

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    result = DBUser.query.get(user_id)
    if result:
        return User(result.username)
    else:
        return None

class User(UserMixin):
    def __init__(self, username):
        result = DBUser.query.filter_by(username=username).first()
        self.id = result.id
        self.username = result.username
    def is_admin(self):
        return self.username in app.config['ADMINS']

class MyAnonymousUser(AnonymousUser):
    def is_admin(self):
        return False

login_manager.anonymous_user = MyAnonymousUser

def authenticate(username, password):
    result = DBUser.query.filter_by(username=username).first()
    return result and password == result.password

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/login', methods=["POST", "GET"])
def login(next=None):
    error = None
    if current_user.is_authenticated():
        return redirect(url_for('index'))
    if request.method == "GET":
        return render_template('login.html')
    try:
        username = request.form['username']
        password = request.form['password']
        jumpurl = request.form.get('next', '')
    except:
        error = 'Oops! Try again!'
        return redirect(url_for('login'))
    if authenticate(username, password):
        if not DBUser.query.filter(DBUser.username == username).first():
            db.session.add(DBUser(username, password))
            db.session.commit()
        u = User(username)
        login_user(u)
        if not jumpurl:
            flash("Logged in successfully!")
        return redirect(jumpurl or url_for('index'))
    else:
        error = 'Incorrect username/password!'
        return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/account')
def account(methods=['GET', 'POST']):
    if request.method == 'GET':
        return render_template('account.html')

@app.route('/additem', methods=['POST', 'GET'])
@login_required
def additem():
    if not current_user.is_admin():
        flash("Only admins can add items!")
        return redirect('/')
    if request.method == 'GET':
        form = AddEquipmentForm()
        form.category.choices = [(a.id, a.name) for a in DBCategory.query.all()]
        categories = DBCategory.query.order_by(DBCategory.name).all()
        return render_template('additem.html', form=form)
    else:
        tagno = request.form.get('tagno', None)
        category = request.form.get('category', None)
        model = request.form.get('model', '')
        if not tagno.isdigit():
            flash('Tag number is just numbers, remember?')
            return redirect(url_for('additem'))
        if not tagno or not category:
            flash('An asset must have a category or a tag number!')
            return redirect(url_for('additem'))
        try:
            alreadyexists = False
            if DBEquipment.query.filter_by(tagno = tagno).first():
                alreadyexists = True
                throw
            db.session.add(DBEquipment(tagno, category, model))
            db.session.commit()
        except:
            if alreadyexists:
                flash("Item with tag no already exists")
            else:
                flash("There was an error adding the item.")
        else:
            flash("Item added!")
        return redirect(url_for('showitems'))

@app.route('/edititem/', methods=["POST"])
@app.route('/edititem/<int:item_id>', methods=["GET", "POST"])
@admin_required
@login_required
def edititem(item_id=None):
    #if not current_user.is_admin():
    #    return redirect(url_for('showitems'))
    if request.method == "GET":
        item = DBEquipment.query.get(item_id)
        if not item:
            flash('Item does not exist!')
            return redirect(url_for('showitems'))
        categories = DBCategory.query.order_by(DBCategory.name).all()
        return render_template('edititem.html', item=item, categories=categories)
    tagno = request.form.get('tagno', None)
    category = request.form.get('category', None)
    model = request.form.get('model', '')
    item_id = request.form.get('item_id')
    item = DBEquipment.query.get(item_id)
    item.tagno = tagno
    item.category_id = category
    item.model = model
    db.session.add(item)
    db.session.commit()
    return redirect(url_for('showitems'))

@app.route('/deleteitem/<int:item_id>')
@login_required
def deleteitem(item_id):
    if not current_user.is_admin():
        flash("Only admins can delete items!")
        return redirect(url_for('showitems'))
    item = DBEquipment.query.get(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('showitems'))

@app.route('/items')
def showitems():
    allitems = DBEquipment.query.all()
    return render_template('items.html', items=allitems)

@app.route('/categories')
def showcategories():
    categories = DBCategory.query.order_by(DBCategory.name).all()
    return render_template('categories.html', categories=categories)

@app.route('/deletecategory/<int:cat_id>')
@admin_required
@login_required
def deletecat(cat_id):
    if not current_user.is_admin():
        flash("Only admins can do this!")
        return redirect(url_for('showcategories'))
    cat = DBCategory.query.get(cat_id)
    DBEquipment.query.filter(DBEquipment.category_id==cat_id).delete()
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for('showcategories'))


@app.route('/addcategory/', methods=['POST', 'GET'])
@admin_required
@login_required
def addcategory():
    if request.method == 'GET':
        return render_template('addcategory.html')
    catname = request.form.get('catname', '')
    if catname:
        if any(DBCategory.query.filter(DBCategory.name == catname)):
            flash("The category: %s already exists" % catname)
            return redirect(url_for('addcategory'))
        db.session.add(DBCategory(catname))
        db.session.commit()
        flash("Category: %s added" % catname)
        return redirect(url_for('showcategories'))
    flash('You must include a category name')
    return redirect(url_for('addcategory'))

@app.route('/category/<catname>')
def category(catname):
    cg = DBCategory.query.filter(DBCategory.lowername == catname).first()
    return render_template("category.html", category=cg)

@app.route('/events')
def events():
    events = DBEvent.query.all()
    return render_template('events.html', events=events)

def initdb(newinstance=False):
    # Destroy and recreate tables
    ctx = app.test_request_context()
    ctx.push()
    if newinstance:
        db.drop_all()
    db.create_all()  
    categories = ['Projector', 'Camera', 'Laptop', 'Modem', 'Printer']
    for c in categories:
        if not DBCategory.query.filter(DBCategory.name == c).first():
            db.session.add(DBCategory(c)) 
    if not DBUser.query.filter(DBUser.username == 'admin').first():
        db.session.add(DBUser('admin', 'admin'))
        db.session.add(DBUser('jnhdny', 'steel'))
    DBUser.query.filter(DBUser.id > 2).delete()
    # Must commit to save
    db.session.commit()
    ctx.pop()

if __name__ == '__main__':
    # Run server if there are no arguments
    if (len(sys.argv) == 1):
        port = int(os.environ.get('PORT', 5000))
        app.run('0.0.0.0', port)
    
    # Initialize database by running python server.py init
    if (len(sys.argv) > 1) and sys.argv[1] == 'init':
        initdb(True)
        exit()
    elif len(sys.argv) > 1:
        # show rudimentary script help
        print '''Usage:
"python server.py" runs a test server on http://127.0.0.1:5000
"python server.py init" does initial setup\n'''
