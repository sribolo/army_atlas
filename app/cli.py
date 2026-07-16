"""Custom Flask CLI commands.

No web surface: `flask seed-concerts` and `flask seed-badges` are the only
ways concert and badge catalog data enter the database. Any future
create/edit route for either must be guarded by @admin_required (see
app/authorization.py).
"""

import json
from datetime import datetime
from pathlib import Path

import click

from app.extensions import db
from app.models import Badge, Concert, Tour

CONCERTS_DATA_FILE = Path(__file__).parent / "data" / "concerts.json"
BADGES_DATA_FILE = Path(__file__).parent / "data" / "badges.json"


def register_cli(app):
    @app.cli.command("seed-concerts")
    def seed_concerts():
        """Load tours and concerts from app/data/concerts.json.

        Idempotent: tours are matched by name, concerts by
        (tour, venue, starts_at) — the same natural key enforced by the
        concerts table's unique constraint. Running this twice updates
        existing rows in place instead of duplicating them.
        """
        payload = json.loads(CONCERTS_DATA_FILE.read_text())

        tours_created = 0
        concerts_created = 0
        concerts_updated = 0

        for tour_data in payload["tours"]:
            tour = Tour.query.filter_by(name=tour_data["name"]).first()
            if tour is None:
                tour = Tour(name=tour_data["name"])
                db.session.add(tour)
                db.session.flush()  # assign tour.id before concerts reference it
                tours_created += 1

            for concert_data in tour_data["concerts"]:
                starts_at = datetime.fromisoformat(
                    concert_data["starts_at"].replace("Z", "+00:00")
                )
                fields = {
                    "name": concert_data["name"],
                    "venue": concert_data["venue"],
                    "city": concert_data["city"],
                    "country": concert_data["country"],
                    "latitude": concert_data["latitude"],
                    "longitude": concert_data["longitude"],
                    "starts_at": starts_at,
                    "timezone": concert_data["timezone"],
                }

                concert = Concert.query.filter_by(
                    tour_id=tour.id,
                    venue=concert_data["venue"],
                    starts_at=starts_at,
                ).first()

                if concert is None:
                    concert = Concert(tour_id=tour.id)
                    db.session.add(concert)
                    concerts_created += 1
                else:
                    concerts_updated += 1

                for field, value in fields.items():
                    setattr(concert, field, value)

        db.session.commit()
        click.echo(
            f"Seeded {tours_created} new tour(s); "
            f"{concerts_created} new concert(s), {concerts_updated} already up to date."
        )

    @app.cli.command("seed-badges")
    def seed_badges():
        """Load the badge catalog from app/data/badges.json.

        Idempotent: matched by `code`, the catalog's natural key. Running
        this twice updates existing rows (name/icon/description) in place
        instead of duplicating them.
        """
        payload = json.loads(BADGES_DATA_FILE.read_text())

        created = 0
        updated = 0

        for badge_data in payload["badges"]:
            badge = Badge.query.filter_by(code=badge_data["code"]).first()
            if badge is None:
                badge = Badge(
                    code=badge_data["code"],
                    name=badge_data["name"],
                    icon=badge_data["icon"],
                    description=badge_data["description"],
                )
                db.session.add(badge)
                created += 1
            else:
                badge.name = badge_data["name"]
                badge.icon = badge_data["icon"]
                badge.description = badge_data["description"]
                updated += 1

        db.session.commit()
        click.echo(f"Seeded {created} new badge(s); {updated} already up to date.")
