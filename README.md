# Athena 预测平台

AI 主导的预测平台，提供实验框架、策略抽象、回测与可观测能力。首个应用场景为足球世界杯预测。

## 技术栈

- Django 4.1, MySQL 5.7
- scikit-learn, LightGBM, pandas
- Hydra, Optuna, MLflow

## 快速开始

```bash
# 创建虚拟环境并安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，设置 DB_* 连接 MySQL

# 迁移
python manage.py migrate

# 启动服务（本地调试，前台）
python manage.py runserver
```

### 服务器部署

后台启停、写 PID 与日志时使用项目根目录的 `run.sh`（`start` / `stop` / `restart` / `status`），详见脚本顶部说明。部署环境可在 `.env` 中设置 `APP_NAME`、`LOG_FILE_PATH` 等。

#### 按应用开关部署（与 service_foundation 一致）

通过 `.env` 中的 **`APP_*_ENABLED`**（`true` / `false`）控制运行时加载的 Django 应用与 `api/v1` 路由，并对应选择依赖文件：

| 变量 | 为 `true` 时 |
|------|----------------|
| `APP_CONSOLE_ENABLED` | 安装 `app_console`、挂载 `/console/`、控制台相关模板与 context |
| `APP_WORLD_CUP_ENABLED` | 挂载 `/api/v1/worldcup/group-winner-prediction`（轻量：numpy / YAML / joblib） |
| `APP_PLATFORM_LAB_ENABLED` | 挂载实验、策略、研究、数据源、训练、`artifacts` 等 API（会 import pandas、LightGBM 等） |

**依赖建议：**

- **仅世界杯等轻量 API**（典型：`APP_PLATFORM_LAB_ENABLED=false`，可按需设 `APP_CONSOLE_ENABLED=false`）：  
  `pip install -r requirements/core.txt`。
- **实验 / 训练能力**（`APP_PLATFORM_LAB_ENABLED=true`）：  
  `pip install -r requirements.txt`（`core.txt` + `lab.txt`）。

说明：`APP_PLATFORM_LAB_ENABLED=false` 时不会加载 `platform_app/urls_lab.py`，避免启动阶段拉起重依赖；与 `service_foundation` 中按开关 `include` 各子项目 URL 的方式一致。

## 访问

- Dashboard: http://127.0.0.1:8000/console/
- API: http://127.0.0.1:8000/api/v1/
- **API 文档 (Swagger)**: http://127.0.0.1:8000/api/schema/swagger-ui/

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/experiments | 创建并启动实验 |
| GET | /api/v1/experiments | 实验列表 |
| GET | /api/v1/experiments/{run_id} | 实验详情 |
| POST | /api/v1/experiments/{run_id}/cancel | 取消实验 |
| GET | /api/v1/strategies | 策略列表 |
| GET | /api/v1/strategies/{id}/schema | 策略参数 schema |
| POST | /api/v1/research/propose | AI Research Loop 提议 |
| GET | /api/v1/worldcup/group-winner-prediction | 世界杯小组赛第一名预测 |

> 完整 API 文档见 [Swagger UI](/api/schema/swagger-ui/)

## 项目结构

```
athena/
├── athena/          # Django 项目
├── common/          # 公共工具
├── platform_core/   # 平台核心（策略、实验、回测、tuning）
├── platform_app/    # Django app（模型、API）
├── app_console/     # Dashboard
├── applications/
│   └── worldcup/    # 足球世界杯应用
│       ├── data/    # DataLoader、sample 数据
│       └── strategies/
└── config/          # Hydra 配置
```

## 使用 World Cup 数据

创建实验时传入 `data_config`:

```json
{
  "name": "World Cup exp",
  "strategy": "lightgbm_match",
  "data_config": {
    "path": "applications/worldcup/data/sample_data.json",
    "format": "json"
  }
}
```
