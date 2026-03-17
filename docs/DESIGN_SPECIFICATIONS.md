# Athena 预测平台 — 设计规约

## 1. 策略插件规约

### 1.1 策略基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class PredictResult:
    """预测结果，保证可序列化与可观测"""
    predictions: Any          # 主预测值
    proba: Optional[Any]      # 概率（如分类）
    metadata: Dict[str, Any]  # 中间结果、特征、日志

@dataclass
class StrategySchema:
    name: str
    version: str
    params_schema: Dict[str, dict]  # JSON Schema 风格

class Strategy(ABC):
    """策略统一接口"""

    @abstractmethod
    def fit(self, X, y, **kwargs) -> None:
        pass

    @abstractmethod
    def predict(self, X, **kwargs) -> PredictResult:
        pass

    def get_params(self) -> dict:
        return {}

    def set_params(self, **params) -> None:
        pass

    @classmethod
    @abstractmethod
    def get_schema(cls) -> StrategySchema:
        pass
```

### 1.2 策略注册

- 策略类通过 `@register_strategy` 或配置文件声明
- 注册信息：`strategy_id`、类路径、参数默认值
- 支持从指定目录扫描并加载

### 1.3 组合策略规约

```python
class MetaStrategy(Strategy):
    """组合策略基类，子策略列表 + 组合逻辑"""

    def __init__(self, sub_strategies: List[Strategy], combiner_config: dict):
        self.sub_strategies = sub_strategies
        self.combiner_config = combiner_config
```

- **Stacking**：子策略输出作为特征，训练一个元模型
- **Weighted**：`combiner_config` 包含各子策略权重
- **Custom**：`combiner_config` 可指向可执行逻辑（需沙箱）

---

## 2. 实验框架规约

### 2.1 实验数据结构

```yaml
Experiment:
  run_id: str           # 全局唯一
  name: str
  strategy_id: str
  params: dict
  data_config: dict     # 数据源、切分配置
  status: enum          # PENDING, RUNNING, SUCCESS, FAILED
  created_at: datetime
  parent_run_id: str?   # 调参/派生实验
  metrics: dict
  artifacts: list       # 模型、日志路径等
```

### 2.2 实验阶段

| 阶段 | 说明 |
|------|------|
| INIT | 加载策略、数据、配置 |
| TRAIN | 训练策略 |
| VALIDATE | 验证集评估 |
| BACKTEST | 回测 |
| FINALIZE | 写库、生成报告 |

### 2.3 实验运行器接口

```python
class ExperimentRunner(ABC):
    def run(self, config: ExperimentConfig) -> ExperimentResult: ...
```

- 本地实现：`LocalRunner`
- 分布式实现：`RayRunner`，将 `run` 提交到 Ray

---

## 3. 回测规约

### 3.1 数据切分

- **Walk-Forward**：按时间窗口滚动，每个窗口内 train/val/test
- **Expanding Window**：训练集逐步扩大
- **K-Fold Time Series**：时序安全的 K 折

### 3.2 回测输出

- 每个时间点的预测值、真实值、指标
- 汇总指标：MAE、RMSE、Accuracy、AUC 等（可配置）
- 支持应用自定义指标函数

### 3.3 避免泄露

- 禁止使用未来信息
- 特征工程必须在切分后进行

---

## 4. 参数搜索规约

### 4.1 搜索空间定义

```yaml
# Hydra / 配置文件
tuning:
  method: bayesian  # bayesian | grid | random
  n_trials: 50
  params:
    learning_rate: {type: float, low: 0.01, high: 0.3}
    n_estimators: {type: int, low: 50, high: 500}
    max_depth: [3, 5, 7, 9]
```

### 4.2 Optuna 集成

- 使用 Optuna 的 `Study` 管理 trial
- 每个 trial 对应一次实验，`run_id` 与 `trial_id` 关联
- 支持 Pruning（早停）

### 4.3 Grid Search

- 笛卡尔积生成参数组合
- 支持与 Ray 并行

---

## 5. 存储规约

### 5.1 Django 模型（示意）

```python
# 核心表
class ExperimentRun(Model):
    run_id = CharField(unique=True)
    name = CharField()
    strategy_id = CharField()
    params = JSONField()
    status = CharField()
    metrics = JSONField()
    parent_id = ForeignKey('self', null=True)
    created_at = DateTimeField()

