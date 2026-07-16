"""Badge-awarding rules, evaluated on attendance and memory-creation events.

BadgeService is the only thing that should award a badge — routes call
through here rather than inserting UserBadge rows directly, so every rule
definition stays in one place. Awarding is idempotent: the unique
constraint on (user_id, badge_id) makes re-evaluating a rule safe even if
it's already been earned, and _award() checks first anyway to avoid
relying on a constraint violation for normal control flow.

Adds to the session but never commits — awards are meant to ride along in
the same transaction as the event that triggered them (an attend or a
create-memory call).
"""

from app.extensions import db
from app.models import Attendance, Badge, Concert, Memory, User, UserBadge

CONCERT_VETERAN_THRESHOLD = 5
MEMORY_KEEPER_THRESHOLD = 5

# Display order for the badges screen — not alphabetical, so it reads as a
# rough difficulty ramp. Any catalog badge not listed here (e.g. one added
# to badges.json without updating this) sorts after these by code.
DISPLAY_ORDER = ["first_attendance", "world_traveler", "concert_veteran", "memory_keeper"]


def _award(user_id, code):
    """Grant `code` to `user_id` unless they already have it (or the badge
    isn't seeded yet). Returns the UserBadge row if one was newly created.
    """
    badge = Badge.query.filter_by(code=code).first()
    if badge is None:
        return None

    already = UserBadge.query.filter_by(user_id=user_id, badge_id=badge.id).first()
    if already is not None:
        return None

    user_badge = UserBadge(user_id=user_id, badge_id=badge.id)
    db.session.add(user_badge)
    return user_badge


class BadgeService:
    @staticmethod
    def evaluate_attendance(user_id):
        """Call after a new Attendance row is added for user_id."""
        attendance_count = Attendance.query.filter_by(user_id=user_id).count()

        if attendance_count >= 1:
            _award(user_id, "first_attendance")

        if attendance_count >= CONCERT_VETERAN_THRESHOLD:
            _award(user_id, "concert_veteran")

        user = db.session.get(User, user_id)
        if user is not None and user.country:
            attended_elsewhere = (
                db.session.query(Attendance)
                .join(Concert, Concert.id == Attendance.concert_id)
                .filter(Attendance.user_id == user_id, Concert.country != user.country)
                .first()
            )
            if attended_elsewhere is not None:
                _award(user_id, "world_traveler")

    @staticmethod
    def evaluate_memory(user_id):
        """Call after a new Memory row is added for user_id."""
        memory_count = Memory.query.filter_by(user_id=user_id).count()
        if memory_count >= MEMORY_KEEPER_THRESHOLD:
            _award(user_id, "memory_keeper")

    @staticmethod
    def progress_for_user(user_id):
        """Every catalog badge annotated with this user's earn status and,
        for count-based badges, progress toward the threshold. Used by the
        badges screen to render locked tiles with a progress bar rather
        than just a yes/no.

        Mirrors the thresholds in evaluate_attendance/evaluate_memory
        above — keep both in sync if a rule changes.
        """
        attendance_count = Attendance.query.filter_by(user_id=user_id).count()
        memory_count = Memory.query.filter_by(user_id=user_id).count()

        user = db.session.get(User, user_id)
        attended_elsewhere = False
        if user is not None and user.country:
            attended_elsewhere = (
                db.session.query(Attendance)
                .join(Concert, Concert.id == Attendance.concert_id)
                .filter(Attendance.user_id == user_id, Concert.country != user.country)
                .first()
                is not None
            )

        progress_by_code = {
            "first_attendance": (attendance_count, 1),
            "world_traveler": (1 if attended_elsewhere else 0, 1),
            "concert_veteran": (attendance_count, CONCERT_VETERAN_THRESHOLD),
            "memory_keeper": (memory_count, MEMORY_KEEPER_THRESHOLD),
        }

        earned_at_by_badge_id = {
            ub.badge_id: ub.earned_at
            for ub in UserBadge.query.filter_by(user_id=user_id).all()
        }

        def sort_key(badge):
            try:
                return (0, DISPLAY_ORDER.index(badge.code))
            except ValueError:
                return (1, badge.code)

        results = []
        for badge in sorted(Badge.query.all(), key=sort_key):
            current, target = progress_by_code.get(badge.code, (0, 1))
            results.append(
                {
                    "badge": badge,
                    "earned_at": earned_at_by_badge_id.get(badge.id),
                    "current": min(current, target),
                    "target": target,
                }
            )
        return results