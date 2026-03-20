-- Athena 建表 SQL
-- 使用方法：mysql -u USER -p DB_NAME < docs/init_schema.sql
-- 或：python manage.py migrate（推荐）

-- 1. ExperimentRun
CREATE TABLE `plat_exp_run` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `description` text NOT NULL DEFAULT '' COMMENT '来自 Train.description 或空',
  `strategy` varchar(128) NOT NULL,
  `params` longtext NOT NULL,
  `data_config` longtext NOT NULL,
  `status` smallint NOT NULL DEFAULT 0,
  `metrics` longtext NOT NULL,
  `artifacts` longtext NOT NULL,
  `data_q` longtext NOT NULL DEFAULT '{}' COMMENT 'JSON: label_type, sample_count, positive_class, negative_class, balance, mean, variance, invalid_or_missing_count, class_counts (multiclass only)',
  `evaluation` text NOT NULL DEFAULT '' COMMENT '实验结果评价（由 AI 生成）',
  `ct` bigint unsigned NOT NULL DEFAULT 0,
  `ut` bigint unsigned NOT NULL DEFAULT 0,
  `error_message` text NOT NULL,
  `parent_id` bigint unsigned NOT NULL DEFAULT 0,
  `v` bigint unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `plat_exp_run_status_idx` (`status`),
  KEY `plat_exp_run_parent_id_idx` (`parent_id`),
  KEY `plat_exp_run_v_idx` (`v`)
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

-- 3. DataSrc（数据源元信息；raw_name/raw_path 含占位符，用于获取数据时生成 raw_data_file；clean_script 为清洗脚本）
CREATE TABLE `data_src` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL DEFAULT '',
  `src_url` varchar(1024) NOT NULL DEFAULT '',
  `url_params` longtext NOT NULL COMMENT 'JSON 数组，每项 {"name": "占位符名"}',
  `raw_name` varchar(512) NOT NULL DEFAULT '',
  `raw_path` varchar(512) NOT NULL DEFAULT '',
  `cleaned_name` varchar(512) NOT NULL DEFAULT '' COMMENT '含占位符，替换后写入 data_file.name',
  `cleaned_path` varchar(512) NOT NULL DEFAULT '' COMMENT '含占位符，替换后得到 data_file.file_path 并保存清洗后文件',
  `clean_script` text NOT NULL COMMENT '数据清洗脚本（Python），输入 raw_data_file，产出 data_file',
  `fetch_mode` smallint unsigned NOT NULL DEFAULT 0 COMMENT '0=raw, 1=html_tables',
  `format_type` smallint NOT NULL DEFAULT 2 COMMENT '1=JSON,2=CSV,3=xlsx,4=xls；html_tables 时输出格式',
  `ct` bigint unsigned NOT NULL DEFAULT 0,
  `ut` bigint unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据源的元信息';

-- 3b. RawDataFile（原始数据文件；由获取数据创建）
CREATE TABLE `raw_data_file` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `data_src_id` int unsigned NOT NULL DEFAULT 0,
  `name` varchar(255) NOT NULL DEFAULT '',
  `file_path` varchar(255) NOT NULL DEFAULT '',
  `args` varchar(1024) NOT NULL DEFAULT '' COMMENT 'JSON，url_params 替换参数',
  `ct` bigint unsigned NOT NULL DEFAULT 0,
  `ut` bigint unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `raw_data_file_data_src_id_idx` (`data_src_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始数据文件';

-- 4. DataFile（清洗后的数据；由 clean_script 产出）
CREATE TABLE `data_file` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `data_src_id` int unsigned NOT NULL,
  `raw_id` bigint unsigned NULL DEFAULT NULL COMMENT '来源 raw_data_file.id',
  `name` varchar(512) NOT NULL DEFAULT '',
  `file_path` varchar(1024) NOT NULL DEFAULT '',
  `ct` bigint unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `data_file_ct_idx` (`ct`),
  KEY `data_file_data_src_id_idx` (`data_src_id`),
  KEY `data_file_raw_id_idx` (`raw_id`),
  CONSTRAINT `data_file_data_src_fk` FOREIGN KEY (`data_src_id`) REFERENCES `data_src` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `data_file_raw_id_fk` FOREIGN KEY (`raw_id`) REFERENCES `raw_data_file` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. DataPatchBatch（版本由 ct 提供）
CREATE TABLE `data_patch_batch` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `ct` bigint unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `data_patch_batch_ct_idx` (`ct`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. DataPatch（通过 batch_id 关联批次）
CREATE TABLE `data_patch` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `batch_id` bigint NOT NULL,
  `name` varchar(255) NOT NULL,
  `value` longtext NOT NULL,
  PRIMARY KEY (`id`),
  KEY `data_patch_batch_id_idx` (`batch_id`),
  KEY `data_patch_batch_name_idx` (`batch_id`,`name`),
  CONSTRAINT `data_patch_batch_fk` FOREIGN KEY (`batch_id`) REFERENCES `data_patch_batch` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Train（训练科目；一轮预测时可选，用于实验名称、描述、策略及数据质量关联；code 用于模型 artifact 路径 artifacts/<code>.pkl）
CREATE TABLE `train` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `code` varchar(128) NOT NULL DEFAULT '' COMMENT '训练科目编码，用于 artifact 保存路径',
  `description` text NOT NULL DEFAULT '',
  `strategy` varchar(128) NOT NULL DEFAULT '',
  `ct` bigint unsigned NOT NULL DEFAULT 0,
  `ut` bigint unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `train_ct_idx` (`ct`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='训练科目';
