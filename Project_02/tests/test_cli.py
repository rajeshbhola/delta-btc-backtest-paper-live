from main import main
from quality_lab.json_store import JsonStore

def test_cli_demo_and_process(tmp_path, capsys):
    base = str(tmp_path / "market")
    assert main(["--data-dir", base, "demo", "--days", "2"]) == 0
    assert main(["--data-dir", base, "process", "--days", "2"]) == 0
    assert JsonStore(base).read_report("5m") is not None
    assert "coverage=" in capsys.readouterr().out
