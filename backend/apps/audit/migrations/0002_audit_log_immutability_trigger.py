"""Database-level write-once immutability triggers for audit_logs table.

Satisfies Architecture Manual Section 4.7 Layer 6:
- PostgreSQL: PL/pgSQL function & BEFORE UPDATE/DELETE trigger
- SQLite: BEFORE UPDATE/DELETE triggers for automated testing
"""

from django.db import migrations


def add_immutability_triggers(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION enforce_audit_log_immutability() RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Audit log entries are strictly immutable. UPDATE and DELETE operations are forbidden.';
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs;
            CREATE TRIGGER trg_audit_logs_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION enforce_audit_log_immutability();
        """)
    elif connection.vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit log entries are strictly immutable. UPDATE operations are forbidden.');
            END;
        """)
        schema_editor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit log entries are strictly immutable. DELETE operations are forbidden.');
            END;
        """)


def drop_immutability_triggers(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs;
            DROP FUNCTION IF EXISTS enforce_audit_log_immutability();
        """)
    elif connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS trg_audit_logs_no_update;")
        schema_editor.execute("DROP TRIGGER IF EXISTS trg_audit_logs_no_delete;")


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_immutability_triggers, drop_immutability_triggers),
    ]
