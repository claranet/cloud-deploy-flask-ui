from flask_wtf import FlaskForm

from wtforms import HiddenField, RadioField, SubmitField
from wtforms.validators import DataRequired as DataRequiredValidator


class DeleteJobForm(FlaskForm):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()],
                              choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Delete Job')


class CancelJobForm(FlaskForm):
    etag = HiddenField(validators=[DataRequiredValidator()])
    confirmation = RadioField('Are you sure?', validators=[DataRequiredValidator()],
                              choices=[('yes', 'Yes'), ('no', 'No')])

    submit = SubmitField('Cancel Job')
