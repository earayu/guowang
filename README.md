# guowang — 国网物资招标审核 · ApeMind 演示工程

面向国网物资部评标场景的**否决情形自动判定**演示。核心是一条"抽取 → 判定 → 举证"链路：
把招标文件与投标文件的原文，抽成结构化字段，再逐条执行 46 条否决情形判定式，
每条结论都能回到原文的哪一行、差多少。

> 演示用途。所有判定结论上限为 `CANDIDATE`（候选意见），**机器不给否决结论**，
> 最终认定必须由评标专家人工签发。

---

## 一、这套东西在做什么

| 环节 | 实现 | 说明 |
|---|---|---|
| 原文 → 字段 | `sgcc_fn_field_extract/`（平台函数） | 表格行匹配 + 引用跳转 + 出处回读，逐物料对位 |
| 字段 → 结论 | `sgcc_fn_rule_judge/`（平台函数） | 46 条否决情形的受限 DSL 判定式，算子白名单穷举 |
| 结论 → 界面 | `sgcc_bff.py` + `国网物资部_评标辅助工作台_W3.html` | 界面调 BFF，BFF 调平台函数，抽屉里给出证据链 |

### 判定器的三条硬约束

1. **不用 `eval` / `exec`**：`check` 是 JSON 数据，15 个白名单算子穷举，规则表可以被审计。
2. **缺字段一律 `UNCERTAIN`**：绝不降级成"未见响应"。判不出来就说判不出来。
3. **结论上限 `CANDIDATE`**：机器只给候选意见，人为终局。

### 规则可外部注入（P0）

判定函数支持三个可选入参，改规则不需要重新发版：

- `rules` —— 规则对象数组。传了就以传入为准，不传则用函数内嵌的 V2 规则集
- `rule_set_version` —— 规则表版本名
- `rule_set_sha` —— 调用方算的规则指纹；与函数实算不符只写进 `notes` 留痕，不阻断判定

出参多一个 `rule_source`（`embedded` / `input`），标明本次用的是内嵌集还是传入集，
便于对客留证与事故追溯。

`_review/rules_source_v2.json` 就是一份可直接注入的规则源（46 条）。
`_review/make_rules_source.py` 可从函数导出并校验指纹。

---

## 二、怎么跑

只需要 Python 3 标准库，无第三方依赖。

```bash
python start_demo.py          # 直接开对客页面（file://，零进程，断网可用）
python start_demo.py --live   # 额外拉起 BFF(8787)，页面里的「现场跑 46 条」才真能跑
```

`--live` 模式需要本机装好并登录 `apemind-cli`，因为判定是调平台函数真跑的。

> 不起 BFF 时，界面上那块会明说"没连上"，不会拿快照冒充实时结果。

---

## 三、目录

```
start_demo.py                一键启动（三种模式）
sgcc_bff.py                  BFF：页面 ↔ 平台函数，含判定快照与规则源注入
国网物资部_评标辅助工作台_W3.html   对客主界面（评标辅助工作台）
国网Demo_演示控制台_V7.html        内部举证用控制台（看函数真跑读数）
国网物资部_标前审阅工作台_W1/W2.html  标前审阅界面

sgcc_fn_rule_judge/          判定函数（已发布 v5）：main.py + function.json
sgcc_fn_field_extract/       字段抽取函数
sgcc_fn_rule_exec/           早期判定器实现 + rules_46.json
sgcc_fn_clarification/       待澄清事项表（CANDIDATE，不可执行判定）

sgcc_rule_runner.py          判定引擎（DSL 求值）
sgcc_rule_dispatch.py        46 条规则分派
build_judge_fn.py            判定函数生成器（规则表内嵌进 main.py）
sgcc_ground_truth.json       人工真值
_judge_in_*.json             六家投标人的抽取输入快照（宜昌/襄阳/黄石/荆州/恩施/华中）

_blind_only/                 专家盲评材料（否决情形清单、三方对账）
_provenance/                 规则法源溯源
_scoreform/                  商务/技术评分表条目
_ux/                         界面脚本
_skills/                     配套 Agent 技能说明
_review/                     方案、证据与回归脚本
demo_pack_v2/                打包好的对客交付件
```

### 关键文档

- `_review/P0_规则注入_发布与核验_2026-11-16.md` —— 规则注入的发布记录与全部实测读数
- `_review/规则引擎可配置_实现路径_2026-11-16.md` —— 四条实现路径的实测对比与分期
- `_review/评审规则库_管理方案_2026-11-16.md` —— 客户侧规则库管理办法
- `国网Demo_演示手册_V2.md` —— 演示脚本
- `国网Demo_规则法源溯源表_V1.md` —— 46 条规则各自的法源出处
- `fe-evidence-bridge_取数契约_v1.2.md` —— 前端取数契约

### 回归与核验

```bash
python _review/regress_v4_v5.py        # 本地四阶段（向后兼容 / 注入 / 改规则 / 闸门）
python _review/verify_platform_v5.py   # 平台侧三阶段（真实调用线上函数）
python _review/make_rules_source.py    # 从函数导出规则源并校验指纹
```

---

## 四、本仓库**未**包含的内容

为避免把客户侧原文与内部运维痕迹放进公开仓库，以下内容被有意排除：

- 投标件全文（`_blind_only/*_投标件全文.txt`）与招标文件原文展开包
- 界面截图（`.png`）
- `apemind-cli` 可执行文件
- 运行日志、审计日志、浏览器配置目录

演示所需的**抽取结果**（`_judge_in_*.json`）已包含，因此不依赖上述原文也能跑通判定链路。

---

## 五、状态

- 判定函数：已发布 **v5**（新增规则注入，向后兼容 v4，六家基线 4962 个字段叶子逐字段一致）
- 规则可配置：P0 已完成（入参注入 + BFF 从规则源注入）
- P1（规则源搬进 dataset）、P2（配置面三道闸）尚未开始

> ⚠️ P2 的三道闸（保存校验 / 回归 / 指纹一致）建好之前，规则源只应由我方维护。
> 改条款文本、适用范围、阈值是安全的；改 `check` 会直接改变判定结论。
