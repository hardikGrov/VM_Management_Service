from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_vm_lifecycle() -> None:
    create_response = client.post(
        "/vms",
        json={
            "name": "api-01",
            "image": "ubuntu-24.04",
            "cpu_count": 2,
            "memory_mb": 4096,
            "region": "us-east-1",
        },
    )

    assert create_response.status_code == 202
    accepted = create_response.json()
    assert accepted["status"] == "provisioning"

    task_response = client.get(f"/tasks/{accepted['task_id']}")
    assert task_response.status_code == 200
    assert task_response.json()["vm_id"] == accepted["vm_id"]

    status_response = client.get(f"/vms/{accepted['vm_id']}/status")
    assert status_response.status_code == 200
    assert status_response.json()["vm"]["state"] == "active"

    get_response = client.get(f"/vms/{accepted['vm_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == accepted["vm_id"]

    delete_response = client.delete(f"/vms/{accepted['vm_id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "VM deleted"


def test_missing_vm_returns_structured_error() -> None:
    response = client.get("/vms/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": "vm_not_found",
        "message": "VM 'missing' was not found.",
        "details": None,
    }
