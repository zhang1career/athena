# 产品与技术路线（ROADMAP）

## 评估指标

### 当前 / 简单方案（先实现）

- **二分类任务**（如 `group_winner`）：使用 **accuracy**（准确率）作为主指标，在实验 run 的 `metrics` 中写入 `accuracy`。
- **多分类任务**（如 `match_1x2`）：使用 **accuracy** 作为主指标。
- 不在首版实现 AUC、F1、per-class 等；不区分子集（如按小组/联赛）的细分指标。

### 后续更全面、性能更好的方案（待做）

- **二分类**：增加 **AUC**、**F1**、**precision/recall**，可选 **阈值可调**（如按业务需求调「是否出线」判定阈值）。
- **多分类**：保留 accuracy，增加 **macro F1**、**confusion matrix** 摘要（可存 artifact 或 metrics）。
- **统一评估接口**：按 `task` 选择默认指标集，策略或实验可覆盖；评估在 runner 内统一调用，避免各策略各自实现不一致。
- **可观测性**：训练/验证曲线、校准曲线（二分类）、重要特征（树模型）等写入 `artifacts` 或单独存储，便于控制台展示与调参。

上述内容在实现「简单方案」跑通流程后，再在 loader/runner/策略层逐步落地。

---

## 其他规划（可补充）

- **命题扩展**：如 `final_winner`（决赛冠军）的数据 schema、loader、策略。
- **StrategySchema.supported_tasks** 与创建实验/启动一轮时的校验（P1）。
- **Loader 注册表**、按 `data_type` 动态选择 loader（P2）。
