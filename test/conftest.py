import pytest

from ._util import *


@pytest.fixture(scope="session")
def source_data() -> pathlib.Path:
    path = pathlib.Path(__file__).parent.joinpath("data")
    hash_list = save_files_hash_and_mtime(path)
    yield path
    assert cmp_files_hash_and_time(path, hash_list) < 100


@pytest.fixture(scope="session")
def project_folder(tmp_path_factory) -> pathlib.Path:
    tmp_dir = tmp_path_factory.mktemp("project", numbered=False)
    return tmp_dir
