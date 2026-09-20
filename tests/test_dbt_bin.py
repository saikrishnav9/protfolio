from pulse.transform import _dbt_bin


def test_dbt_cli_resolves_next_to_python():
    cmd = _dbt_bin()
    assert cmd
    assert "dbt" in cmd[0].lower() or cmd[-1].endswith("dbt.cli.main")
