"""Memory create/edit form.

Media validity is enforced server-side by content in
app/blueprints/memories/media.py — FileAllowed here is just a UX hint.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, MultipleFileField
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.models import MemoryVisibility

TAG_NAME_MAX_LENGTH = 50


def parse_tags(raw):
    """Split, lowercase, strip leading '#', dedupe (order-preserving)."""
    if not raw:
        return []
    seen = {}
    for chunk in raw.split(","):
        tag = chunk.strip().lstrip("#").lower()[:TAG_NAME_MAX_LENGTH]
        if tag:
            seen[tag] = None
    return list(seen.keys())


class MemoryForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    seat_section = StringField("Seat / section", validators=[Optional(), Length(max=100)])
    story = TextAreaField("Story", validators=[Optional(), Length(max=5000)])
    tags = StringField("Tags (comma-separated)", validators=[Optional(), Length(max=500)])
    visibility = SelectField(
        "Who can see this",
        choices=[(v.value, v.value.capitalize()) for v in MemoryVisibility],
        default=MemoryVisibility.PUBLIC.value,
        validators=[DataRequired()],
    )
    media = MultipleFileField(
        "Photos / videos",
        validators=[
            FileAllowed(
                ["jpg", "jpeg", "png", "webp", "mp4", "mov", "webm"],
                "Images and videos only.",
            )
        ],
    )
    submit = SubmitField("Post memory")


class CommentForm(FlaskForm):
    body = TextAreaField("Comment", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Post comment")