class ExperimentMetric(Model):
    run = ForeignKey(ExperimentRun)
    name = CharField()
    value = FloatField()
    step = IntegerField(null=True)  # 用于曲线
```

### 5.2 MLflow 集成

- 使用 MLflow 记录：params、metrics、artifacts
- `run_id` 与 MLflow `run_id` 一致或映射
- 模型可存 MLflow Model Registry（可选）

### 5.3 可观测数据

- 每次预测的输入/输出可写入 `ExperimentArtifact`
- 支持按 `run_id` 查询中间结果

---

## 6. API 规约

### 6.1 实验 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/experiments | 创建并启动实验 |
| GET | /api/experiments/{run_id} | 获取实验详情 |
| GET | /api/experiments | 列表、筛选、分页 |
| POST | /api/experiments/{run_id}/cancel | 取消实验 |

### 6.2 策略 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/strategies | 列出已注册策略 |
| GET | /api/strategies/{id}/schema | 获取策略参数 schema |

### 6.3 AI 操作接口

- 上述 API 均支持 JSON 请求/响应
- 可选：提供 Python SDK 封装，便于 AI 脚本调用
- 策略定义、组合配置可通过 API 提交（需校验与沙箱）

---

## 7. 配置规约（Hydra）

### 7.1 配置结构

```
config/
├── default.yaml       # 平台默认
├── experiment.yaml    # 实验相关
├── strategy.yaml      # 策略默认
└── applications/
    └── worldcup/
        ├── config.yaml
        └── data.yaml
```

### 7.2 配置合并

- 平台默认 → 应用默认 → 命令行覆盖
- 所有参数均可通过 Hydra CLI 覆盖

---

## 8. 分布式规约（Ray）

### 8.1 任务划分

- 每个实验为独立 Task
- 参数搜索的 trial 可并行
- 支持 `@ray.remote` 装饰的实验函数

### 8.2 资源约束

- 可配置每任务 CPU/内存
- 支持队列与并发上限

---

## 9. Dashboard 规约

### 9.1 页面

| 页面 | 内容 |
|------|------|
| 实验列表 | 表格：run_id、策略、状态、关键指标、时间 |
| 实验详情 | 参数、指标、曲线、日志链接 |
| 策略列表 | 已注册策略及 schema |
| 指标对比 | 多实验指标并排对比 |

### 9.2 AI 友好

- 数据以结构化 JSON/表格为主
- 避免复杂图表，优先表格与简单折线
- 提供导出（CSV/JSON）供 AI 分析

---

## 10. AI Research Loop 规约

### 10.1 输入输出

- **输入**：当前最优实验、指标、策略列表
- **输出**：新策略定义 / 参数修改 / 组合调整

### 10.2 执行方式

- 平台提供 `research_loop` 入口，接受「提议」并执行
- 提议格式：策略 ID、参数覆盖、组合配置
- 执行后返回 `run_id`，AI 通过 API 获取结果

### 10.3 安全

- 策略代码执行在隔离环境
- 资源限制（CPU、内存、时间）
- 可配置审核流程（人工/AI 二次校验）

---

## 11. 足球世界杯应用规约

### 11.1 数据

- 数据源由应用定义（API、文件、DB）
- 平台提供 `DataLoader` 接口，应用实现

### 11.2 预测目标

- 胜平负、比分、进球数等（由应用配置）
- 指标：准确率、对数损失等

### 11.3 配置示例

```yaml
# applications/worldcup/config.yaml
application: worldcup
data:
  loader: worldcup.loaders.MatchDataLoader
  split:
    method: time_based
    train_ratio: 0.7
    val_ratio: 0.15
metrics:
  - accuracy
  - log_loss
strategies:
  - lightgbm_match
  - elo_baseline
  - stacking_ensemble
```

---

## 12. 版本与兼容

- 策略 schema 带版本号
- 平台 API 支持版本前缀：`/api/v1/`
- 实验记录不可篡改，新指标可追加
