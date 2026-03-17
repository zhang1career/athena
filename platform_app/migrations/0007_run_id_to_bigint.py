# run_id: varchar(64) -> bigint (snowflake id)

from django.db import connection, migrations, models


def migrate_run_id_to_bigint(apps, schema_editor):
    """Convert run_id from varchar to bigint. Existing string IDs -> unique bigint via id+hash."""
    with connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE plat_exp_run ADD COLUMN run_id_new bigint NOT NULL DEFAULT 0"
        )
        # Deterministic unique bigint: id * 1e12 + hash(run_id) % 1e12
        cursor.execute(
            """
            UPDATE plat_exp_run SET run_id_new = id * 1000000000000
                + MOD(CONV(SUBSTRING(MD5(run_id), 1, 12), 16, 10), 1000000000000)
            """
        )
        cursor.execute("ALTER TABLE plat_exp_run DROP INDEX run_id")
        cursor.execute("ALTER TABLE plat_exp_run DROP INDEX plat_exp_run_run_id_idx")
        cursor.execute("ALTER TABLE plat_exp_run DROP COLUMN run_id")
        cursor.execute(
            "ALTER TABLE plat_exp_run CHANGE COLUMN run_id_new run_id bigint NOT NULL"
        )
        cursor.execute("CREATE UNIQUE INDEX run_id ON plat_exp_run (run_id)")
        cursor.execute("CREATE INDEX plat_exp_run_run_id_idx ON plat_exp_run (run_id)")


def reverse_migrate_run_id(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE plat_exp_run ADD COLUMN run_id_old varchar(64) NOT NULL DEFAULT ''"
        )
        cursor.execute(
            "UPDATE plat_exp_run SET run_id_old = CAST(run_id AS CHAR)"
        )
        cursor.execute("ALTER TABLE plat_exp_run DROP INDEX run_id")
        cursor.execute("ALTER TABLE plat_exp_run DROP INDEX plat_exp_run_run_id_idx")
        cursor.execute("ALTER TABLE plat_exp_run DROP COLUMN run_id")
        cursor.execute(
            "ALTER TABLE plat_exp_run CHANGE COLUMN run_id_old run_id varchar(64) NOT NULL"
        )
        cursor.execute("CREATE UNIQUE INDEX run_id ON plat_exp_run (run_id)")
        cursor.execute("CREATE INDEX plat_exp_run_run_id_idx ON plat_exp_run (run_id)")


class Migration(migrations.Migration):

    dependencies = [
        ("platform_app", "0006_status_to_smallint"),
    ]

    operations = [
        migrations.RunPython(migrate_run_id_to_bigint, reverse_migrate_run_id),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="experimentrun",
                    name="run_id",
                    field=models.BigIntegerField(db_index=True, unique=True),
                ),
            ],
        ),
    ]
