from __future__ import annotations


def _login_as_depot_controller(client):
    response = client.post(
        "/auth/login",
        data={"email": "depot.controller@borderflow.local", "password": "borderflow123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/dashboard" in response.headers["location"]


def test_depot_controller_can_log_in_and_open_dashboard(client):
    _login_as_depot_controller(client)

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Site Dashboard" in dashboard.text
    assert "Container states" in dashboard.text


def test_border_agent_cannot_log_into_depot_site(client):
    response = client.post(
        "/auth/login",
        data={"email": "border.agent@borderflow.local", "password": "borderflow123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/auth/login" in response.headers["location"]
    assert "different+site" in response.headers["location"]


def test_depot_controller_can_register_client_vehicle_and_driver(client):
    _login_as_depot_controller(client)

    client_response = client.post(
        "/clients",
        data={
            "company_name": "Maluti Exports",
            "contact_name": "Lebo Mokoena",
            "contact_email": "ops@malutiexports.example",
            "contact_phone": "+266-5000-2000",
            "country": "Lesotho",
        },
        follow_redirects=False,
    )
    assert client_response.status_code == 303
    assert "/clients" in client_response.headers["location"]
    assert "Maluti Exports" in client.get("/clients").text

    vehicle_response = client.post(
        "/vehicles",
        data={"registration_no": "BFL-900-LS", "vehicle_type": "REEFER", "capacity_teu": 3},
        follow_redirects=False,
    )
    assert vehicle_response.status_code == 303
    assert "/vehicles" in vehicle_response.headers["location"]
    assert "BFL-900-LS" in client.get("/vehicles").text

    driver_response = client.post(
        "/drivers",
        data={
            "full_name": "Puleng Driver",
            "email": "puleng.driver@borderflow.local",
            "password": "borderflow123",
            "licence_no": "LS-CDL-22002",
            "licence_expiry": "2029-01-31",
        },
        follow_redirects=False,
    )
    assert driver_response.status_code == 303
    assert "/drivers" in driver_response.headers["location"]
    assert "Puleng Driver" in client.get("/drivers").text


def test_site_can_register_non_demo_user_and_that_user_can_log_in(client):
    _login_as_depot_controller(client)

    create_user_response = client.post(
        "/users",
        data={
            "full_name": "Mpho Yard Clerk",
            "email": "mpho.yard@borderflow.local",
            "password": "borderflow123",
            "role": "YARD_CLERK",
        },
        follow_redirects=False,
    )
    assert create_user_response.status_code == 303
    assert "/users" in create_user_response.headers["location"]
    assert "Mpho Yard Clerk" in client.get("/users").text

    client.post("/auth/logout", follow_redirects=False)
    login_response = client.post(
        "/auth/login",
        data={"email": "mpho.yard@borderflow.local", "password": "borderflow123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert "/dashboard" in login_response.headers["location"]


def test_public_signup_creates_site_user_and_signs_them_in(client):
    signup_response = client.post(
        "/auth/register",
        data={
            "full_name": "Line Supervisor",
            "email": "line.supervisor@borderflow.local",
            "password": "borderflow123",
            "role": "YARD_CLERK",
        },
        follow_redirects=False,
    )
    assert signup_response.status_code == 303
    assert "/dashboard" in signup_response.headers["location"]

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Line Supervisor" in dashboard.text


def test_public_signup_can_create_driver_account(client):
    signup_response = client.post(
        "/auth/register",
        data={
            "full_name": "Public Driver",
            "email": "public.driver@borderflow.local",
            "password": "borderflow123",
            "role": "DRIVER",
            "licence_no": "LS-CDL-44001",
            "licence_expiry": "2030-12-31T00:00:00",
        },
        follow_redirects=False,
    )
    assert signup_response.status_code == 303
    assert "/dashboard" in signup_response.headers["location"]

    client.post("/auth/logout", follow_redirects=False)
    login_response = client.post(
        "/auth/login",
        data={"email": "public.driver@borderflow.local", "password": "borderflow123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 303
    assert "/dashboard" in login_response.headers["location"]
