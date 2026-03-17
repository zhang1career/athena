# status: varchar(32) -> smallint (enum id)
# PENDING=0, RUNNING=1, SUCCESS=2, FAILED=3, CANCELLED=4

from django.db import migrations, models


def migrate_status_to_int(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cursor:
        # Add temp column, migrate data, drop old, rename
        cursor.execute(
            "ALTER TABLE plat_exp_run ADD COLUMN status_new smallint NOT NULL DEFAULT 0"
        )
        cursor.execute(
            """
            UPDATE plat_exp_run SET status_new = CASE
                WHEN status = 'PENDING' THEN 0
                WHEN status = 'RUNNING' THEN 1
                WHEN status = 'SUCCESS' THEN 2
                WHEN status = 'FAILED' THEN 3
                WHEN status = 'CANCELLED' THEN 4
                ELSE 0
            END
            """
        )
        cursor.execute("ALTER TABLE plat_exp_run DROP INDEX plat_exp_run_status_idx")
        cursor.execute("ALTER TABLE plat_exp_run DROP COLUMN status")
        cursor.execute(
            "ALTER TABLE plat_exp_run CHANGE COLUMN status_new status smallint NOT NULL DEFAULT 0"
        )
        cursor.execute(
            "CREATE INDEX plat_exp_run_status_idx ON plat_exp_run (status)"
        )


def reverse_migrate_status(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE plat_exp_run ADD COLUMN status_old varchar(32) NOT NULL DEFAULT 'PENDING'"
        )
        cursor.execute(
            """
            UPDATE plat_exp_run SET status_old = CASE
                WHEN status = 0 THEN 'PENDING'
                WHEN status = 1 THEN 'RUNNING'
                WHEN status = 2 THEN 'SUCCESS'
                WHEN status = 3 THEN 'FAILED'
                WHEN status = 4 THEN 'CANCELLED'
                ELSE 'PENDING'
            END
            """
        )
        cursor.execute("ALTER TABLE plat_exp_run DROP INDEX plat_exp_run_status_idx")
        cursor.execute("ALTER TABLE plat_exp_run DROP COLUMN status")
        cursor.execute(
            "ALTER TABLE plat_exp_run CHANGE COLUMN status_old status varchar(32) NOT NULL DEFAULT 'PENDING'"
        )
        cursor.execute(
            "CREATE INDEX plat_exp_run_status_idx ON plat_exp_run (status)"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("platform_app", "0005_parent_id_not_null"),
    ]

    operations = [
        migrations.RunPython(migrate_status_to_int, reverse_migrate_status),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="experimentrun",
                    name="status",
                    field=models.SmallIntegerField(
                        choices=[
                            (0, "Pending"),
                            (1, "Running"),
                            (2, "Success"),
                            (3, "Failed"),
                            (4, "Cancelled"),
                        ],
                        db_index=True,
                        default=0,
                    ),
                ),
            ],
        ),
    ]
