import glob
import platform

pytest_plugins = []

for fixture_file in glob.glob("tests/fixtures/[!__]*.py", recursive=True):
    if platform.system() == "Windows":
        fixture_file = fixture_file.replace("\\", "/")  # noqa: PLW2901
    pytest_plugins.append(fixture_file.replace("/", ".").replace(".py", ""))
