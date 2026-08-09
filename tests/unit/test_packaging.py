from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def test_cryptography_is_only_required_by_ssh_and_dev_extras():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    runtime_dependencies = pyproject["project"].get("dependencies", [])
    optional_dependencies = pyproject["project"]["optional-dependencies"]

    assert not any(dep.startswith("cryptography") for dep in runtime_dependencies)
    assert any(dep.startswith("cryptography") for dep in optional_dependencies["ssh"])
    assert any(dep.startswith("cryptography") for dep in optional_dependencies["dev"])
