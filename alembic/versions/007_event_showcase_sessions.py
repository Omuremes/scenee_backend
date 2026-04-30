"""event_showcase_sessions

Revision ID: 007
Revises: ed63303825ce
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "007"
down_revision = "ed63303825ce"
branch_labels = None
depends_on = None


old_event_type_enum = postgresql.ENUM(
    "MOVIE_SCREENING",
    "CONCERT",
    "THEATER",
    "STANDUP",
    "SPORT",
    name="eventtype",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "event_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    op.add_column("events", sa.Column("type", sa.String(length=50), nullable=True))
    op.add_column("events", sa.Column("poster_url", sa.String(length=1000), nullable=True))
    op.add_column("events", sa.Column("trailer_url", sa.String(length=1000), nullable=True))
    op.add_column("events", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("events", sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_events_category_id_event_categories",
        "events",
        "event_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column(
        "events",
        "event_type",
        existing_type=old_event_type_enum,
        type_=sa.String(length=50),
        existing_nullable=False,
        nullable=True,
        postgresql_using="event_type::text",
    )

    op.execute(
        """
        UPDATE events
        SET
            type = CASE lower(event_type)
                WHEN 'movie_screening' THEN 'cinema'
                WHEN 'concert' THEN 'concerts'
                WHEN 'standup' THEN 'stand-up'
                WHEN 'sport' THEN 'sports'
                WHEN 'theater' THEN 'events'
                ELSE COALESCE(lower(event_type), 'events')
            END,
            poster_url = COALESCE(events.poster_url, events.image_url),
            city = COALESCE(events.city, venues.city, '')
        FROM venues
        WHERE events.venue_id = venues.id
        """
    )
    op.execute("UPDATE events SET type = COALESCE(type, 'events'), city = COALESCE(city, '')")
    op.execute("UPDATE events SET event_type = type")

    op.alter_column("events", "type", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("events", "city", existing_type=sa.String(length=100), nullable=False)
    op.alter_column("events", "start_datetime", existing_type=sa.DateTime(), nullable=True)
    op.alter_column("events", "venue_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("events", "price", existing_type=sa.Float(), nullable=True)
    op.alter_column("events", "max_capacity", existing_type=sa.Integer(), nullable=True)
    op.alter_column("events", "available_seats", existing_type=sa.Integer(), nullable=True)

    op.create_index(op.f("ix_events_type"), "events", ["type"], unique=False)
    op.create_index(op.f("ix_events_city"), "events", ["city"], unique=False)
    op.create_index(op.f("ix_events_category_id"), "events", ["category_id"], unique=False)

    op.create_table(
        "event_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("base_price", sa.Float(), nullable=False),
        sa.Column("pricing_type", sa.String(length=20), nullable=False),
        sa.Column("cinema_name", sa.String(length=255), nullable=True),
        sa.Column("hall_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("base_price >= 0", name="ck_event_session_base_price"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_sessions_event_id"), "event_sessions", ["event_id"], unique=False)
    op.create_index(op.f("ix_event_sessions_starts_at"), "event_sessions", ["starts_at"], unique=False)

    op.execute(
        """
        INSERT INTO event_sessions (
            id, event_id, starts_at, ends_at, base_price, pricing_type, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            id,
            COALESCE(start_datetime, created_at, now()),
            end_datetime,
            COALESCE(price, 0),
            'fixed',
            COALESCE(created_at, now()),
            updated_at
        FROM events
        WHERE NOT EXISTS (
            SELECT 1 FROM event_sessions WHERE event_sessions.event_id = events.id
        )
        """
    )

    op.create_table(
        "event_seats",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("zone", sa.String(length=100), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("price >= 0", name="ck_event_seat_price"),
        sa.ForeignKeyConstraint(["session_id"], ["event_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "label", name="uq_event_seat_session_label"),
    )
    op.create_index(op.f("ix_event_seats_session_id"), "event_seats", ["session_id"], unique=False)

    op.add_column("bookings", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("bookings", sa.Column("seat_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_bookings_session_id_event_sessions",
        "bookings",
        "event_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bookings_seat_id_event_seats",
        "bookings",
        "event_seats",
        ["seat_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_bookings_seat_id_event_seats", "bookings", type_="foreignkey")
    op.drop_constraint("fk_bookings_session_id_event_sessions", "bookings", type_="foreignkey")
    op.drop_column("bookings", "seat_id")
    op.drop_column("bookings", "session_id")

    op.drop_index(op.f("ix_event_seats_session_id"), table_name="event_seats")
    op.drop_table("event_seats")
    op.drop_index(op.f("ix_event_sessions_starts_at"), table_name="event_sessions")
    op.drop_index(op.f("ix_event_sessions_event_id"), table_name="event_sessions")
    op.drop_table("event_sessions")

    op.drop_index(op.f("ix_events_category_id"), table_name="events")
    op.drop_index(op.f("ix_events_city"), table_name="events")
    op.drop_index(op.f("ix_events_type"), table_name="events")
    op.drop_constraint("fk_events_category_id_event_categories", "events", type_="foreignkey")

    op.alter_column("events", "available_seats", existing_type=sa.Integer(), nullable=False)
    op.alter_column("events", "max_capacity", existing_type=sa.Integer(), nullable=False)
    op.alter_column("events", "price", existing_type=sa.Float(), nullable=False)
    op.alter_column("events", "venue_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column("events", "start_datetime", existing_type=sa.DateTime(), nullable=False)

    op.alter_column(
        "events",
        "event_type",
        existing_type=sa.String(length=50),
        type_=old_event_type_enum,
        existing_nullable=True,
        nullable=False,
        postgresql_using=(
            "CASE event_type "
            "WHEN 'cinema' THEN 'MOVIE_SCREENING' "
            "WHEN 'concerts' THEN 'CONCERT' "
            "WHEN 'stand-up' THEN 'STANDUP' "
            "WHEN 'sports' THEN 'SPORT' "
            "ELSE 'THEATER' END::eventtype"
        ),
    )

    op.drop_column("events", "category_id")
    op.drop_column("events", "city")
    op.drop_column("events", "trailer_url")
    op.drop_column("events", "poster_url")
    op.drop_column("events", "type")
    op.drop_table("event_categories")
