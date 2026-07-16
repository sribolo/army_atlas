"""Memory create/read/edit/delete, always scoped to a concert, plus comments
and likes on a memory.

Ownership is enforced via app.authorization.require_ownership on every
edit/delete/media-delete route — this is the main IDOR surface in the app
(phase 3 security focus). Story/title/comment bodies are rendered through
Jinja's default autoescaping; nothing here is ever marked |safe. Comment
creation and like/unlike are gated by can_view_memory — the same visibility
rule that governs reading a memory also governs reacting to it.
"""

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.datastructures import FileStorage

from app.authorization import require_ownership
from app.badges import BadgeService
from app.blueprints.memories import memories_bp
from app.blueprints.memories.forms import CommentForm, MemoryForm, parse_tags
from app.blueprints.memories.media import (
    MAX_FILES_PER_MEMORY,
    delete_memory_media,
    upload_memory_media,
)
from app.extensions import db, limiter
from app.models import (
    Comment,
    Concert,
    Media,
    MediaType,
    Memory,
    MemoryLike,
    MemoryVisibility,
    NotificationType,
    Report,
    Tag,
)
from app.notifications import NotificationService
from app.reports import ReportForm
from app.social_graph import can_view_memory
from app.uploads import InvalidUploadError


def _submitted_files(field_data):
    """Filter a MultipleFileField's .data down to real uploads.

    When a field named "media" is edited with obj=memory and the multipart
    POST doesn't include that field at all (e.g. editing text without
    adding files), WTForms falls back to getattr(memory, "media") — the
    ORM relationship, not an upload list. Filtering by type (not just
    truthiness) keeps that fallback from ever reaching Cloudinary.
    """
    return [f for f in (field_data or []) if isinstance(f, FileStorage) and f.filename]


def _get_or_create_tags(names):
    tags = []
    for name in names:
        tag = Tag.query.filter_by(name=name).first()
        if tag is None:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()
        tags.append(tag)
    return tags


def _attach_uploads(memory, uploads):
    """Validate and upload each file, adding a Media row per success.

    Raises InvalidUploadError on the first bad file; the caller rolls back
    so a partially-processed batch never leaves orphaned Media rows.
    """
    for upload in uploads:
        url, public_id, media_type = upload_memory_media(upload)
        db.session.add(
            Media(
                memory_id=memory.id,
                url=url,
                public_id=public_id,
                media_type=MediaType(media_type),
            )
        )


def _format_local_date(concert):
    return concert.starts_at_local.strftime("%b %d, %Y").replace(" 0", " ")


def _memory_concert_options(selected_concert):
    concerts = Concert.query.order_by(Concert.starts_at.desc()).all()
    if selected_concert not in concerts:
        concerts = [selected_concert, *concerts]

    grouped_by_stop = defaultdict(list)
    for concert in sorted(concerts, key=lambda item: item._starts_at_utc):
        grouped_by_stop[(concert.tour_id, concert.venue)].append(concert)

    night_labels = {}
    for stop_concerts in grouped_by_stop.values():
        if len(stop_concerts) > 1:
            for index, concert in enumerate(stop_concerts, start=1):
                night_labels[concert.id] = f"Night {index}"

    options = []
    for concert in concerts:
        date_label = _format_local_date(concert)
        night_label = night_labels.get(concert.id)
        main_label = f"{concert.city} · {night_label or date_label}"
        if night_label:
            detail_label = f"{date_label} · {concert.venue}"
        else:
            detail_label = concert.venue
        options.append(
            {
                "concert": concert,
                "tour_name": concert.tour.name,
                "main_label": main_label,
                "detail_label": detail_label,
                "select_label": f"{concert.country} - {main_label} - {detail_label}",
                "selected": concert.id == selected_concert.id,
            }
        )
    return options


