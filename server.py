from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash

#from flask.ext.login import *
from flask_login import * # Same as above, but I get autocomplete!

from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property, Comparator, hybrid_method
from sqlalchemy import func
from contextlib import closing
import sys
from datetime import datetime

from collections import namedtuple
from forms import *
import os
from functools import wraps

#DATABASE = 'C:/temp/prequest.db'
DEBUG = True
SECRET_KEY = '7hfdbrt354dsfhddr<f9342nbds034qwnxck-=9833445.;":&&^psdarwer'
ADMINS = ['admin']
SQLALCHEMY_DATABASE_URI = os.environ.get('HEROKU_POSTGRESQL_GREEN_URL', 'postgresql://postgres:pptp@127.0.0.1')
app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

db = SQLAlchemy(app)

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
            

class CIC(Comparator):
    def __eq__(self, other):
        return func.lower(self.__clause_element__()) ==  func.lower(other)

class DBCategory(db.Model):
    __tablename__='categories'
    def __init__(self, name):
        self.name = name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    items = db.relationship('DBEquipment', backref='category', lazy='select')
    
    @hybrid_property
    def lowername(self):
        return self.name.lower()
    
    @lowername.comparator
    def lowername(cls):
        return CIC(cls.name)
    
    def __repr__(self):
        return "Category: %s" % self.name

class DBEquipment(db.Model):
    __tablename__='equipment'
    def __init__(self, tagno, category_id, model=""):
        self.tagno = tagno
        self.category_id = category_id
        self.model = model
    def __repr__(self):
        return "USAID Tag: %s" % self.tagno
    id = db.Column(db.Integer, primary_key=True)
    tagno = db.Column(db.Integer)
    model = db.Column(db.String)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))

class DBUser(db.Model):
    __tablename__ = 'users'
    def __init__(self, username, password):
        self.username = username
        self.password = password
    def __repr__(self):
        return self.username
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True)
    password = db.Column(db.String)

class DBEvent(db.Model):
    __tablename__ = 'events'
    def __init__(self, name, user):
        self.name = name
        self.creator_id = user.id
    def add_requirement(self, category, quantity):
        pass
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    description = db.Column(db.String)
    start_date = db.Column(db.DateTime, default=func.now())
    end_date = db.Column(db.DateTime, default=func.now())
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    creator = db.relationship('DBUser', backref='events', lazy='select')

class DBRequirement(db.Model):
    __tablename__ = 'requirements'
    def __init__(self):
        pass
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=1)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    category = db.relationship('DBCategory')
    event = db.relationship('DBEvent', backref='requirements', lazy='select')

#class DBBooking(db.Model):
#    __tablename__ = 'bookings'
#    id = db.Column(db.Integer, primary_key=True)


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

@app.before_request
def before_request():
    #g.db = connect_db()
    pass

@app.teardown_request
def teardown_request(exception):
    #g.db.close()
    pass

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

if __name__ == '__main__':
    # Run server if there are no arguments
    if (len(sys.argv) == 1):
        initdb()
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
