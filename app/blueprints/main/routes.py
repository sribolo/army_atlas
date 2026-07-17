from datetime import datetime, timezone

from flask import render_template, request
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.blueprints.main import main_bp
from app.extensions import db
from app.models import Concert, Follow, Friendship, Memory, MemoryLike, MemoryVisibility, Tag, Tour, User
from app.models.tag import memory_tags
from app.social_graph import can_view_memory

UPCOMING_CONCERTS_LIMIT = 6
HOME_FEED_LIMIT = 3
SEARCH_RESULT_LIMIT = 20
TRENDING_TAGS_LIMIT = 5

# Cycled per pin on the homepage's stylized map card — purely decorative.
MAP_PIN_COLORS = [
    {"ring": "#ff6ec7", "fill": "#ff8ed4"},
    {"ring": "#9b6cff", "fill": "#b794ff"},
    {"ring": "#7c9cff", "fill": "#aec4ff"},
    {"ring": "#ffb56e", "fill": "#ffd0a8"},
]

# The mockup's map SVG is a hand-drawn stylized world (viewBox 0 0 332 172),
# not a real projection — this is a simple equirectangular mapping of
# lat/long onto that same viewBox so real pins land roughly in the right
# place relative to the drawn continents.
MAP_VIEWBOX_W = 332
MAP_VIEWBOX_H = 172


def _project_to_map(latitude: float, longitude: float) -> tuple[float, float]:
    x = (longitude + 180) / 360 * MAP_VIEWBOX_W
    y = (90 - latitude) / 180 * MAP_VIEWBOX_H
    return round(x, 1), round(y, 1)


@main_bp.route("/")
def index():
    upcoming_concerts = (
        Concert.query.filter(Concert.starts_at > datetime.now(timezone.utc))
        .order_by(Concert.starts_at.asc())
        .limit(UPCOMING_CONCERTS_LIMIT)
        .all()
    )

    next_tour = upcoming_concerts[0].tour if upcoming_concerts else None

    # The map card is branded with next_tour's name, so its stats and pins
    # are scoped to that tour's own concerts rather than the whole catalog
    # — one pin per city (a multi-night stop only gets a single dot).
    tour_concerts = (
        Concert.query.filter_by(tour_id=next_tour.id).order_by(Concert.starts_at.asc()).all()
        if next_tour
        else []
    )
    map_pins = []
    seen_cities = set()
    for concert in tour_concerts:
        if concert.city in seen_cities:
            continue
        seen_cities.add(concert.city)
        i = len(map_pins)
        x, y = _project_to_map(concert.latitude, concert.longitude)
        colors = MAP_PIN_COLORS[i % len(MAP_PIN_COLORS)]
        map_pins.append({"concert": concert, "x": x, "y": y, "delay": round((i % 6) * 0.6, 1), **colors})

    total_shows = len(tour_concerts)
    total_cities = len(seen_cities)

    feed_memories = []
    like_counts = {}
    if current_user.is_authenticated:
        followed_ids = db.session.query(Follow.followed_id).filter(
            Follow.follower_id == current_user.id
        )
        friend_ids = Friendship.friend_ids_for(current_user.id)
        candidates = (
            # Friendship doesn't imply a Follow row (see social.feed for the
            # same union, and why) — a friend's memory should show up here
            # even if you never separately hit Follow on them.
            Memory.query.filter(
                or_(Memory.user_id.in_(followed_ids), Memory.user_id.in_(friend_ids))
            )
            .filter(Memory.visibility != MemoryVisibility.PRIVATE)
            .options(joinedload(Memory.user), joinedload(Memory.concert), selectinload(Memory.media))
            .order_by(Memory.created_at.desc())
            .limit(HOME_FEED_LIMIT * 3)  # over-fetch; can_view_memory below may drop some
            .all()
        )
        feed_memories = [m for m in candidates if can_view_memory(current_user, m)][:HOME_FEED_LIMIT]
        like_counts = MemoryLike.counts_for([m.id for m in feed_memories])

    return render_template(
        "main/index.html",
        upcoming_concerts=upcoming_concerts,
        map_pins=map_pins,
        total_shows=total_shows,
        total_cities=total_cities,
        next_tour=next_tour,
        feed_memories=feed_memories,
        like_counts=like_counts,
    )


@main_bp.route("/splash")
def splash():
    return render_template("main/splash.html")


@main_bp.route("/terms")
def terms():
    return render_template("main/terms.html")


@main_bp.route("/privacy")
def privacy():
    return render_template("main/privacy.html")


@main_bp.route("/search")
def search():
    """Case-insensitive search across concerts, tours, users, and tags.

    Tag matches also surface a preview of memories carrying that tag —
    those, like any memory result, are filtered through can_view_memory so
    a search can never reveal a private or friends-only memory to someone
    who couldn't otherwise see it.
    """
    query = request.args.get("q", "").strip()
    results = {"concerts": [], "tours": [], "users": [], "tags": [], "memories": []}
    trending_tags = []

    if query:
        like_pattern = f"%{query}%"

        results["concerts"] = (
            Concert.query.filter(
                Concert.name.ilike(like_pattern)
                | Concert.city.ilike(like_pattern)
                | Concert.country.ilike(like_pattern)
            )
            .limit(SEARCH_RESULT_LIMIT)
            .all()
        )

        results["tours"] = Tour.query.filter(Tour.name.ilike(like_pattern)).limit(SEARCH_RESULT_LIMIT).all()

        results["users"] = (
            User.query.filter(User.username.ilike(like_pattern) | User.bias.ilike(like_pattern))
            .limit(SEARCH_RESULT_LIMIT)
            .all()
        )

        matching_tags = Tag.query.filter(Tag.name.ilike(like_pattern)).limit(SEARCH_RESULT_LIMIT).all()
        results["tags"] = matching_tags

        if matching_tags:
            tag_ids = [tag.id for tag in matching_tags]
            candidate_memories = (
                Memory.query.join(Memory.tags)
                .filter(Tag.id.in_(tag_ids))
                .distinct()
                .limit(SEARCH_RESULT_LIMIT * 2)  # over-fetch; visibility filtering below may drop some
                .all()
            )
            results["memories"] = [
                m for m in candidate_memories if can_view_memory(current_user, m)
            ][:SEARCH_RESULT_LIMIT]
    else:
        # Popularity by usage across publicly-visible memories only, so a
        # trending tag can never hint at what's inside a private memory.
        trending_tags = (
            db.session.query(Tag, func.count(memory_tags.c.memory_id).label("uses"))
            .join(memory_tags, Tag.id == memory_tags.c.tag_id)
            .join(Memory, Memory.id == memory_tags.c.memory_id)
            .filter(Memory.visibility != MemoryVisibility.PRIVATE)
            .group_by(Tag.id)
            .order_by(func.count(memory_tags.c.memory_id).desc())
            .limit(TRENDING_TAGS_LIMIT)
            .all()
        )

    return render_template("main/search.html", query=query, results=results, trending_tags=trending_tags)
