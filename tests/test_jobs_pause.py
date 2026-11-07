"""Per-queue pause is a separate switch from pausing every drain."""

from library.errors import AppError
from library.jobs import jobs_status, read_jobs_action


def test_one_queue_pause_is_named() -> None:
    assert read_jobs_action({"action": "pause", "queue": "infer-faces"}) == ("pause", "infer-faces")
    assert read_jobs_action({"action": "resume"}) == ("resume", None)


def test_unknown_queue_is_rejected() -> None:
    try:
        read_jobs_action({"action": "pause", "queue": "globe"})
    except AppError as exc:
        assert exc.code == "invalid-argument"
        return
    raise AssertionError("expected invalid-argument")


def test_paused_queue_is_marked_on_an_empty_library(tmp_path) -> None:
    status = jobs_status(tmp_path, paused=False, paused_queues={"rate"})
    assert status["queuePause"] is True
    assert status["pausedQueues"] == ["rate"]
    by_id = {queue["id"]: queue for queue in status["queues"]}
    assert by_id["rate"]["percent"] is None
    assert by_id["infer-faces"]["state"] == "idle"
