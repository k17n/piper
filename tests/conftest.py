from __future__ import annotations

import pytest
from sqlmodel import Session

from piper_jobs.config import Settings
from piper_jobs.db import dispose_engine, get_engine


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(data_dir=tmp_path)
    yield s
    dispose_engine(s.db_path)


@pytest.fixture
def session(settings):
    with Session(get_engine(settings.db_path)) as s:
        yield s
