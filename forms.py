from wtforms import Form, BooleanField, TextField, SelectField, PasswordField, validators

class AddEquipmentForm(Form):
    tagno = TextField('USAID Tag', [validators.required(), validators.number_range(10000,99999)])
    category = SelectField('Category', validators=[validators.required()])
    model = TextField('Model', [validators.optional()])

class AddCategoryForm(Form):
    catname = TextField('Category Name', [validators.required()])