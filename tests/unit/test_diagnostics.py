from app.diagnostics.checks import CheckLevel, run_all_checks


def test_run_all_checks_returns_every_check_with_a_valid_level(test_settings):
    checks = run_all_checks()

    assert len(checks) == 8
    for check in checks:
        assert check.level in set(CheckLevel)
        assert check.name
        assert check.detail
