"""Send-a-message form.

Image validity is enforced server-side by content in
app/blueprints/messages/media.py — FileAllowed here is just a UX hint.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class MessageForm(FlaskForm):
    body = TextAreaField("Message", validators=[DataRequired(), Length(max=2000)])
    image = FileField(
        "Image (optional)",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only.")],
    )
    submit = SubmitField("Send")