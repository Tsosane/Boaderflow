from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.enums import MilestoneType, TripStatus
from app.models import AppUser, Client, Consignment, Container, Driver, Milestone, Site, Trip, TripContainer, Vehicle
from app.services.projections import load_container_states, refresh_projection_cache
from app.services.rules import (
    BusinessRuleError,
    ensure_container_not_on_active_trip,
    ensure_driver_not_on_active_trip,
    ensure_milestone_allowed,
    ensure_vehicle_not_on_active_trip,
)


def _seeded(session, model, **filters):
    return session.scalar(select(model).filter_by(**filters))


def _create_trip_flow(session):
    depot_user = _seeded(session, AppUser, email="depot.controller@borderflow.local")
    client = _seeded(session, Client, contact_email="client@acmetextiles.example")
    vehicle = _seeded(session, Vehicle, registration_no="BFL-401-LS")
    driver = session.scalar(select(Driver).join(Driver.user).where(AppUser.email == "driver@borderflow.local"))
    hub_site = _seeded(session, Site, code="HUB-JHB")

    consignment = Consignment(
        client_id=client.id,
        origin_site_id=depot_user.site_id,
        destination_site_id=hub_site.id,
        origin_site_code="DEPOT-MSU",
        reference_no="BF-TEST-001",
        created_by_id=depot_user.id,
    )
    session.add(consignment)
    session.flush()

    container = Container(
        consignment_id=consignment.id,
        origin_site_code="DEPOT-MSU",
        container_no="MSCU7654321",
        container_type="40FT_HC",
        created_by_id=depot_user.id,
    )
    session.add(container)
    session.flush()

    trip = Trip(
        origin_site_id=depot_user.site_id,
        destination_site_id=hub_site.id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin_site_code="DEPOT-MSU",
        status=TripStatus.DEPARTED.value,
        planned_departure=datetime.now(timezone.utc),
        actual_departure=datetime.now(timezone.utc),
        created_by_id=depot_user.id,
    )
    session.add(trip)
    session.flush()

    assignment = TripContainer(
        trip_id=trip.id,
        container_id=container.id,
        origin_site_code="DEPOT-MSU",
        assigned_by_id=depot_user.id,
        active_assignment=True,
    )
    session.add(assignment)

    milestone = Milestone(
        trip_id=trip.id,
        container_id=container.id,
        site_id=depot_user.site_id,
        recorded_by_id=depot_user.id,
        origin_site_code="DEPOT-MSU",
        milestone_type=MilestoneType.DEPARTED.value,
        milestone_time=datetime.now(timezone.utc),
    )
    session.add(milestone)
    session.commit()
    return trip, container


def test_container_cannot_be_assigned_to_two_active_trips(session):
    _, container = _create_trip_flow(session)
    with pytest.raises(BusinessRuleError):
        ensure_container_not_on_active_trip(session, container.id)


def test_vehicle_and_driver_cannot_be_reused_on_active_trip(session):
    trip, _ = _create_trip_flow(session)

    with pytest.raises(BusinessRuleError):
        ensure_vehicle_not_on_active_trip(session, trip.vehicle_id)

    with pytest.raises(BusinessRuleError):
        ensure_driver_not_on_active_trip(session, trip.driver_id)


def test_milestone_order_is_enforced(session):
    trip, container = _create_trip_flow(session)

    ensure_milestone_allowed(
        session,
        trip_id=trip.id,
        container_id=container.id,
        milestone_type=MilestoneType.ARRIVED,
        site_code="BORDER-MB",
    )

    with pytest.raises(BusinessRuleError):
        ensure_milestone_allowed(
            session,
            trip_id=trip.id,
            container_id=container.id,
            milestone_type=MilestoneType.DELIVERED,
            site_code="HUB-JHB",
        )


def test_projection_cache_uses_latest_milestone(session):
    trip, container = _create_trip_flow(session)
    _ = trip
    refresh_projection_cache(session)
    session.commit()

    states = load_container_states(session)
    row = next(item for item in states if item["container_id"] == container.id)
    assert row["current_status"] == MilestoneType.DEPARTED.value
    assert row["container_no"] == "MSCU7654321"
