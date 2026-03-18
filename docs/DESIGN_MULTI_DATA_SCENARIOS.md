# 多策略架构 — 适应多样数据场景的设计思路

## 1. 现状与挑战

| 数据场景 | 数据粒度 | 目标类型 | 示例 |
|----------|----------|----------|------|
| 比赛级胜平负 | 每场比赛一行 | 1/X/2 多分类 | MatchRecord，有 home/away、result |
| 小组出线赔率 | 每队每组一行 | 二分类（是否冠军） | odds-worldcup-group，只有「是否小组第一」 |

当前 `MatchRecord` + `match_records_to_arrays` 仅支持「比赛级 1/X/2」场景。赔率、小组冠军等任务需要不同 schema 与 loader。

---

## 2. 设计思路总览

```
┌─────────────────────────────────────────────────────────────────────┐
│  Data Schema Registry（数据 schema 注册）                             │
│  - match_1x2: MatchRecord, feature_cols, result -> 0/1/2           │
│  - group_winner: GroupTeamRecord, feature_cols, is_winner -> 0/1    │
│  - (可扩展) odds_regression, rank_classification 等                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Strategy–Task 绑定                                                  │
│  - lightgbm_match: 支持 task=match_1x2                              │
│  - lightgbm_group_winner: 支持 task=group_winner                    │
│  - elo_baseline: 支持 task=match_1x2                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Application Loader（按 data_type / task 选择 loader）                │
│  - data_config 含 data_type 或 task                                 │
│  - 平台按类型选择 loader，返回 (X_train, y_train, ...)               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 具体设计要点

### 3.1 数据 Schema 抽象

- **思路**：每种任务定义自己的 Record 类型和 `to_arrays` 函数。
- **实现**：在 `applications/worldcup/data/` 下增加 `schemas/` 或通过 `data_type` 映射到不同 schema。

```python
# 示例：group_winner schema
@dataclass
class GroupTeamRecord:
    group: str
    team: str
    record_id: str
    features: dict
    is_winner: int  # 0 or 1

def group_records_to_arrays(records, feature_cols) -> Tuple[np.ndarray, np.ndarray]:
    X = [[r.features.get(c, 0) for c in feature_cols] for r in records]
    y = [r.is_winner for r in records]
    return np.array(X), np.array(y)
```

### 3.2 Strategy 声明支持的任务

- **思路**：在 `StrategySchema` 中增加 `supported_tasks: List[str]`。
- **作用**：实验创建时根据 `data_config.task` 校验策略是否兼容。

```python
@classmethod
def get_schema(cls) -> StrategySchema:
    return StrategySchema(
        name="LightGBMGroupWinner",
        version="0.1.0",
        params_schema={...},
        supported_tasks=["group_winner"],  # 新增
    )
```

### 3.3 Loader 按 data_type / task 分发

- **思路**：`data_config` 增加 `data_type`（如 `"group_odds"`）或 `task`（如 `"group_winner"`）。
- **实现**：`worldcup_data_loader` 先判断 `data_type` / `task`，再选择对应 loader 与 `to_arrays`。

```python
def worldcup_data_loader(data_config):
    data_type = data_config.get("data_type") or data_config.get("task") or "match_1x2"
    if data_type == "group_winner":
        return _load_group_winner(data_config)
    return _load_match_1x2(data_config)  # 原有逻辑
```

### 3.4 清洗脚本输出约定

- **建议**：清洗后的 JSON 顶部包含 `data_type` 和 `task`，便于 loader 自动识别。
- 示例：`{"data_type": "group_odds", "task": "group_winner", "records": [...], "feature_cols": [...]}`

---

## 4. 实施优先级

| 阶段 | 内容 | 说明 |
|------|------|------|
| P0 | 增加 group_winner schema 与 loader | 支持当前赔率数据 |
| P0 | 新增 lightgbm_group_winner 策略 | 二分类预测小组冠军 |
| P1 | StrategySchema 增加 supported_tasks | 校验策略与任务匹配 |
| P2 | Loader 注册表 | 按 data_type 动态选择 loader |
| P2 | 统一评估接口 | 二分类用 accuracy/auc，多分类用 accuracy，可扩展 |

---

## 5. 与现有流程的关系

- **clean_script**：负责产出符合约定 schema 的 JSON（含 `data_type`、`task`、`records`、`feature_cols`）。
- **DataLoader**：按 `data_type` / `task` 选择 schema 和 `to_arrays`，输出 `(X, y)`。
- **Strategy**：只需接收 `(X, y)`，不关心原始 schema；通过 `supported_tasks` 声明兼容的任务类型。
- **预测流程**：`data_config` 中显式或隐式指定 `data_type` / `task`，与策略、loader 一起完成端到端流程。

---

## 6. 约定与确认

### 6.1 clean_script 统一产出「带信封」的 JSON

**结论：是。** 所有通过 `data_src.clean_script` 产出、并由 `save_cleaned_file` 写入的清洗结果，**统一约定为带信封的 JSON**，便于平台按 `data_type` / `task` 选择 loader 与策略。

- **信封格式**：`{"data_type": "<类型名>", "task": "<任务名>", "records": [...], "feature_cols": [...]}`  
  - 至少包含：`data_type`、`task`、`records`、`feature_cols`（或由 loader 从 records 推断）。
- **数据来源**：当前及未来进入「一轮预测」的数据，均来自对 `data_src` 表中某条记录的 `clean_script` 执行结果（如 id=1）；该脚本的产出应遵循上述信封格式。
- **Versioning 层**：合成数据时需识别「信封」——若 JSON 根为对象且含 `records` 键，则用 `records` 作为记录列表做 patch 合成，并在写出 composed 文件时**保留信封**（`data_type`、`task`、`feature_cols` 等），供 loader 读取。patch 合并时用 `record_id`（或约定主键）匹配记录。

### 6.2 命题（task）优先，策略在命题下绑定

**结论：小组出线预测与决赛冠军预测等，是不同「命题」，而不是同一命题下的不同策略。**

- **命题**：由业务含义与数据形态决定，例如  
  - `match_1x2`：比赛级胜平负（每场一行，多分类）；  
  - `group_winner`：小组出线/小组第一（每队每组一行，二分类）；  
  - 未来如 `final_winner`：决赛冠军（赛会制、淘汰赛逻辑，与小组机制不同）。  
  比赛机制、影响因素、样本粒度都不同，因此先区分为不同 **task**，再在各自 task 下挂载策略。
- **策略**：每个策略通过 `supported_tasks` 声明自己支持哪些 task（如 `lightgbm_match` 支持 `match_1x2`，`lightgbm_group_winner` 支持 `group_winner`）。  
  「启动一轮预测」时：**先由数据（信封中的 task）确定命题，再在该命题下选用或自动匹配策略**，而不是用同一策略处理所有数据。
