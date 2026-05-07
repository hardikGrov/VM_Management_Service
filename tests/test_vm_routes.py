from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_vm_lifecycle() -> None:
    create_response = client.post(
        "/v1/vms",
        json={
            "name": "api-01",
            "image": "ubuntu-24.04",
            "cpu_count": 2,
            "memory_mb": 4096,
            "region": "us-east-1",
        },
    )

    assert create_response.status_code == 201
    vm = create_response.json()
    assert vm["state"] == "provisioned"

    get_response = client.get(f"/v1/vms/{vm['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == vm["id"]

    delete_response = client.delete(f"/v1/vms/{vm['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "VM deleted"


def test_missing_vm_returns_structured_error() -> None:
    response = client.get("/v1/vms/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": "vm_not_found",
        "message": "VM 'missing' was not found.",
        "details": None,
    }
