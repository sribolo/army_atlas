"""Public profile page, owner-only profile editing, time capsules, and
user reports.

Edit access is gated by app.authorization.require_ownership rather than an
implicit "always self" assumption, so a logged-in user hitting another
user's edit URL gets a real 403. Time capsules are self-only (never take a
username/user_id from the URL) and additionally time-locked: the body is
never included in a rendered response before unlock_at, not even for the
owner — see TimeCapsule.is_unlocked.
"""

from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.authorization import require_ownership
from app.badges import BadgeService
from app.blueprints.profiles import profiles_bp
from app.blueprints.profiles.forms import EditProfileForm, TicketDetailsForm, TimeCapsuleForm
from app.blueprints.profiles.images import (
    COVER_CLOUDINARY_FOLDER,
    InvalidImageError,
    upload_profile_image,
)
from app.extensions import db
from app.models import (
    Attendance,
    Concert,
    Follow,
    Friendship,
    Memory,
    MemoryLike,
    Report,
    TimeCapsule,
    User,
    UserBadge,
)
from app.reports import ReportForm
from app.social_graph import can_view_memory, relationship_summary


TICKET_ART = {
    "Arirang World Tour": {
        "wallet": "arirang-wallet.jpg",
        "detail": "arirang-detail.jpg",
        "theme": "arirang",
    },
    "#RUNSEOKJIN_EP.TOUR": {
        "wallet": "runseokjin-wallet.jpeg",
        "detail": "runseokjin-detail.jpeg",
        "theme": "runseokjin",
    },
    "Hope on the Stage Tour": {
        "wallet": "hope-wallet.jpeg",
        "detail": "hope-detail.jpeg",
        "theme": "hope",
    },
    "D-DAY Tour": {
        "wallet": "agustd-wallet.webp",
        "detail": "agustd-detail.webp",
        "theme": "dday",
    },
    "Love Yourself Tour": {
        "wallet": "ly-wallet.webp",
        "detail": "ly-detail.jpg",
        "theme": "love-yourself",
    },
    "Love Yourself Tour: Speak Yourself": {
        "wallet": "ly-wallet.webp",
        "detail": "ly-detail.jpg",
        "theme": "love-yourself",
    },
    "Wings Tour": {
        "wallet": "wings-wallet.jpg",
        "detail": "wings-detail.jpg",
        "theme": "wings",
    },
}


def _ticket_art(concert):
    return TICKET_ART.get(concert.tour.name, {})


# Solo-member tours, not full-group OT7 concerts — anything not listed here
# defaults to "BTS · OT7" (see _ticket_artist below).
SOLO_TOUR_ARTISTS = {
    "#RUNSEOKJIN_EP.TOUR": "Jin",
    "Hope on the Stage Tour": "j-hope",
    "D-DAY Tour": "SUGA · Agust D",
}


def _ticket_artist(concert):
    return SOLO_TOUR_ARTISTS.get(concert.tour.name, "BTS · OT7")


# Pill choices on the edit-profile screen. bias/country stay free-text
# columns (User.bias, User.country) — picking "Other" reveals a plain text
# input (see edit_profile.html) so a value outside this list is never
# silently discarded.
BIAS_PRESETS = ["RM", "Jin", "SUGA", "j-hope", "Jimin", "V", "JK", "OT7 \U0001F49c"]
COUNTRY_PRESETS = ["Korea", "USA", "Japan", "Indonesia", "Philippines", "Brazil", "UK"]


