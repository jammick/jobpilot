# JobPilot Agent Eval

这套评测不预测候选人是否应被录用。它验证 Agent 是否忠实执行已发布的岗位规则，并且每个结论都能回链到简历原文。

数据集先声明 `strong / partial / missing` 结构化事实，再由 `generator.py` 渲染自然语言简历，因此标准答案由构造过程产生，不依赖 HR 主观打分。

当前 20 个场景覆盖：完整匹配、技能同义词、初级候选人、单/双硬门槛缺失、RAG 或 LLM 单项证据、关键词堆砌、量化成果、弱证据与多个普通能力缺口。

运行：

```powershell
cd backend
python -m evals.runner
python -m evals.runner --json
```

核心指标：

- `score_accuracy`：规则总分是否等于构造标准答案。
- `status_accuracy`：逐项 `matched / partial / unmatched` 是否正确。
- `evidence_validity`：所有引用是否真实存在于原简历。
- `deterministic_rate`：相同输入重复运行是否产生相同评分。
- `optimization_guard_accuracy`：优化草稿是否拦截新增数字、技术、公司、职位和知识包技能。
- `metamorphic_pass_rate`：调换段落、堆砌关键词和注入提示词后，评分是否保持稳定。

开源简历只应用于扩充语言表达，不应直接成为“是否录用”的标签。新增数据时必须记录来源、许可证和处理方式；真实个人简历不得进入仓库。

## 影子数据

`sources.json` 是来源与许可证登记表。下载文件必须由开发者先核对数据卡和具体版本，再通过本地导入器移除常见邮箱、手机号、网址和证件号；自动脱敏不能替代人工隐私复核。`reference-only` 来源不能作为简历样本导入，输出默认放在 Git 忽略的 `.local/` 目录。

```powershell
python -m evals.shadow_import `
  --input path/to/resumes.parquet `
  --output .local/shadow/records.jsonl `
  --source-id hf-candidate-matching-synthetic `
  --resume-field __auto__ `
  --limit 200

python -m evals.shadow_runner --input .local/shadow/records.jsonl
```

也可以不安装 Parquet 依赖，直接导入已登记来源公开的最多 100 条预览数据：

```powershell
python -m evals.shadow_import --from-preview `
  --source-id hf-candidate-matching-synthetic `
  --output .local/shadow/records.jsonl `
  --limit 100
```

Parquet 数据只在开发者评测环境需要，安装 `requirements-eval.txt` 即可；生产后端不额外携带该依赖。

影子评测不需要 HR 标签。它检查段落重排、关键词堆砌和提示词注入前后结果是否稳定，以及全部证据能否回链原文。
