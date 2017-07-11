from flask_wtf import Form

from wtforms import HiddenField, RadioField, SubmitField
from wtforms.validators import DataRequired as DataRequiredValidator


class DeleteJobForm(Form):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()],
                              choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Job')


class CancelJobForm(Form):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()],
                              choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Cancel Job')
