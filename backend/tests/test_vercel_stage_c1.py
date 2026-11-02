import os
import sys
import json
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from api.index import app

@pytest.mark.asyncio
async def test_vercel_asgi_app_root():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "operational"

@pytest.mark.asyncio
async def test_vercel_asgi_app_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"

@pytest.mark.asyncio
async def test_vercel_asgi_openapi_spec():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/openapi.json")
        assert res.status_code == 200
        spec = res.json()
        assert "paths" in spec
        assert "/api/v1/health" in spec["paths"]

def test_vercel_config_structure():
    vercel_json = root_dir / "vercel.json"
    assert vercel_json.exists(), "vercel.json not found in root"
    with open(vercel_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    assert "rewrites" in config
    routes = [r["source"] for r in config["rewrites"]]
    assert any("/api/v1/:path*" in r for r in routes)

    req_file = root_dir / "api" / "requirements.txt"
    assert req_file.exists(), "api/requirements.txt not found"
