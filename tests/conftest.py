from datetime import date

import pytest

from basketball_tracker.models import ShootingSession


@pytest.fixture
def session() -> ShootingSession:
    return ShootingSession(date(2020, 1, 2), "Ray", 8, 10, 12, 20, 5, 15)
