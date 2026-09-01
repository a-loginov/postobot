import config


def test_default_user_is_not_admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", [1, 2, 3])
    assert config.is_admin(2) is True
    assert config.is_admin(4) is False


def test_admin_ids_parsed_as_ints(monkeypatch):
    # Simulate parsing of ADMIN_IDS env value as a comma-separated list of ints
    from config import ADMIN_IDS as _original  # noqa: F401

    raw = "123456789,987654321"
    parsed = [int(x.strip()) for x in raw.split(",") if x.strip()]
    monkeypatch.setattr(config, "ADMIN_IDS", parsed)
    assert config.is_admin(123456789) is True
    assert config.is_admin(987654321) is True


def test_admin_filter_blocks_regular_user(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", [777])
    from bot.filters.admin import IsAdminFilter

    class FakeUser:
        id = 555

    class FakeMessage:
        def __init__(self):
            self.from_user = FakeUser()

    import asyncio

    result = asyncio.run(IsAdminFilter().__call__(FakeMessage()))
    assert result is False


def test_admin_filter_allows_admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", [777])
    from bot.filters.admin import IsAdminFilter

    class FakeUser:
        id = 777

    class FakeMessage:
        def __init__(self):
            self.from_user = FakeUser()

    import asyncio

    result = asyncio.run(IsAdminFilter().__call__(FakeMessage()))
    assert result is True
