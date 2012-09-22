from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property, Comparator, hybrid_method
from sqlalchemy import func

from server import app

db = SQLAlchemy(app)

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