@profiles_bp.route("/u/<username>")
def public_profile(username):
    profile_user = User.query.filter_by(username=username).first_or_404()

    concerts_attended_count = Attendance.query.filter_by(user_id=profile_user.id).count()
    memories_count = Memory.query.filter_by(user_id=profile_user.id).count()
    follower_count = Follow.query.filter_by(followed_id=profile_user.id).count()
    following_count = Follow.query.filter_by(follower_id=profile_user.id).count()
    friend_count = len(Friendship.friend_ids_for(profile_user.id))

    all_memories = (
        Memory.query.filter_by(user_id=profile_user.id).order_by(Memory.created_at.desc()).all()
    )
    memories = [m for m in all_memories if can_view_memory(current_user, m)]
    like_counts = MemoryLike.counts_for([m.id for m in memories])

    passport_stamps = (
        db.session.query(Concert)
        .join(Attendance, Attendance.concert_id == Concert.id)
        .filter(Attendance.user_id == profile_user.id)
        .order_by(Concert.starts_at.desc())
        .all()
    )

    next_upcoming_concert = (
        db.session.query(Concert)
        .join(Attendance, Attendance.concert_id == Concert.id)
        .filter(Attendance.user_id == profile_user.id, Concert.starts_at > datetime.now(timezone.utc))
        .order_by(Concert.starts_at.asc())
        .first()
    )

    earned_badges = (
        db.session.query(UserBadge)
        .filter_by(user_id=profile_user.id)
        .order_by(UserBadge.earned_at.desc())
        .all()
    )

    return render_template(
        "profiles/public_profile.html",
        profile_user=profile_user,
        concerts_attended_count=concerts_attended_count,
        memories_count=memories_count,
        follower_count=follower_count,
        following_count=following_count,
        friend_count=friend_count,
        memories=memories,
        like_counts=like_counts,
        passport_stamps=passport_stamps,
        next_upcoming_concert=next_upcoming_concert,
        earned_badges=earned_badges,
        relationship=relationship_summary(current_user, profile_user),
    )


@profiles_bp.route("/u/<username>/badges")
def badges(username):
    profile_user = User.query.filter_by(username=username).first_or_404()

    badge_progress = BadgeService.progress_for_user(profile_user.id)
    earned_count = sum(1 for entry in badge_progress if entry["earned_at"] is not None)

    return render_template(
        "profiles/badges.html",
        profile_user=profile_user,
        badge_progress=badge_progress,
        earned_count=earned_count,
    )


@profiles_bp.route("/u/<username>/edit", methods=["GET", "POST"])
@login_required
def edit_profile(username):
    profile_user = User.query.filter_by(username=username).first_or_404()
    require_ownership(profile_user.id)

    form = EditProfileForm(obj=profile_user)
    picker_context = {
        "bias_presets": BIAS_PRESETS,
        "country_presets": COUNTRY_PRESETS,
        "bias_is_other": bool(profile_user.bias) and profile_user.bias not in BIAS_PRESETS,
        "country_is_other": bool(profile_user.country) and profile_user.country not in COUNTRY_PRESETS,
    }

    if form.validate_on_submit():
        profile_user.display_name = form.display_name.data or None

        country = form.country.data
        if country == "__other__":
            country = (request.form.get("country_other") or "").strip() or None
        profile_user.country = country

        bias = form.bias.data
        if bias == "__other__":
            bias = (request.form.get("bias_other") or "").strip() or None
        profile_user.bias = bias

        profile_user.city = form.city.data
        profile_user.bio = form.bio.data
        profile_user.instagram = form.instagram.data
        profile_user.tiktok = form.tiktok.data
        profile_user.twitter = form.twitter.data
        profile_user.discord = form.discord.data
        profile_user.spotify = form.spotify.data

        upload = form.profile_image.data
        if upload and upload.filename:
            try:
                url, public_id = upload_profile_image(
                    upload, previous_public_id=profile_user.profile_image_public_id
                )
                profile_user.profile_image_url = url
                profile_user.profile_image_public_id = public_id
            except InvalidImageError as exc:
                flash(str(exc), "danger")
                return render_template(
                    "profiles/edit_profile.html", form=form, profile_user=profile_user, **picker_context
                )

        cover_upload = form.cover_image.data
        if cover_upload and cover_upload.filename:
            try:
                url, public_id = upload_profile_image(
                    cover_upload,
                    previous_public_id=profile_user.cover_image_public_id,
                    folder=COVER_CLOUDINARY_FOLDER,
                )
                profile_user.cover_image_url = url
                profile_user.cover_image_public_id = public_id
            except InvalidImageError as exc:
                flash(str(exc), "danger")
                return render_template(
                    "profiles/edit_profile.html", form=form, profile_user=profile_user, **picker_context
                )

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profiles.public_profile", username=profile_user.username))

    return render_template(
        "profiles/edit_profile.html", form=form, profile_user=profile_user, **picker_context
    )


# --- time capsules -------------------------------------------------------
# Always self-only: no username/user_id in these URLs, so — like phase 4's
# follow/unfollow — there's no IDOR surface to guard by construction.


