import json

from compute import persist_work_result


def test_persist_work_result_writes_expected_payload(tmp_path):
    task_id = "task-123"
    peer_id = "peer-abc"
    proofs = [{"index": 1, "logitHash": "deadbeef", "timestamp": 1, "nodeSignature": ""}]

    outbox_dir = tmp_path / "data" / "outbox"
    public_key = "abcd"
    file_path = persist_work_result(
        task_id,
        peer_id,
        proofs,
        outbox_dir=outbox_dir,
        public_key=public_key,
    )

    assert file_path.exists()
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    assert payload["taskId"] == task_id
    assert payload["peerId"] == peer_id
    assert payload["proofOfLogits"] == proofs
    assert payload["publicKey"] == public_key
