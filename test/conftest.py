import pytest

from ._util import *


def pytest_addoption(parser):
    parser.addoption("--no-load", action="store_true")
    parser.addoption("--project-folder", action="store", default=None)


@pytest.fixture(scope="session")
def cmdopt_no_load(request):
    return request.config.getoption("--no-load")


@pytest.fixture(scope="session")
def cmdopt_project_folder(request):
    return request.config.getoption("--project-folder")


@pytest.fixture(scope="session")
def source_data() -> pathlib.Path:
    path = pathlib.Path(__file__).parent.joinpath("data")
    hash_list = save_files_hash_and_mtime(path)
    yield path
    assert cmp_files_hash_and_time(path, hash_list) < 100


@pytest.fixture(scope="session")
def project_folder(cmdopt_project_folder, tmp_path_factory) -> pathlib.Path:
    if cmdopt_project_folder:
        folder = pathlib.Path(cmdopt_project_folder)
        if folder.parent.exists():
            if not folder.exists():
                folder.mkdir()
            return folder
        else:
            print("folder does not exist using tmp directory")

    return tmp_path_factory.mktemp("project", numbered=False)
