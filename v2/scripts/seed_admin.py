#!/usr/bin/env python3
"""Seed initial org owner — Phase 10C. Run after migrations on fresh install."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Allow running from repo root or inside api container
for candidate in (
    Path(__file__).resolve().parents[1] / "backend" / "src",
    Path("/app/src"),
):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from sqlalchemy import select

from auth_utils import hash_password
from db import Organization, User, async_session_factory, slugify_org_name


async def seed_admin(*, email: str, password: str, org_name: str) -> None:
    email = email.lower().strip()
    base_slug = slugify_org_name(org_name)
    slug = base_slug
    suffix = 0

    async with async_session_factory() as db:
        existing_user = await db.execute(select(User).where(User.email == email))
        if existing_user.scalar_one_or_none():
            print(f"User {email} already exists — skipping")
            return

        while True:
            clash = await db.execute(select(Organization).where(Organization.slug == slug))
            if not clash.scalar_one_or_none():
                break
            suffix += 1
            slug = f"{base_slug}-{suffix}"[:64]

        org = Organization(id=uuid.uuid4(), name=org_name.strip(), slug=slug)
        db.add(org)
        await db.flush()

        user = User(
            email=email,
            password_hash=hash_password(password),
            role="owner",
            org_id=org.id,
        )
        db.add(user)
        await db.commit()
        print(f"Created owner {email} in org '{org_name}' ({slug})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed admin owner user")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", "admin@local"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", ""))
    parser.add_argument("--org-name", default=os.environ.get("ORG_NAME", "Default Organization"))
    args = parser.parse_args()

    if len(args.password) < 8:
        print("ERROR: password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    asyncio.run(seed_admin(email=args.email, password=args.password, org_name=args.org_name))


if __name__ == "__main__":
    main()
