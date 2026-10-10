import pytest
from cryptography.fernet import Fernet

from integrations.token_store import EncryptedSupabaseTokenStore, TokenEncryptionError, build_gmail_token_store


class _Query:
    def __init__(self, rows, table): self.rows, self.table, self.filters, self.op, self.payload = rows, table, {}, None, None
    def select(self, *_): self.op = "select"; return self
    def upsert(self, row, on_conflict=None): self.op, self.payload = "upsert", row; return self
    def delete(self): self.op = "delete"; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def limit(self, _): return self
    def execute(self):
        match = lambda r: all(r.get(k) == v for k, v in self.filters.items())
        if self.op == "upsert":
            self.rows[:] = [r for r in self.rows if not (r["tenant_id"] == self.payload["tenant_id"] and r["provider"] == self.payload["provider"])] + [dict(self.payload)]
        elif self.op == "delete":
            self.rows[:] = [r for r in self.rows if not match(r)]
        class R: pass
        out = R(); out.data = [r for r in self.rows if match(r)] if self.op == "select" else []
        return out


class FakeClient:
    def __init__(self): self.rows = []
    def table(self, name): return _Query(self.rows, name)


def test_round_trip_is_encrypted_at_rest():
    client = FakeClient()
    store = EncryptedSupabaseTokenStore(client, key=Fernet.generate_key().decode())
    store.save("t1", {"refresh_token": "SECRET-REFRESH", "access_token": "a"})
    assert "SECRET-REFRESH" not in str(client.rows) and "refresh_token" not in str(client.rows)
    assert store.get("t1")["refresh_token"] == "SECRET-REFRESH"
    assert store.get("other") is None
    store.save("t1", {"refresh_token": "NEW"})
    assert len(client.rows) == 1 and store.get("t1")["refresh_token"] == "NEW"
    store.delete("t1")
    assert store.get("t1") is None


def test_wrong_key_forces_reconnect_instead_of_leaking_or_crashing():
    client = FakeClient()
    EncryptedSupabaseTokenStore(client, key=Fernet.generate_key().decode()).save("t1", {"refresh_token": "x"})
    with pytest.raises(TokenEncryptionError):
        EncryptedSupabaseTokenStore(client, key=Fernet.generate_key().decode()).get("t1")


def test_missing_or_invalid_key_fails_closed(monkeypatch, tmp_path):
    monkeypatch.delenv("GMAIL_TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(TokenEncryptionError):
        EncryptedSupabaseTokenStore(FakeClient())
    with pytest.raises(TokenEncryptionError):
        EncryptedSupabaseTokenStore(FakeClient(), key="not-a-fernet-key")
    monkeypatch.setenv("GMAIL_TOKEN_DIR", str(tmp_path))
    assert type(build_gmail_token_store(FakeClient())).__name__ == "TrialGmailTokenStore"
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert type(build_gmail_token_store(FakeClient())).__name__ == "EncryptedSupabaseTokenStore"
