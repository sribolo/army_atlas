"""Read-only concert listing/detail, attendance marking, and the
open-to-connect opt-in.

Concerts themselves are admin-curated canonical data — loaded only via
`flask seed-concerts` (app/cli.py). There is still no write path to the
concerts table itself; any future create/edit route must be guarded by
@admin_required (see app/authorization.py). Attendance is a separate,
user-owned table and is fair game for a write path here, including the
open_to_connect flag added in phase 4 (it's just another attendance field).
"""

from collections import defaultdict
from datetime import datetime, timezone
from math import ceil

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.badges import BadgeService
from app.blueprints.concerts import concerts_bp
from app.extensions import db
from app.models import Attendance, Concert, Memory, MemoryLike, User
from app.social_graph import can_view_memory


TOUR_BANNERS = {
    "Arirang World Tour": "arirang.jpg",
    "#RUNSEOKJIN_EP.TOUR": "runseokjin.jpg",
    "Hope on the Stage Tour": "hope-on-the-stage.png",
    "D-DAY Tour": "dday.jpg",
    "Love Yourself Tour": "love-yourself.jpg",
    "Love Yourself Tour: Speak Yourself": "love-yourself.jpg",
    "Wings Tour": "wings.jpg",
}


def _tour_banner_filename(concert):
    return TOUR_BANNERS.get(concert.tour.name, "arirang.jpg")


@concerts_bp.route("/concerts")
def list_concerts():
    now_utc = datetime.now(timezone.utc)
    requested_filter = request.args.get("filter", "upcoming")
    if requested_filter not in {"upcoming", "all", "past"}:
        requested_filter = "upcoming"

    all_concerts = sorted(Concert.query.all(), key=lambda concert: concert._starts_at_utc)
    upcoming_concerts = [concert for concert in all_concerts if concert._starts_at_utc >= now_utc]
    past_concerts = [concert for concert in all_concerts if concert._starts_at_utc < now_utc]
    current_filter = requested_filter
    if requested_filter == "upcoming" and not upcoming_concerts:
        current_filter = "all"

    if current_filter == "upcoming":
        concerts = upcoming_concerts
    elif current_filter == "past":
        concerts = list(reversed(past_concerts))
    else:
        concerts = all_concerts

    # Same stop = same tour + venue, regardless of date filter, so a
    # multi-night stop always reports its true total night count.
    nights_per_stop = defaultdict(int)
    for concert in all_concerts:
        nights_per_stop[(concert.tour_id, concert.venue)] += 1

    concert_cards = []
    for concert in concerts:
        days_until = ceil((concert._starts_at_utc - now_utc).total_seconds() / 86400)
        if days_until < 0:
            status = "PAST"
            day_count = None
        elif days_until == 0:
            status = "TODAY"
            day_count = None
        else:
            status = "DAYS"
            day_count = days_until
        night_count = nights_per_stop[(concert.tour_id, concert.venue)]
        concert_cards.append(
            {
                "concert": concert,
                "day_count": day_count,
                "status": status,
                "banner_filename": _tour_banner_filename(concert),
                "night_label": f"{night_count} Night" if night_count == 1 else f"{night_count} Nights",
            }
        )

    return render_template(
        "concerts/list.html",
        concert_cards=concert_cards,
        current_filter=current_filter,
        total_concert_count=len(all_concerts),
        upcoming_concert_count=len(upcoming_concerts),
        past_concert_count=len(past_concerts),
    )


@concerts_bp.route("/concerts/<uuid:concert_id>")
def concert_detail(concert_id):
    concert = Concert.query.get_or_404(concert_id)

    sibling_nights = (
        Concert.query.filter_by(tour_id=concert.tour_id, venue=concert.venue)
        .order_by(Concert.starts_at)
        .all()
    )

    attendee_count = Attendance.query.filter_by(concert_id=concert.id).count()
    memory_count = Memory.query.filter_by(concert_id=concert.id).count()

    all_memories = Memory.query.filter_by(concert_id=concert.id).order_by(Memory.created_at.desc()).all()
    memories = [m for m in all_memories if can_view_memory(current_user, m)]
    like_counts = MemoryLike.counts_for([m.id for m in memories])

    user_attendance = None
    co_attendee_count = 0
    open_connect_users = []
    if current_user.is_authenticated:
        user_attendance = Attendance.query.filter_by(
            user_id=current_user.id, concert_id=concert.id
        ).first()
        if user_attendance is not None:
            co_attendee_count = Attendance.query.filter(
                Attendance.concert_id == concert.id, Attendance.user_id != current_user.id
            ).count()
            open_connect_users = (
                User.query.join(Attendance, Attendance.user_id == User.id)
                .filter(
                    Attendance.concert_id == concert.id,
                    Attendance.open_to_connect.is_(True),
                    Attendance.user_id != current_user.id,
                )
                .order_by(User.username)
                .all()
            )

    return render_template(
        "concerts/detail.html",
        concert=concert,
        sibling_nights=sibling_nights,
        attendee_count=attendee_count,
        memory_count=memory_count,
        memories=memories,
        like_counts=like_counts,
        banner_filename=_tour_banner_filename(concert),
        user_attending=user_attendance is not None,
        user_open_to_connect=user_attendance.open_to_connect if user_attendance else False,
        co_attendee_count=co_attendee_count,
        open_connect_users=open_connect_users,
    )


@concerts_bp.route("/concerts/<uuid:concert_id>/attend", methods=["POST"])
@login_required
def attend_concert(concert_id):
    concert = Concert.query.get_or_404(concert_id)
    already = Attendance.query.filter_by(user_id=current_user.id, concert_id=concert.id).first()
    if already is None:
        db.session.add(Attendance(user_id=current_user.id, concert_id=concert.id))
        db.session.flush()  # so the new row counts toward BadgeService's queries
        BadgeService.evaluate_attendance(current_user.id)
        db.session.commit()
        flash("Added to your countdown." if concert.is_upcoming else "Marked as attended.", "success")
    return redirect(url_for("concerts.concert_detail", concert_id=concert.id))


@concerts_bp.route("/concerts/<uuid:concert_id>/unattend", methods=["POST"])
@login_required
def unattend_concert(concert_id):
    concert = Concert.query.get_or_404(concert_id)
    Attendance.query.filter_by(user_id=current_user.id, concert_id=concert.id).delete()
    db.session.commit()
    flash("Attendance removed.", "info")
    return redirect(url_for("concerts.concert_detail", concert_id=concert.id))


@concerts_bp.route("/concerts/<uuid:concert_id>/open-to-connect", methods=["POST"])
@login_required
def toggle_open_to_connect(concert_id):
    concert = Concert.query.get_or_404(concert_id)
    attendance = Attendance.query.filter_by(
        user_id=current_user.id, concert_id=concert.id
    ).first_or_404()
    attendance.open_to_connect = not attendance.open_to_connect
    db.session.commit()
    flash(
        "You're now listed as open to connect." if attendance.open_to_connect else "No longer listed as open to connect.",
        "info",
    )
    return redirect(url_for("concerts.concert_detail", concert_id=concert.id))
