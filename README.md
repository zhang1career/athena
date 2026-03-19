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

# 启动服务
python manage.py runserver
```

## 访问

- Dashboard: http://127.0.0.1:8000/console/
- API: http://127.0.0.1:8000/api/v1/

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