def _will_earn_memory_keeper_badge(user_id):
    """True only if this user's *next* memory post would actually tip them
    over the Memory Keeper threshold (see app.badges.MEMORY_KEEPER_THRESHOLD)
    — not just "some day". Used so the review step never promises a badge
    the post won't actually unlock.
    """
    progress = BadgeService.progress_for_user(user_id)
    entry = next((e for e in progress if e["badge"].code == "memory_keeper"), None)
    if entry is None or entry["earned_at"] is not None:
        return False
    return entry["current"] + 1 >= entry["target"]


def _memory_concert_option_groups(selected_concert):
    groups = []
    for option in _memory_concert_options(selected_concert):
        if not groups or groups[-1]["label"] != option["tour_name"]:
            groups.append({"label": option["tour_name"], "options": []})
        groups[-1]["options"].append(option)
    return groups


def _selected_memory_concert(default_concert):
    submitted_id = request.form.get("concert_id")
    if not submitted_id:
        return default_concert
    try:
        concert_id = UUID(submitted_id)
    except ValueError:
        flash("Choose a valid show.", "danger")
        return default_concert
    return Concert.query.get(concert_id) or default_concert


@memories_bp.route("/memories/new")
@login_required
def new_memory():
    concert = (
        Concert.query.filter(Concert.starts_at > datetime.now(timezone.utc))
        .order_by(Concert.starts_at.asc())
        .first()
    )
    if concert is None:
        concert = Concert.query.order_by(Concert.starts_at.desc()).first()
    if concert is None:
        flash("No concerts are available yet.", "info")
        return redirect(url_for("concerts.list_concerts"))
    return redirect(url_for("memories.create_memory", concert_id=concert.id))


@memories_bp.route("/concerts/<uuid:concert_id>/memories/new", methods=["GET", "POST"])
@login_required
def create_memory(concert_id):
    concert = Concert.query.get_or_404(concert_id)
    form = MemoryForm()
    selected_concert = _selected_memory_concert(concert)
    concert_option_groups = _memory_concert_option_groups(selected_concert)

    if form.validate_on_submit():
        uploads = _submitted_files(form.media.data)[:MAX_FILES_PER_MEMORY]

        memory = Memory(
            user_id=current_user.id,
            concert_id=selected_concert.id,
            title=form.title.data,
            seat_section=form.seat_section.data or None,
            story=form.story.data or None,
            visibility=MemoryVisibility(form.visibility.data),
        )
        memory.tags = _get_or_create_tags(parse_tags(form.tags.data))
        db.session.add(memory)
        db.session.flush()
        BadgeService.evaluate_memory(current_user.id)

        try:
            _attach_uploads(memory, uploads)
        except InvalidUploadError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template(
                "memories/form.html",
                form=form,
                concert=selected_concert,
                memory=None,
                concert_option_groups=concert_option_groups,
                max_media_files=MAX_FILES_PER_MEMORY,
                will_earn_memory_keeper_badge=_will_earn_memory_keeper_badge(current_user.id),
            )

        db.session.commit()
        flash("Memory posted.", "success")
        return redirect(url_for("memories.memory_detail", memory_id=memory.id))

    return render_template(
        "memories/form.html",
        form=form,
        concert=selected_concert,
        memory=None,
        concert_option_groups=concert_option_groups,
        max_media_files=MAX_FILES_PER_MEMORY,
        will_earn_memory_keeper_badge=_will_earn_memory_keeper_badge(current_user.id),
    )


