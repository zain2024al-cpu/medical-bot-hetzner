# modules/residency/repository.py
# استعلامات القراءة على res_profiles/res_companions — المرحلة الأولى فقط.

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProfileRow:
    id: int
    name: str
    photo_file_id: str
    reminder_date: str
    reminder_active: bool
    submitted: bool
    companions: list[str] = field(default_factory=list)


def get_pending_profiles() -> list[ProfileRow]:
    """كل الملفات التي لم يُقدَّم طلبها بعد (submitted=False) — أحدث أولاً."""
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    rows: list[ProfileRow] = []
    with get_db() as db:
        profiles = (
            db.query(ResidencyProfile)
            .filter_by(submitted=False)
            .order_by(ResidencyProfile.created_at.desc())
            .all()
        )
        for p in profiles:
            comps = db.query(ResidencyCompanion).filter_by(profile_id=p.id).all()
            rows.append(ProfileRow(
                id=p.id,
                name=p.name or "—",
                photo_file_id=p.photo_file_id or "",
                reminder_date=p.reminder_date or "",
                reminder_active=bool(p.reminder_active),
                submitted=bool(p.submitted),
                companions=[c.name for c in comps],
            ))
    return rows


def get_due_reminders() -> list[ProfileRow]:
    """ملفات reminder_active=True وsubmitted=False وتاريخ التنبيه اليوم أو قبله."""
    from datetime import date
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    today_iso = date.today().isoformat()
    rows: list[ProfileRow] = []
    with get_db() as db:
        profiles = (
            db.query(ResidencyProfile)
            .filter(
                ResidencyProfile.reminder_active == True,   # noqa: E712
                ResidencyProfile.submitted == False,         # noqa: E712
                ResidencyProfile.reminder_date != "",
                ResidencyProfile.reminder_date <= today_iso,
            )
            .order_by(ResidencyProfile.reminder_date.asc())
            .all()
        )
        for p in profiles:
            comps = db.query(ResidencyCompanion).filter_by(profile_id=p.id).all()
            rows.append(ProfileRow(
                id=p.id,
                name=p.name or "—",
                photo_file_id=p.photo_file_id or "",
                reminder_date=p.reminder_date or "",
                reminder_active=bool(p.reminder_active),
                submitted=bool(p.submitted),
                companions=[c.name for c in comps],
            ))
    return rows


def get_profile_by_id(profile_id: int) -> ProfileRow | None:
    from db.session import get_db
    from db.models import ResidencyProfile, ResidencyCompanion

    with get_db() as db:
        p = db.query(ResidencyProfile).filter_by(id=profile_id).first()
        if not p:
            return None
        comps = db.query(ResidencyCompanion).filter_by(profile_id=p.id).all()
        return ProfileRow(
            id=p.id,
            name=p.name or "—",
            photo_file_id=p.photo_file_id or "",
            reminder_date=p.reminder_date or "",
            reminder_active=bool(p.reminder_active),
            submitted=bool(p.submitted),
            companions=[c.name for c in comps],
        )
