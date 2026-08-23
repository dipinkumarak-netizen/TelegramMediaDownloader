"""Comprehensive REST API tests for authentication, dashboard, storage, and sources."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "telegram-downloader"
    assert "version" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_structured_error_responses(client: AsyncClient):
    # Test 404 endpoint returns valid JSON (never HTML)
    resp = await client.get("/api/nonexistent_endpoint_123")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    assert data["status"] == "error"
    assert "message" in data


@pytest.mark.asyncio
async def test_auth_setup_and_login_flow(client: AsyncClient, tmp_path):
    # 1. Check initial setup status
    status_resp = await client.get("/api/auth/setup-status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "is_setup_completed" in status_data

    # 2. Run Setup Wizard
    download_folder = str(tmp_path / "Downloads")
    setup_payload = {
      "username": "testadmin",
      "password": "TestPassword123!",
      "download_dir": download_folder,
      "telegram_api_id": 28941234,
      "telegram_api_hash": "test_hash_3a89e9d91f8",
      "telegram_phone": "+1234567890",
    }
    setup_resp = await client.post("/api/auth/setup", json=setup_payload)
    # If not yet completed:
    if setup_resp.status_code == 200:
        setup_res = setup_resp.json()
        assert setup_res["status"] == "success"
        token = setup_res["token"]
    else:
        # Already set up in earlier test, perform login
        login_resp = await client.post("/api/auth/login", json={"username": "testadmin", "password": "TestPassword123!"})
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]

    auth_headers = {"Authorization": f"Bearer {token}"}

    # 3. Test /api/auth/me
    me_resp = await client.get("/api/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "testadmin"

    # 4. Test Dashboard Stats
    dash_resp = await client.get("/api/dashboard/stats", headers=auth_headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert "system" in dash_data
    assert "downloads" in dash_data
    assert "storage" in dash_data

    # 5. Test Storage Drives
    storage_resp = await client.get("/api/storage/drives", headers=auth_headers)
    assert storage_resp.status_code == 200
    assert "drives" in storage_resp.json()

    # 6. Test Telegram Sources CRUD
    source_payload = {
      "telegram_id": "@test_public_channel",
      "title": "Test Public Channel",
      "download_videos": True,
      "download_documents": True,
    }
    src_create_resp = await client.post("/api/sources", json=source_payload, headers=auth_headers)
    assert src_create_resp.status_code == 200
    source_obj = src_create_resp.json()
    assert source_obj["telegram_id"] == "@test_public_channel"
    source_id = source_obj["id"]

    # List sources
    src_list_resp = await client.get("/api/sources", headers=auth_headers)
    assert src_list_resp.status_code == 200
    assert len(src_list_resp.json()) >= 1

    # Delete source
    src_del_resp = await client.delete(f"/api/sources/{source_id}", headers=auth_headers)
    assert src_del_resp.status_code == 200
