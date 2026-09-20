from pathlib import Path


def test_storage_migration_uses_portable_policy_creation_pattern():
    sql = Path("supabase/migrations/004_attachments_storage.sql").read_text()
    assert "create policy if not exists" not in sql.lower()
    assert "drop policy if exists engineering_attachments_authenticated_select" in sql.lower()
    assert "drop policy if exists engineering_attachments_authenticated_insert" in sql.lower()
    assert "insert into storage.buckets" in sql.lower()
