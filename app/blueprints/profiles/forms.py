"""Edit-profile, time capsule, and report forms.

Image validity (EditProfileForm.profile_image / cover_image) is enforced
server-side by content in app/blueprints/profiles/images.py — FileAllowed
here is just a UX hint.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class EditProfileForm(FlaskForm):
    display_name = StringField("Display name", validators=[Optional(), Length(max=50)])
    country = StringField("Country", validators=[Optional(), Length(max=100)])
    city = StringField("City", validators=[Optional(), Length(max=100)])
    bias = StringField("Bias", validators=[Optional(), Length(max=50)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=2000)])

    instagram = StringField("Instagram", validators=[Optional(), Length(max=100)])
    tiktok = StringField("TikTok", validators=[Optional(), Length(max=100)])
    twitter = StringField("Twitter", validators=[Optional(), Length(max=100)])
    discord = StringField("Discord", validators=[Optional(), Length(max=100)])
    spotify = StringField("Spotify", validators=[Optional(), Length(max=100)])

    profile_image = FileField(
        "Profile picture",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only.")],
    )
    cover_image = FileField(
        "Cover photo",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only.")],
    )

    submit = SubmitField("Save changes")


class TimeCapsuleForm(FlaskForm):
    body = TextAreaField(
        "A message to your future self", validators=[DataRequired(), Length(max=5000)]
    )
    unlock_years = SelectField(
        "Unlock in",
        choices=[("1", "1 year"), ("5", "5 years"), ("10", "10 years")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Seal capsule")


class TicketDetailsForm(FlaskForm):
    section = StringField("Section", validators=[Optional(), Length(max=100)])
    seat = StringField("Seat", validators=[Optional(), Length(max=100)])
    submit = SubmitField("Save ticket details")
