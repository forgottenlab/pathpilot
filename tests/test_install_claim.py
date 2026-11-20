from __future__ import annotations

import multiprocessing
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.json_store import JsonStoreError, update_json
from app.core.paths import get_pending_installs_path
from app.installers.queue import (
    add_install_suggestion,
    claim_install_suggestion,
    finish_install_claim,
    load_pending_installs,
    prepare_install_launch,
    skip_install_suggestion,
)
from app.installers.runner import run_install_record
from app.installers.strategy import build_suggestion_from_family, rebuild_execution_fields


@pytest.fixture
def suggestion(runtime_paths):
    installers = Path(runtime_paths["archive_root"]) / "01-Software" / "_IncomingInstallers"
    installers.mkdir(parents=True)
    installer = installers / "Example Setup.exe"
    installer.write_bytes(b"inert test fixture")
    record = add_install_suggestion(build_suggestion_from_family(
        installer, {"family": "inno_setup"}, runtime_paths,
    ))
    return record, {"apps_root": runtime_paths["apps_root"], "installers_root": installers}


def _compete(record, roots, start, competitor_done, results):
    attempts = []

    def mock_launch(argv, *, shell):
        persisted, = load_pending_installs()
        attempts.append((persisted["status"], persisted.get("claim_id"), shell))
        # Keep the winner inside Popen until the losing runner has returned.
        assert competitor_done.wait(timeout=15)
        return object()

    with patch("app.installers.runner.subprocess.Popen", mock_launch):
        start.wait(timeout=15)
        launched = run_install_record(record, **roots)
    competitor_done.set()
    results.put((launched, attempts))


def test_two_processes_contend_for_one_launch(suggestion):
    record, roots = suggestion
    ctx = multiprocessing.get_context("spawn")
    results = ctx.Queue()
    args = (record, roots, ctx.Barrier(2), ctx.Event(), results)
    processes = [ctx.Process(target=_compete, args=args) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=35)
            assert process.exitcode == 0
        outcomes = [results.get(timeout=5) for _ in processes]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()

    final, = load_pending_installs()
    assert final["status"] == "launched"
    assert final["claim_id"]
    assert sorted(launched for launched, _ in outcomes) == [False, True]
    assert [attempt for _, calls in outcomes for attempt in calls] == [
        ("launching", final["claim_id"], False),
    ]
    assert claim_install_suggestion(record["id"]) is None
    assert skip_install_suggestion(record["id"]) is None
    assert load_pending_installs() == [final]


def test_claim_owner_and_phase_guard_every_transition(suggestion):
    record, roots = suggestion
    record_id = record["id"]
    claimed = claim_install_suggestion(record_id)
    assert claimed["status"] == "claimed"
    owner = claimed["claim_id"]
    assert owner
    fields = rebuild_execution_fields(claimed, claimed["target_dir"])
    assert claim_install_suggestion(record_id) is None
    assert skip_install_suggestion(record_id) is None
    assert prepare_install_launch(record_id, "other-attempt", fields) is None
    assert finish_install_claim(record_id, "other-attempt", "blocked") is None
    assert finish_install_claim(record_id, owner, "launched") is None
    assert load_pending_installs() == [claimed]

    launching = prepare_install_launch(record_id, owner, fields)
    assert launching["status"] == "launching"
    # A runner that died here may already have created the process.
    with patch("app.installers.runner.subprocess.Popen") as launch:
        assert not run_install_record(record, **roots)
        launch.assert_not_called()
    assert finish_install_claim(record_id, "other-attempt", "launch_failed") is None
    assert prepare_install_launch(record_id, owner, fields) is None
    assert load_pending_installs() == [launching]
    assert finish_install_claim(record_id, owner, "launched")["status"] == "launched"
    assert finish_install_claim(record_id, owner, "launch_failed") is None


@pytest.mark.parametrize(("error", "status"), [
    (OSError("simulated process creation failure"), "launch_failed"),
    (RuntimeError("simulated ambiguous launch outcome"), "launch_unknown"),
])
def test_launch_error_cannot_be_retried(suggestion, error, status):
    record, roots = suggestion
    with patch("app.installers.runner.subprocess.Popen", side_effect=error) as launch:
        assert not run_install_record(record, **roots)
        persisted, = load_pending_installs()
        assert persisted["status"] == status
        assert not run_install_record(record, **roots)
        launch.assert_called_once()
    assert load_pending_installs() == [persisted]


def test_stale_pending_cannot_launch_after_skip(suggestion):
    record, roots = suggestion
    skipped = skip_install_suggestion(record["id"])
    assert skipped["status"] == "skipped"
    with patch("app.installers.runner.subprocess.Popen") as launch:
        assert not run_install_record(record, **roots)
        launch.assert_not_called()
    assert load_pending_installs() == [skipped]


def test_successful_launch_with_unwritable_result_cannot_be_retried(suggestion):
    record, roots = suggestion
    with patch("app.installers.runner.subprocess.Popen") as launch:
        with patch(
            "app.installers.runner.finish_install_claim",
            side_effect=JsonStoreError("simulated result write failure"),
        ) as finish:
            with pytest.raises(JsonStoreError):
                run_install_record(record, **roots)

        persisted, = load_pending_installs()
        assert persisted["status"] == "launching"
        finish.assert_called_once_with(record["id"], persisted["claim_id"], "launched")
        assert not run_install_record(record, **roots)
        launch.assert_called_once()
    assert load_pending_installs() == [persisted]


def test_stale_safe_snapshot_cannot_bypass_persisted_path(suggestion, tmp_path):
    record, roots = suggestion
    outside = tmp_path / "outside.exe"
    outside.write_bytes(b"inert test fixture")
    update_json(
        get_pending_installs_path(),
        lambda items: items[0].update(installer_path=str(outside)),
        default=[],
        expected_type=list,
    )
    with patch("app.installers.runner.subprocess.Popen") as launch:
        assert not run_install_record(record, **roots)
        launch.assert_not_called()
    current, = load_pending_installs()
    assert current["status"] == "pending"
    assert current["installer_path"] == str(outside)
