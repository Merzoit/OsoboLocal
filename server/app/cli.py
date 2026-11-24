from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from uuid import UUID

from app.config import get_settings
from app.db.migrate import upgrade_head
from app.db.models import DeviceRegistrationCode, Station
from app.db.session import create_engine_from_url, get_session_factory, session_scope
from app.ids import new_uuid
from app.security import generate_registration_code, sha256_hex
from app.timeutil import utcnow

ROLES = ("kiosk", "station", "expo", "operator")


def cmd_create_registration_code(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = get_session_factory(engine)

    if args.role not in ROLES:
        print(f"Invalid role: {args.role}. Expected one of {ROLES}", file=sys.stderr)
        return 1

    station_id = UUID(args.station_id) if args.station_id else None
    code = generate_registration_code()
    now = utcnow()
    expires_at = now + timedelta(hours=args.expires_hours)

    with session_scope(factory) as session:
        if station_id is not None:
            station = session.get(Station, station_id)
            if station is None:
                print(f"Station not found: {station_id}", file=sys.stderr)
                return 1
        if args.role == "station" and station_id is None:
            print("station role requires --station-id", file=sys.stderr)
            return 1

        session.add(
            DeviceRegistrationCode(
                id=new_uuid(),
                code_hash=sha256_hex(code),
                role=args.role,
                station_id=station_id,
                expires_at=expires_at,
                used_at=None,
                created_at=now,
            )
        )

    print(code)
    return 0


def cmd_migrate(_args: argparse.Namespace) -> int:
    settings = get_settings()
    upgrade_head(settings.database_url)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ososbo", description="Ososbo server CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser("migrate", help="Apply Alembic migrations to head")
    migrate.set_defaults(func=cmd_migrate)

    reg = sub.add_parser("create-registration-code", help="Create a one-time device code")
    reg.add_argument("--role", required=True, choices=ROLES)
    reg.add_argument("--station-id", default=None, help="Required for station role")
    reg.add_argument("--expires-hours", type=int, default=24)
    reg.set_defaults(func=cmd_create_registration_code)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
