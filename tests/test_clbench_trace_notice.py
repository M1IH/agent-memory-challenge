from benchmarks.probe_clbench_trace_memory import NOTICE, is_environment_change_notice


def test_explicit_environment_change_notice_is_detected():
    assert is_environment_change_notice("user", NOTICE)
    assert is_environment_change_notice(
        "user", "IMPORTANT: The tool configuration has been updated; recheck assumptions."
    )


def test_ordinary_discussion_and_tool_output_do_not_start_new_epoch():
    assert not is_environment_change_notice(
        "user", "Has the database changed since our previous discussion?"
    )
    assert not is_environment_change_notice(
        "tool", "NOTICE: The database schema has changed."
    )
    assert not is_environment_change_notice(
        "user", "NOTICE: The meeting time has changed."
    )
