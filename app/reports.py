"""Shared report-filing form.

Lives here (not in the admin blueprint) because it's used by the memories
blueprint (report a memory or comment) and the profiles blueprint (report
a user), and none of those should depend on the admin blueprint just to
render a form. The admin review queue itself lives in
app/blueprints/admin/routes.py.
"""

from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class ReportForm(FlaskForm):
    reason = TextAreaField("Reason for reporting", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Submit report")