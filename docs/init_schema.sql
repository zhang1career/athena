-- Athena 建表 SQL（由 Django 迁移生成）
-- 使用方法：mysql -u USER -p DB_NAME < docs/init_schema.sql
-- 或：python manage.py migrate（推荐）

-- 1. ExperimentRun
CREATE TABLE `plat_exp_run` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `run_id` bigint NOT NULL COMMENT 'snowflake id',
  `name` varchar(255) NOT NULL,
  `strategy_id` varchar(128) NOT NULL,
  `params` longtext NOT NULL COMMENT 'JSON string',
  `data_config` longtext NOT NULL COMMENT 'JSON string',
  `status` smallint NOT NULL DEFAULT 0 COMMENT '0=PENDING,1=RUNNING,2=SUCCESS,3=FAILED,4=CANCELLED',
  `metrics` longtext NOT NULL COMMENT 'JSON string',
  `artifacts` longtext NOT NULL COMMENT 'JSON string',
  `ct` bigint unsigned NOT NULL DEFAULT 0 COMMENT '创建时间(unix)',
  `ut` bigint unsigned NOT NULL DEFAULT 0 COMMENT '更新时间(unix)',
  `error_message` text NOT NULL,
  `parent_id` bigint unsigned NOT NULL DEFAULT 0 COMMENT '0表示无父记录',
  PRIMARY KEY (`id`),
  UNIQUE KEY `run_id` (`run_id`),
  KEY `plat_exp_run_run_id_idx` (`run_id`),
  KEY `plat_exp_run_status_idx` (`status`),
  KEY `plat_exp_run_parent_id_idx` (`parent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. ExperimentMetric
CREATE TABLE `plat_exp_metric` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  `value` double NOT NULL,
  `step` int DEFAULT NULL,
  `run_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `plat_exp_metric_run_id_idx` (`run_id`,`name`),
  CONSTRAINT `plat_exp_metric_run_id_fk` FOREIGN KEY (`run_id`) REFERENCES `plat_exp_run` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
