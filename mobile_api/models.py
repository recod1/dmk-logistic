from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mobile_api.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False, default="driver", index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    legacy_tg_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    routes: Mapped[list[Route]] = relationship(
        back_populates="assignee",
        foreign_keys="Route.assigned_user_id",
    )
    created_routes: Mapped[list[Route]] = relationship(
        back_populates="created_by",
        foreign_keys="Route.created_by_user_id",
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")
    web_push_subscriptions: Mapped[list["WebPushSubscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    legacy_driver_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default="new")
    number_auto: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    temperature: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    dispatcher_contacts: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    registration_number: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    trailer_number: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    assignee: Mapped[User | None] = relationship(
        back_populates="routes",
        foreign_keys=[assigned_user_id],
    )
    created_by: Mapped[User | None] = relationship(
        back_populates="created_routes",
        foreign_keys=[created_by_user_id],
    )
    points: Mapped[list[Point]] = relationship(back_populates="route")
    ordered_points: Mapped[list[RoutePoint]] = relationship(
        back_populates="route",
        order_by="RoutePoint.order_index",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="route")


class Point(Base):
    __tablename__ = "points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    type_point: Mapped[str] = mapped_column(String(32), nullable=False)
    place_point: Mapped[str] = mapped_column(Text, nullable=False)
    date_point: Mapped[str] = mapped_column(String(64), nullable=False)
    point_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    point_contacts: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    point_time: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    point_note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")

    time_accepted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_registration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_put_on_gate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_docs: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    photo_docs: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Новая модель этапов точки рейса для PWA:
    # выезд -> регистрация -> ворота -> документы.
    departure_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    departure_odometer: Mapped[str | None] = mapped_column(Text, nullable=True)
    departure_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    departure_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    registration_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_odometer: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    registration_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    gate_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gate_odometer: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gate_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    docs_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    docs_odometer: Mapped[str | None] = mapped_column(Text, nullable=True)
    docs_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    docs_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default="new")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    odometer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    route: Mapped[Route] = relationship(back_populates="points")
    route_links: Mapped[list[RoutePoint]] = relationship(back_populates="point")
    events: Mapped[list[RouteEvent]] = relationship(back_populates="point")
    notifications: Mapped[list[Notification]] = relationship(back_populates="point")
    document_images: Mapped[list["PointDocumentImage"]] = relationship(
        back_populates="point",
        cascade="all, delete-orphan",
    )


class PointDocumentImage(Base):
    __tablename__ = "point_document_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    point_id: Mapped[int] = mapped_column(
        ForeignKey("points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_id: Mapped[str] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    point: Mapped[Point] = relationship(back_populates="document_images")


class RoutePoint(Base):
    __tablename__ = "route_points"
    __table_args__ = (
        UniqueConstraint("route_id", "point_id", name="uq_route_points_route_point"),
        UniqueConstraint("route_id", "order_index", name="uq_route_points_route_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    point_id: Mapped[int] = mapped_column(ForeignKey("points.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    route: Mapped[Route] = relationship(back_populates="ordered_points")
    point: Mapped[Point] = relationship(back_populates="route_links")


class RouteEvent(Base):
    __tablename__ = "route_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "device_id",
            "client_event_id",
            name="uq_route_events_user_device_event",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    point_id: Mapped[int] = mapped_column(ForeignKey("points.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    client_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at_client: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    point: Mapped[Point] = relationship(back_populates="events")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id: Mapped[str | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    point_id: Mapped[int | None] = mapped_column(
        ForeignKey("points.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user: Mapped[User] = relationship(back_populates="notifications")
    route: Mapped[Route | None] = relationship(back_populates="notifications")
    point: Mapped[Point | None] = relationship(back_populates="notifications")


class WebPushSubscription(Base):
    __tablename__ = "web_push_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "endpoint", name="uq_web_push_user_endpoint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="web_push_subscriptions")


class Salary(Base):
    __tablename__ = "salary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_driver: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date_salary: Mapped[str] = mapped_column(String(64), nullable=False)
    type_route: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default="")
    sum_status: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_daily: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    load_2_trips: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    calc_shuttle: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_load_unload: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_curtain: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_return: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_add_shuttle: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_add_point: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_gas_station: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    pallets_hyper: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pallets_metro: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pallets_ashan: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_3km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    rate_3_5km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    rate_5km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    rate_10km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    rate_12km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    rate_12_5km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    mileage: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_cell_compensation: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    percent_10: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_bonus: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    withhold: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    compensation: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    dr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_without_daily_dr_bonus_exp: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sum_without_daily_dr_bonus: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    load_address: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    unload_address: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    transport: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    trailer_number: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    route_number: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    status_driver: Mapped[str] = mapped_column(String(32), nullable=False, default=" ", server_default=" ")
    comment_driver: Mapped[str] = mapped_column(Text, nullable=False, default=" ", server_default=" ")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Repair(Base):
    __tablename__ = "repair"

    id_ticket: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    tg_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    number_auto: Mapped[str] = mapped_column(String(64), nullable=False)
    malfunction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new", server_default="new")
    date_repair: Mapped[str] = mapped_column(String(64), nullable=False, default="0", server_default="0")
    place_repair: Mapped[str] = mapped_column(Text, nullable=False, default="0", server_default="0")
    comment_repair: Mapped[str] = mapped_column(Text, nullable=False, default="0", server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

