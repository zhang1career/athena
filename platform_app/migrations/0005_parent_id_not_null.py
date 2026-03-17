# parent_id: NULL -> NOT NULL DEFAULT 0, 0表示无父记录
# 移除外键约束（0 非有效引用）

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_app", "0004_alter_plat_exp_run_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE plat_exp_run DROP FOREIGN KEY plat_exp_run_parent_id_fk",
                "UPDATE plat_exp_run SET parent_id = 0 WHERE parent_id IS NULL",
                "ALTER TABLE plat_exp_run MODIFY parent_id bigint unsigned NOT NULL DEFAULT 0 COMMENT '0表示无父记录'",
            ],
            reverse_sql=[
                "UPDATE plat_exp_run SET parent_id = NULL WHERE parent_id = 0",
                "ALTER TABLE plat_exp_run MODIFY parent_id bigint DEFAULT NULL",
                "ALTER TABLE plat_exp_run ADD CONSTRAINT plat_exp_run_parent_id_fk "
                "FOREIGN KEY (parent_id) REFERENCES plat_exp_run (id) ON DELETE SET NULL",
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="experimentrun",
                    name="parent",
                ),
                migrations.AddField(
                    model_name="experimentrun",
                    name="parent_id",
                    field=models.PositiveBigIntegerField(db_column="parent_id", default=0),
                ),
            ],
        ),
    ]
