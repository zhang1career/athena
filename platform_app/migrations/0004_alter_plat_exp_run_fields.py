# Generated migration for plat_exp_run schema changes
# - params, data_config, metrics, artifacts: JSON -> TEXT (JSON string, app encode/decode)
# - created_at, updated_at -> ct, ut: BIGINT UNSIGNED (unix timestamp)
# - error_message: LONGTEXT -> TEXT

from django.db import migrations, models
import platform_app.fields


def migrate_created_updated_to_ct_ut(apps, schema_editor):
    """Copy created_at/updated_at to ct/ut as unix timestamps."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE plat_exp_run SET ct = UNIX_TIMESTAMP(created_at), ut = UNIX_TIMESTAMP(updated_at)"
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("platform_app", "0003_rename_parent_run_to_parent"),
    ]

    operations = [
        # 1. params, data_config, metrics, artifacts: JSONField -> JSONTextField (DB: JSON -> LONGTEXT)
        migrations.AlterField(
            model_name="experimentrun",
            name="params",
            field=platform_app.fields.JSONTextField(default=dict, json_type=dict),
        ),
        migrations.AlterField(
            model_name="experimentrun",
            name="data_config",
            field=platform_app.fields.JSONTextField(default=dict, json_type=dict),
        ),
        migrations.AlterField(
            model_name="experimentrun",
            name="metrics",
            field=platform_app.fields.JSONTextField(default=dict, json_type=dict),
        ),
        migrations.AlterField(
            model_name="experimentrun",
            name="artifacts",
            field=platform_app.fields.JSONTextField(default=list, json_type=list),
        ),
        # 2. Add ct, ut
        migrations.AddField(
            model_name="experimentrun",
            name="ct",
            field=models.PositiveBigIntegerField(db_column="ct", default=0),
        ),
        migrations.AddField(
            model_name="experimentrun",
            name="ut",
            field=models.PositiveBigIntegerField(db_column="ut", default=0),
        ),
        # 3. Migrate created_at, updated_at -> ct, ut
        migrations.RunPython(migrate_created_updated_to_ct_ut, noop),
        # 4. Remove created_at, updated_at
        migrations.RemoveField(
            model_name="experimentrun",
            name="created_at",
        ),
        migrations.RemoveField(
            model_name="experimentrun",
            name="updated_at",
        ),
        # 5. error_message: LONGTEXT -> TEXT
        migrations.RunSQL(
            sql="ALTER TABLE plat_exp_run MODIFY error_message TEXT NOT NULL",
            reverse_sql="ALTER TABLE plat_exp_run MODIFY error_message LONGTEXT NOT NULL",
        ),
    ]
