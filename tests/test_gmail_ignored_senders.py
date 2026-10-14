from integrations.providers.gmail import is_ignored_sender


def test_known_promotional_senders_are_ignored():
    assert is_ignored_sender("Fiverr <no-reply@announce.fiverr.com>") == "announce.fiverr.com"
    assert is_ignored_sender("Upwork <upwork@email.upwork.com>") == "email.upwork.com"


def test_real_clients_and_other_upwork_mail_are_not_ignored(monkeypatch):
    assert is_ignored_sender("Client <buyer@example.com>") == ""
    assert is_ignored_sender("Upwork <donotreply@upwork.com>") == ""
    assert is_ignored_sender("") == ""


def test_env_extension(monkeypatch):
    monkeypatch.setenv("GMAIL_IGNORE_SENDERS", "news.example.com, spam@x.org")
    assert is_ignored_sender("a@mail.news.example.com") == "news.example.com"
    assert is_ignored_sender("spam@x.org") == "spam@x.org"