@profiles_bp.route("/capsules")
@login_required
def capsules():
    items = (
        TimeCapsule.query.filter_by(user_id=current_user.id)
        .order_by(TimeCapsule.unlock_at.asc())
        .all()
    )
    return render_template("profiles/capsules.html", capsules=items)


@profiles_bp.route("/capsules/new", methods=["GET", "POST"])
@login_required
def new_capsule():
    form = TimeCapsuleForm()
    if form.validate_on_submit():
        unlock_at = datetime.now(timezone.utc) + relativedelta(years=int(form.unlock_years.data))
        db.session.add(TimeCapsule(user_id=current_user.id, body=form.body.data, unlock_at=unlock_at))
        db.session.commit()
        flash("Capsule sealed. Check back after it unlocks.", "success")
        return redirect(url_for("profiles.capsules"))

    return render_template("profiles/capsule_form.html", form=form)


@profiles_bp.route("/capsules/<uuid:capsule_id>")
@login_required
def view_capsule(capsule_id):
    capsule = TimeCapsule.query.get_or_404(capsule_id)
    require_ownership(capsule.user_id)
    # The template only ever interpolates capsule.body when
    # capsule.is_unlocked is true — the body is genuinely absent from the
    # response otherwise, not just hidden by CSS.
    return render_template("profiles/capsule_detail.html", capsule=capsule)


@profiles_bp.route("/capsules/<uuid:capsule_id>/delete", methods=["POST"])
@login_required
def delete_capsule(capsule_id):
    capsule = TimeCapsule.query.get_or_404(capsule_id)
    require_ownership(capsule.user_id)
    db.session.delete(capsule)
    db.session.commit()
    flash("Capsule deleted.", "info")
    return redirect(url_for("profiles.capsules"))


# --- ticket wallet ----------------------------------------------------------
# Tickets are generated from Attendance, which is the app's canonical "I was
# there" record. No separate ticket table is needed unless physical seat/barcode
# metadata is added later.


@profiles_bp.route("/tickets")
@login_required
def tickets():
    attended_concerts = (
        db.session.query(Concert)
        .join(Attendance, Attendance.concert_id == Concert.id)
        .filter(Attendance.user_id == current_user.id)
        .order_by(Concert.starts_at.desc())
        .all()
    )
    ticket_cards = [
        {"concert": concert, "ticket_art": _ticket_art(concert), "artist": _ticket_artist(concert)}
        for concert in attended_concerts
    ]
    return render_template(
        "profiles/tickets.html",
        concerts=attended_concerts,
        ticket_cards=ticket_cards,
    )


@profiles_bp.route("/tickets/<uuid:concert_id>", methods=["GET", "POST"])
@login_required
def ticket_detail(concert_id):
    attendance = Attendance.query.filter_by(
        user_id=current_user.id, concert_id=concert_id
    ).first_or_404()
    concert = Concert.query.get_or_404(attendance.concert_id)
    ticket_form = TicketDetailsForm(obj=attendance)
    if ticket_form.validate_on_submit():
        attendance.section = ticket_form.section.data or None
        attendance.seat = ticket_form.seat.data or None
        db.session.commit()
        flash("Ticket details saved.", "success")
        return redirect(url_for("profiles.ticket_detail", concert_id=concert.id))

    return render_template(
        "profiles/ticket_detail.html",
        attendance=attendance,
        concert=concert,
        ticket_form=ticket_form,
        ticket_art=_ticket_art(concert),
        ticket_artist=_ticket_artist(concert),
    )


# --- reports ---------------------------------------------------------------


@profiles_bp.route("/u/<username>/report", methods=["GET", "POST"])
@login_required
def report_user(username):
    target = User.query.filter_by(username=username).first_or_404()
    if target.id == current_user.id:
        abort(404)

    form = ReportForm()
    if form.validate_on_submit():
        db.session.add(
            Report(
                reporter_id=current_user.id,
                target_type="user",
                target_id=target.id,
                reason=form.reason.data,
            )
        )
        db.session.commit()
        flash("Thanks — your report has been submitted for review.", "success")
        return redirect(url_for("profiles.public_profile", username=username))

    return render_template(
        "report_form.html",
        form=form,
        target_label=f"user “{target.username}”",
        cancel_url=url_for("profiles.public_profile", username=username),
    )