@memories_bp.route("/memories/<uuid:memory_id>")
def memory_detail(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    if not can_view_memory(current_user, memory):
        abort(403)

    comments = (
        Comment.query.filter_by(memory_id=memory.id).order_by(Comment.created_at.asc()).all()
    )
    like_count = MemoryLike.query.filter_by(memory_id=memory.id).count()
    user_has_liked = current_user.is_authenticated and (
        MemoryLike.query.filter_by(user_id=current_user.id, memory_id=memory.id).first() is not None
    )

    return render_template(
        "memories/detail.html",
        memory=memory,
        comments=comments,
        comment_form=CommentForm(),
        like_count=like_count,
        user_has_liked=user_has_liked,
    )


@memories_bp.route("/memories/<uuid:memory_id>/edit", methods=["GET", "POST"])
@login_required
def edit_memory(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    require_ownership(memory.user_id)

    form = MemoryForm(obj=memory)
    selected_concert = _selected_memory_concert(memory.concert)
    concert_option_groups = _memory_concert_option_groups(selected_concert)
    if not form.is_submitted():
        form.tags.data = ", ".join(tag.name for tag in memory.tags)
        form.visibility.data = memory.visibility.value

    if form.validate_on_submit():
        memory.concert_id = selected_concert.id
        memory.title = form.title.data
        memory.seat_section = form.seat_section.data or None
        memory.story = form.story.data or None
        memory.visibility = MemoryVisibility(form.visibility.data)
        memory.tags = _get_or_create_tags(parse_tags(form.tags.data))

        remaining_slots = max(MAX_FILES_PER_MEMORY - len(memory.media), 0)
        uploads = _submitted_files(form.media.data)[:remaining_slots]

        try:
            _attach_uploads(memory, uploads)
        except InvalidUploadError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template(
                "memories/form.html",
                form=form,
                concert=selected_concert,
                memory=memory,
                concert_option_groups=concert_option_groups,
                max_media_files=max(MAX_FILES_PER_MEMORY - len(memory.media), 0),
            )

        db.session.commit()
        flash("Memory updated.", "success")
        return redirect(url_for("memories.memory_detail", memory_id=memory.id))

    return render_template(
        "memories/form.html",
        form=form,
        concert=selected_concert,
        memory=memory,
        concert_option_groups=concert_option_groups,
        max_media_files=max(MAX_FILES_PER_MEMORY - len(memory.media), 0),
    )


@memories_bp.route("/memories/<uuid:memory_id>/media/<uuid:media_id>/delete", methods=["POST"])
@login_required
def delete_media(memory_id, media_id):
    memory = Memory.query.get_or_404(memory_id)
    require_ownership(memory.user_id)
    media = Media.query.filter_by(id=media_id, memory_id=memory.id).first_or_404()

    delete_memory_media(media.public_id, media.media_type.value)
    db.session.delete(media)
    db.session.commit()
    flash("Photo/video removed.", "info")
    return redirect(url_for("memories.edit_memory", memory_id=memory.id))


@memories_bp.route("/memories/<uuid:memory_id>/delete", methods=["POST"])
@login_required
def delete_memory(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    require_ownership(memory.user_id)
    concert_id = memory.concert_id

    for media in memory.media:
        delete_memory_media(media.public_id, media.media_type.value)

    db.session.delete(memory)
    db.session.commit()
    flash("Memory deleted.", "info")
    return redirect(url_for("concerts.concert_detail", concert_id=concert_id))


# --- comments ------------------------------------------------------------


def _can_delete_comment(comment, memory) -> bool:
    """Author or memory owner may delete; nobody else."""
    return current_user.is_authenticated and current_user.id in (comment.user_id, memory.user_id)


@memories_bp.route("/memories/<uuid:memory_id>/comments", methods=["POST"])
@login_required
@limiter.limit("30 per hour", methods=["POST"])
def create_comment(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    if not can_view_memory(current_user, memory):
        abort(403)

    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(user_id=current_user.id, memory_id=memory.id, body=form.body.data)
        db.session.add(comment)
        NotificationService.notify(
            recipient_id=memory.user_id,
            actor_id=current_user.id,
            type=NotificationType.COMMENT,
            target_type="memory",
            target_id=memory.id,
        )
        db.session.commit()
        flash("Comment posted.", "success")
    else:
        for error in form.body.errors:
            flash(error, "danger")

    return redirect(url_for("memories.memory_detail", memory_id=memory.id))


@memories_bp.route("/memories/<uuid:memory_id>/comments/<uuid:comment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_comment(memory_id, comment_id):
    memory = Memory.query.get_or_404(memory_id)
    comment = Comment.query.filter_by(id=comment_id, memory_id=memory.id).first_or_404()
    require_ownership(comment.user_id)  # edit is author-only, unlike delete

    form = CommentForm(obj=comment)
    if form.validate_on_submit():
        comment.body = form.body.data
        db.session.commit()
        flash("Comment updated.", "success")
        return redirect(url_for("memories.memory_detail", memory_id=memory.id))

    return render_template("memories/comment_edit.html", form=form, memory=memory, comment=comment)


@memories_bp.route("/memories/<uuid:memory_id>/comments/<uuid:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(memory_id, comment_id):
    memory = Memory.query.get_or_404(memory_id)
    comment = Comment.query.filter_by(id=comment_id, memory_id=memory.id).first_or_404()
    if not _can_delete_comment(comment, memory):
        abort(403)

    db.session.delete(comment)
    db.session.commit()
    flash("Comment deleted.", "info")
    return redirect(url_for("memories.memory_detail", memory_id=memory.id))


# --- likes -----------------------------------------------------------------


@memories_bp.route("/memories/<uuid:memory_id>/like", methods=["POST"])
@login_required
def like_memory(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    if not can_view_memory(current_user, memory):
        abort(403)

    already = MemoryLike.query.filter_by(user_id=current_user.id, memory_id=memory.id).first()
    if already is None:
        db.session.add(MemoryLike(user_id=current_user.id, memory_id=memory.id))
        NotificationService.notify(
            recipient_id=memory.user_id,
            actor_id=current_user.id,
            type=NotificationType.LIKE,
            target_type="memory",
            target_id=memory.id,
        )
        db.session.commit()

    return redirect(url_for("memories.memory_detail", memory_id=memory.id))


@memories_bp.route("/memories/<uuid:memory_id>/unlike", methods=["POST"])
@login_required
def unlike_memory(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    if not can_view_memory(current_user, memory):
        abort(403)

    MemoryLike.query.filter_by(user_id=current_user.id, memory_id=memory.id).delete()
    db.session.commit()
    return redirect(url_for("memories.memory_detail", memory_id=memory.id))


# --- reports ---------------------------------------------------------------


@memories_bp.route("/memories/<uuid:memory_id>/report", methods=["GET", "POST"])
@login_required
def report_memory(memory_id):
    memory = Memory.query.get_or_404(memory_id)
    if not can_view_memory(current_user, memory):
        abort(403)  # can't report something you can't even see

    form = ReportForm()
    if form.validate_on_submit():
        db.session.add(
            Report(
                reporter_id=current_user.id,
                target_type="memory",
                target_id=memory.id,
                reason=form.reason.data,
            )
        )
        db.session.commit()
        flash("Thanks — your report has been submitted for review.", "success")
        return redirect(url_for("memories.memory_detail", memory_id=memory.id))

    return render_template(
        "report_form.html",
        form=form,
        target_label=f"memory “{memory.title}”",
        cancel_url=url_for("memories.memory_detail", memory_id=memory.id),
    )


@memories_bp.route("/memories/<uuid:memory_id>/comments/<uuid:comment_id>/report", methods=["GET", "POST"])
@login_required
def report_comment(memory_id, comment_id):
    memory = Memory.query.get_or_404(memory_id)
    if not can_view_memory(current_user, memory):
        abort(403)
    comment = Comment.query.filter_by(id=comment_id, memory_id=memory.id).first_or_404()

    form = ReportForm()
    if form.validate_on_submit():
        db.session.add(
            Report(
                reporter_id=current_user.id,
                target_type="comment",
                target_id=comment.id,
                reason=form.reason.data,
            )
        )
        db.session.commit()
        flash("Thanks — your report has been submitted for review.", "success")
        return redirect(url_for("memories.memory_detail", memory_id=memory.id))

    return render_template(
        "report_form.html",
        form=form,
        target_label=f"comment by {comment.user.username}",
        cancel_url=url_for("memories.memory_detail", memory_id=memory.id),
    )
