# ApeMind DSH 插件化补齐可行性评估 · 需求—能力矩阵 V1.1 修订

> 编制日期：2026-11-14　｜　上游：《ApeMind×国网招标审核_需求能力差距矩阵与业务闭环.md》（V1，本日）
> 触发问题：「ApeMind 本身有 DSH 功能，目前缺的功能能否以插件方式做能力补齐？」
> 用途：售前架构判断 / 交付形态重选 / 插件开发立项输入。**不覆盖 V1 判定，作为修订输入并存。**
> 边界：本文基于公开官方资料与仓库文档核验，**未在 tgotest 租户或任何 DSH 实例上实跑插件**。不含报价、工期、性能承诺、安全结论。

---

## 〇、结论先行

**能补，而且能补掉 V1 里 16 项「需建设/需集成」中的大部分技术工作量；但补的是「实现方式」，不是「业务闭环的责任与效力」。**

1. **DSH 不是 ApeMind 里的一个功能，是 ApeMind Desktop 的宿主框架。** DSH = DeepSeek Harness，DeepSeek 官方开源（MIT），「一切皆插件」，Cordis 内核支持运行时挂载/卸载与事务性回滚；模型、工具、技能、会话、沙箱、存储、循环、调度、UI 全在插件边界内【F/B】。ApeMind Desktop 是「基于 DSH 的品牌化发行版：版本锁 + 品牌 overlay，不是 fork」【F】。
2. **V1 的三个最硬断点被显著缓解**：B1 规则与判定（规则插件 + 热插拔/回滚）、B5 评测自动迭代（Workflow 承担官方明说「需自有编排」的那层）、B3 外部数据（工具/MCP 插件）；**B4 模型路线甚至转为正向**——DSH 模型路由本身是插件，若「光明唯一指定」属实，恰好是现成适配层【J】。
3. **V1 的 ⑤ 三项一项不动**：在线会签、异常价格判定、自动赋分。技术上 DSH 有 shell 与写能力，反而**更容易越界**；政策禁止 AI 替代判断是责任边界，不因技术可做而改变。
4. **新增两条 V1 没有的断点，且都是硬约束**：
   - **B7 架构边界**：ApeMind 官方 CLI-first 设计文档明文「**CLI 是唯一的 Agent 能力面**」「插件只展示登录状态并打开 ApeMind Web，**不把插件内部 Remote 当成 Agent 的第二套能力入口**」「Desktop 不提供另一套 Agent Tool API」【F】。→ **插件只能补宿主侧，改不了平台侧**（知识库、组织权限、写操作审计、引用回溯仍须走 `apemind` CLI / 服务端 `/api/v2`）。
   - **B6 生产就绪**：DSH 官方 README 明示 *Developer preview*、**THERE WILL BE COMPATIBILITY-BREAKING CHANGES**、运行前须读 safety notice【F】；ApeMind 官网同日仍写 **「DSH integration is in progress.」**【F】；Desktop 仓状态（2026-09-11）「可分发正式安装包 ⛔ 阻塞于 Apple Developer 凭据」「**构建需要外网，不是离线构建**」【F】。
5. **闭环结论不变，但工程量与耦合度下降**：仍是「S1 只可演示、S2 才具备可上线闭环」。变化是 S2 的组件从「自建规则引擎 + 工作流引擎 + 编排服务」变为「**6 个自研插件 + 客户接口 + 1 条 CLI 合同**」。
6. **一句话对客话术**：「ApeMind 出证据，DSH 插件做编排与工作台，规则与签署仍在贵方系统；**AI 只给建议，签字还是人**。」

---

## 一、DSH 事实核验（V1 漏项补正）

### 1.1 是什么

| 事实 | 内容 | 证据 |
|---|---|---|
| 定义 | DeepSeek Harness（dsh），开源 Agent **运行框架/Harness**，不是模型、不是推理服务；公式 `Agent = Model + Harness` | 【F】github.com/deepseek-ai/deepseek-harness README；【B】技术媒体 |
| 许可与状态 | MIT；2026-08-13 进入 **Developer Preview**；原文「**THERE WILL BE COMPATIBILITY-BREAKING CHANGES**」＋「Review the safety notice before running the project」 | 【F】官方 README |
| 架构 | 「**Everything is a Plugin**」，Cordis 内核；插件运行时挂载/卸载、依赖与事件机制、事务性回滚 | 【F】官方 README；【B】技术媒体 |
| 可插部件 | 模型、工具、技能、会话、沙箱、存储、Agent Loop、调度、UI、LLM provider | 【B】官方文档站引述 / 社区拆解 |
| 运行模式 | Web / CLI / SDK / ACP / Desktop；可 headless 嵌入、只引入需要的子包 | 【B】社区与官方文档引述 |
| 编排能力 | Standard 模式含 skills / planning / **goals / subagents / workflows**；Workflow 可用脚本编排多 Agent；append-only session log（系统提示、推理、工具调用与结果、子 Agent 调度、上下文注入）＋ Trajectory 回放/resume/fork | 【B】官方文档站引述、钛媒体、CSDN |
| 模型路由 | 插件化，可接 OpenAI / Anthropic 兼容端点与自定义 base URL；密钥 write-only 存本地 | 【B】官方文档站引述 |

> **注意证据等级**：上表「可插部件 / 运行模式 / 编排能力 / 模型路由」主要来自官方文档站的二手引述与社区拆解【B】，**本次未直接抓取官方文档站逐条核对**，POC 前须由技术侧复核。

### 1.2 ApeMind 与 DSH 的关系（官方一手）

| 事实 | 原文要点 | 来源 |
|---|---|---|
| Desktop 定位 | 「ApeMind Desktop 是**基于 DSH 的 Harness**，Agent 通过 shell 使用外部能力」；「ApeMind Desktop = ApeMind CLI 的图形化控制台 + **DSH 宿主**」 | 【F】Issue #11、CLI-first 设计文档 |
| 交付形态 | 「版本锁 + 品牌 overlay，**不是 fork**」；`upstream.lock` 锁上游 commit；桌面运行时加载 `$DSH_HOME/profiles/desktop` 安装的插件，**保留用户插件，激活失败回滚** | 【F】apemind-desktop README |
| 状态（2026-09-11） | 仓骨架 / dev 模式 / 未签名 `.app` 本机可用 ✅；**可分发正式安装包 ⛔ 阻塞于 Apple Developer 凭据**；**构建需要外网** | 【F】同上 |
| 品牌化修 bug | 2026-10-06 Issue #124 修「品牌化 Desktop 的 **dsh 启动器路径**」，已关闭 | 【F】Issue #124 |
| 官网口径（2026-11-14） | 「**DSH integration is in progress.**」 | 【F】apemind.ai 首页 |
| CLI 改进文档（2026-11-02） | `apemind agent get/update --dry-run/--confirm`、`dataset eval create/get/compare`；「候选生成、应用顺序、停止条件、回滚和跨任务经验检索**需要外部编排**」「**不是独立的一键优化命令**」 | 【F】apemind.ai/docs/developers/agent-improvement.html |
| RSI 页 | 「An unattended improvement loop requires **your own orchestration**… These steps are **not a built-in one-click RSI feature**」 | 【F】apemind.ai/rsi/en |
| 私有化边界 | 「Private deployment **does not automatically make every integration offline**」，须逐一审查模型端点、解析器、搜索服务、MCP 工具；「**A citation is a route back to evidence, not proof that a conclusion is correct**」 | 【F】apemind.ai/enterprise/en |

### 1.3 新口径冲突（须向产品侧核实，勿对客回避）

| # | 冲突 | 处理 |
|---|---|---|
| **C6** | 官网「DSH integration **in progress**」（2026-11-14） vs GitHub 桌面仓「dev 模式/未签名包已实测」（2026-09-11）＋ Issue #124 已修 dsh 启动器（2026-10-06）＋ CLI-first 文档「生产默认关闭个人空间是产品基线」（2026-10-02） | 「**桌面宿主可跑**」与「**平台侧集成完成**」是两件事。客户拿到的是 SaaS、Desktop 还是私有化包，决定插件能力是否可用【?】 |
| **C7** | DSH 官方 README 只有「developer preview / 破坏性变更 / safety notice」；二手来源称「**官方声明尚未经过安全审计**」 | 未核到该表述的官方原文，标【B 待核】，**不得当作已确认安全结论** |
| **C8** | 第三方文章称 DSH「私有化是一等公民、官方提供容器镜像」 vs ApeMind Desktop 仓「构建需要外网、不是离线构建」 | 二者谈的不是同一产物（DSH 上游 vs 品牌化 Desktop 安装包）；国网离线内网构建路径需单独确认【?】 |

---

## 二、决定性边界：CLI-first 单一能力面（B7）

ApeMind 官方 CLI-first 设计文档把插件的边界写死了，这是本轮最重要的发现：

```
DSH Agent ──shell/process──> apemind CLI ──OAuth token──> ApeMind /api/v2
                              （唯一正式接口）            （服务端最终鉴权）
```

| 约束 | 官方原文要点 | 对「插件补齐」的含义 |
|---|---|---|
| 唯一能力面 | 「Agent 使用 ApeMind 的**唯一正式方式是执行 `apemind` 命令**」「CLI 是唯一的 Agent 能力面」 | 插件**不得**直接调 `/api/v2` 读写知识库 |
| 插件禁区 | 「Desktop 的 ApeMind 插件**只展示登录状态并打开 ApeMind Web**，不维护业务页面，也不把插件内部 Remote 当成 Agent 的第二套能力入口」；「Desktop 不提供…**另一套 Agent Tool API**」 | 插件不能补 ApeMind 平台侧业务能力（组织权限、审计、引用、索引） |
| 身份不串线 | 禁止用 Cookie / SLOCK / 其他 Agent 凭据 / 服务器环境 Key 回退；「登录不创建隐藏 API Key」；API Key 只从 stdin 读 | 国网内网不得以环境变量给插件塞 Key |
| 写操作三件套 | `--dry-run` → `confirmation_required` → `--confirm --idempotency-key`；退出码 `4`＝需要用户确认；服务端写操作审计含用户/workspace/request ID | **F03 人机闸门已有现成技术合同**，不必新建工作流引擎 |
| 输出合同 | 每个结构化结果含 `request_id` / `server` / `workspace` / `fetched_at`；stdout 不含令牌、Key、Cookie | 可直接作为 F04 留痕的可关联主键 |
| 服务端最终裁决 | 「服务端是最终权限来源」「不信任 CLI 传来的角色或权限」；权限缩小/Key 撤销后旧会话拒绝 | 宿主侧插件不能放大平台权限 |

**一个已发生的真实坑（实证风险）**：GitHub `apemind-computer` Issue #40（2026-09-01）——DSH 子进程 `scrubbedParentEnv()` 按 `KEY|PASSWORD|SECRET|TOKEN` 剥离环境变量，导致 `apemind` CLI 未认证；issue 同时指出「**agent 还可能把 env.json 里的 key 打到对话里**」【F】。→ 凭据注入路径与泄漏风险必须在 POC 中实测，不能按设计文档假定成立。

---

## 三、V1 矩阵修订：哪些档位被 DSH 改写

> 修订档：**PL**＝DSH 插件可承担主要实现｜**PL+**＝插件做编排/展示，权威数据或判定仍在客户系统｜**NO**＝不可插件化｜**↑**＝较 V1 改善｜**＝**＝不变

### 3.1 V1「③ 需扩展开发」7 项 → 全部可插件化

| ID | V1 | V1.1 | 插件化落点 | 残留依赖 |
|---|:--:|:--:|---|---|
| F04 留痕审计 | ③ | **PL+ ↑** | DSH append-only session log（工具调用/参数/结果/错误/上下文）＋ CLI `request_id` ＋ 审计插件回写 | 法定归档仍在客户档案系统；四 ID 需统一 |
| F11 招标文件合规检测 | ③ | **PL+ ↑** | 规则插件（结构化规则＋Code Mode 执行）＋ evidence 插件（CLI 检索/回读）＋ 问题清单 UI | 规则资产 F01、总部 59 条导入 |
| F12 技术规范书审查 | ③ | **PL+ ↑** | 品类规则插件＋图纸 OCR 插件＋语义比对 | 固化 ID 与品类规则集；批量性能未实测 |
| F32 同屏横向对比 | ③ | **PL ↑** | UI 插件（三栏/分屏/对照表） | 打分偏离预警仍需统计侧 |
| F33 评标报告核验 | ③ | **PL+ ↑** | 语义一致性插件＋算术校验插件；**赋分结论不得由插件给出** | 分值计算错误部分按 ⑤ 处理 |
| F43 异议投诉辅助 | ③ | **PL ↑** | 历史案例库插件＋处理意见模板插件 | 法律效力与投诉流程外置 |
| F55 业务交互（规则广场/看板/分屏/语音） | ③ | **PL ↑** | UI 全可插件化，DSH 强项；插件 profile 按角色分发 | 规则广场数据源依赖 F01 规则服务 |

### 3.2 V1「④ 需外部集成」9 项 → 6 项降为 PL+，3 项保留外部主导

| ID | V1 | V1.1 | 判断 |
|---|:--:|:--:|---|
| **F01 规则库与版本管理**（P0 最大缺口） | ④ | **PL+ ↑↑** | **最大翻转**。Cordis 原生支持插件热插拔、依赖、事务性回滚 → 规则注册表/版本/灰度/回滚可直接做成插件；规则代码生成借 Code Mode。**但规则资产、生效审批、总部与省两级治理流程仍归客户**，插件只是执行壳 |
| **F03 人机协同闸门** | ④ | **PL ↑↑** | 无需新建工作流：CLI-first 已有 `--dry-run` / `confirmation_required` / `--confirm --idempotency-key` / 退出码 4，DSH 提供确认 UI（设计文档把「写操作前的用户确认界面」列为 Desktop 职责） |
| F14 采购计划审核 | ④ | **PL+ ↑** | 规则插件＋ERP 数据工具插件；判定回业务系统 |
| F21 供应商资质核实 | ④ | **PL+ ↑** | 外部数据工具插件（MCP/只读）；接口授权与数据质量仍客户侧 |
| F22 黑名单实时比对 | ④ | **PL+ ＝** | 插件可做触发/定时比对，但**实时节点在交易系统**，不宜让插件进主链路 |
| F23 围串标穿透 | ④ | **PL+ ↑** | 图谱/统计插件出线索与证据，**否决处置建议仍须人工**，不得自动否决 |
| F35 专家回避 | ④ | **PL+ ↑** | 关联规则插件＋专家库只读连接；回避执行仍在评标系统 |
| F41 中标候选人画像 | ④ | **PL+ ↑** | 核验报告插件＋外部信用数据；定标流程外置 |
| F44 履约绩效回灌 | ④ | **PL+ ＝** | 语义回灌可插件，履约状态机仍在客户系统 |

### 3.3 V1「② 平台具备未实测」中被 DSH 直接改善的 2 项

| ID | V1 | V1.1 | 判断 |
|---|:--:|:--:|---|
| F51 多智能体编排 | ②（**未实测**） | **PL ↑** | DSH Standard 含 subagents / workflows / goals，`reportDelivery` 回传唤醒父任务【B】→ 平台侧不再是瓶颈；**但仍未在国网上实测**，且 ApeMind 侧四要素编排与 DSH 编排的职责边界需厘清 |
| F54 版本化评测与回归 | ②（半闭 B5） | **PL ↑** | 官方明说「持续迭代需外部编排、不是一键 RSI」→ **DSH Workflow 正是那一层**：候选生成 → dry-run → `dataset eval create/compare` → 回归 → 回滚/停止；需自研策略、留出集与预算控制 |

> 另：F45 看板、F05 宿主侧角色分层（插件 profile）亦有改善，但不改变平台侧判定，**不升档**。

### 3.4 不变项（必须守住）

| 组 | 项 | 理由 |
|---|---|---|
| **⑤ 边界外** | F15 在线会签、F24 异常价格判定、F31 客观赋分 | 195 号文第十一条辅助性定位；技术上 DSH 能做，**合规上不许**。DSH 有 shell 与写能力 → 必须在插件沙箱与 Agent 指令双重禁用 |
| **① 原生覆盖** | F02 / F13 / F34 / F52 | 仍是 ApeMind 平台能力，与 DSH 无关；F13/F34 依旧是差异化主卖点 |
| **平台侧能力** | 知识库与三类索引、引用回读、组织权限、写操作审计 | B7：插件不得成为第二套能力入口，只能经 CLI |
| **B4 模型路线** | Q3「唯一指定」 | **性质变化**：从纯风险变为「DSH 模型路由插件可作适配层」【J】，但正式文件未核实前仍属头号待确认 |

### 3.5 修订汇总

| 类别 | V1 | V1.1 修订后 | 变化 |
|---|:--:|:--:|---|
| 可插件化承担（PL / PL+） | 0 | **16 项**（原 ③7 + ④9 中 16 项，另 F51/F54 由 ② 改善） | 从「自建系统」降为「自研插件 + 客户接口」 |
| 仍需外部系统主导 | 9 | **3 项半**（F22 实时节点 / F44 状态机 / 规则资产与签署效力） | 显著下降 |
| 明确不可插件化 | 3 | **3 项（不变）** | 政策边界不动 |
| 五断点 | B1–B5 全未闭 | **B1/B2/B3/B5 技术侧缓解，B4 转适配机会**；新增 **B6 生产就绪**、**B7 架构边界** | 闭环仍待 S2 |

---

## 四、建议的 6 个自研插件（S2 工作量清单）

| # | 插件 | 补的缺口 | 输入 → 输出 | 权限与红线 |
|---|---|---|---|---|
| 1 | `gw-rule` 规则注册表 | B1 / F01 / F11 / F12 / F33 | 规则资产 → 规则 ID/版本/灰度/回滚 + Code Mode 判定结果 | **只出建议**；规则生效审批在客户；不改 ApeMind 资源 |
| 2 | `gw-evidence` 证据封装 | F02 / F13 / F34 / F42 | 问题 → 检索/回读/引文校验/差异清单 | **必须经 `apemind` CLI**；不直连 `/api/v2`；不读凭据 |
| 3 | `gw-datasource` 外部数据 | B3 / F14 / F21 / F23 / F35 / F41 | 接口清单 → 只读拉取 + 缓存 + 异常标注 | **默认只读**；回写须人工确认＋幂等键；不进交易主链路 |
| 4 | `gw-review-ui` 复核工作台 | F03 / F32 / F45 / F55 | 问题清单/矛盾对照 → 三栏体检、**确认抽屉**、规则广场、看板 | 退出码 4 必须呈现；dry-run 差异可见；不得隐藏 AI 建议来源 |
| 5 | `gw-audit` 审计桥接 | F04 / R5 | session log + `request_id` + 四 ID → 客户审计库/档案系统 | 技术轨迹 ≠ 法定留痕；须双轨关联，不得互相替代 |
| 6 | `gw-eval-orchestrator` 评测编排 | B5 / F54 | 诊断 → 候选配置 → dry-run → eval compare → 回归/回滚/停止 | 不改评分标准与留出集；预算与停止条件显式；官方「非一键 RSI」 |

**插件交付纪律**：全部自研、白名单、版本锁、签名校验、离线分发；**禁止第三方市场插件入内网**（社区插件多为可执行代码，含趣味/外部联网类）。

---

## 五、插件补不了的四类（防止售前过度承诺）

1. **政策与责任**：AI 不得自动否决/定标/赋分；复核签署的法律效力来自客户制度与系统，不来自插件日志。
2. **平台内建能力**：知识库、索引、图谱、引用回读、组织权限、服务端写操作审计 —— B7 规定必须 CLI-first。
3. **权威数据与规则资产**：总部 59 条规则、省级本地化规则、黑名单/征信/发票/专家库/ERP 的**授权、质量与时效**，插件只是连接壳。
4. **形态与生产就绪（B6）**：DSH 是桌面/Web 宿主 + 本地 `$DSH_HOME/profiles/desktop` 插件组合，与国网「内网集中式多人会签、总部/省两级、评标基地隔离」存在**形态错配**；叠加 Developer Preview、破坏性变更、官网 integration in progress、正式安装包阻塞、构建需外网、Issue #40 凭据坑 → **不能直接进生产，须先过内网适配与安全复核**。

---

## 六、架构纪律 7 条（写进方案，不可省）

1. **单一能力面**：ApeMind 一切读写只经 `apemind` CLI；插件禁止直连 `/api/v2`、禁止 Cookie/环境 Key/其他 Agent 身份。
2. **写操作三件套**：`--dry-run` → `confirmation_required` → `--confirm --idempotency-key`；退出码 4 必须在 UI 可见。
3. **只读优先**：外部数据默认只读；任何回写客户系统须人工确认＋幂等键。
4. **⑤ 三项硬禁**：插件与 Agent 指令双重禁用自动否决、定标、赋分；DSH shell 能力须沙箱/白名单收敛。
5. **凭据不入上下文**：禁环境变量注入 Key（Issue #40 实证）；用 CLI OAuth + 系统凭据库；插件不得读凭据文件、不得把 Key 打进对话。
6. **供应链**：仅自研白名单插件、签名＋离线分发、`upstream.lock` 式版本锁、每次升级跑固定评测集回归。
7. **双轨留痕**：DSH session log 是技术轨迹，客户审计库是法定留痕；用统一四 ID（规则/文件版本/模型+提示词版本/复核动作）关联，不互相替代。

---

## 七、交付形态（V1 三形态的 DSH 化重述，请主公拍板）

> 三者共同前提：**ApeMind 出证据、DSH 插件做编排与工作台、客户系统握规则与签署**。

| | **A · 插件化证据工作台（推荐起步）** | **B · DSH headless 服务端编排 + 客户门户（生产目标态）** | **C · 不引入 DSH，MCP + 外置微服务（保守兜底）** |
|---|---|---|---|
| 形态 | ApeMind Desktop / DSH 宿主 + 6 个自研插件；ApeMind 平台作知识层 | DSH 以 SDK/headless 跑内网服务端，按角色分发 profile；UI 全在客户 ECP 门户 | ApeMind 只出证据；规则服务/工作流/评测编排均为独立微服务，经 MCP 接入 |
| 页面布局 | ①审查任务台（批次/文件/状态）②**三栏体检页**（问题清单｜依据条款｜原文定位）③**左右分栏矛盾对照**④**人工确认抽屉**（dry-run 差异＋幂等键）⑤规则广场/插件版本台⑥轨迹与评测视图 | ①ECP 招标文件编制页内嵌「体检结果」抽屉②评标页「依据一键定位」面板③确认弹窗（双人复核）④客户门户内的规则与审计视图 | ①客户门户审查页②独立规则管理台（版本/灰度/回滚）③独立评测与审计台④MCP 连接状态视图 |
| 闭环 | R1–R5 技术侧可闭、R6 由评测编排闭 | R1–R6 全闭（法定效力仍在客户系统） | R1–R6 全闭，工程量大 |
| 优点 | 最快验证插件化补齐；CLI 合同现成；改动集中在宿主侧 | **规避桌面端形态错配**，多人会签/两级组织/内网集中部署最贴合国网 | 不引入 Developer Preview 组件，安全与等保阻力最小 |
| 代价/风险 | 桌面端形态错配；B6 生产就绪未证 | 需验证 DSH headless 服务端可行性【?】；工程量最大 | 放弃 DSH 的编排与热插拔红利，回到 V1 的自建工作量 |
| 适用 | **S1 POC / 插件可行性验证** | **S2 生产交付** | DSH 未过安全审查、或客户明确禁用预览版组件时 |

**推荐路径**：**A 做 S1（2 周等价，验证 6 插件中先做 1/2/4 三个）→ B 做 S2 生产态 → C 作为兜底**。Q-D1/Q-D3 未核实前，不向客户承诺 DSH 生产可用。

---

## 八、质量门禁与如实披露（红队自查）

| 项 | 结论 |
|---|---|
| **本轮实测状态** | **零实测**。结论基于官网、官方 GitHub 仓库、CLI-first 设计文档、CLI 文档、Issue 与二手技术报道的静态核验；**未在 tgotest 租户或任何 DSH 实例上运行过插件、未验证 CLI confirmation 全链路、未验证 headless 部署**。V1 的「国网数据/内网/国产算力/光明大模型/TB 级批量六项零实测」依然成立 |
| **证据等级** | DSH「可插部件/运行模式/Workflow/Goal/subagent/模型路由/profile」多为【B】二手引述官方文档站，未逐条核官方原文；「未经过安全审计」为【B 待核】 |
| **新增口径冲突** | C6（官网 in progress vs 仓库已可跑）、C7（安全审计表述）、C8（离线构建）—— 均未决，须产品侧书面确认 |
| **不得表述为** | 「ApeMind 自带插件市场」「插件可改平台权限」「DSH 已生产就绪」「插件能替代规则引擎/工作流」「AI 可自动否决」 |
| **沿用 V1 约束** | 195 号文第十一条辅助性定位、1358 号文全过程可追溯；C1–C5 冲突全部有效；Q3 唯一指定模型仍是头号待确认 |
| **本文未涉及** | 报价、工期、合同条款、性能承诺、等保结论、法律意见、插件开发人天 |
| **门禁判定** | 🟡 **有条件通过**：作为售前架构评估与插件立项输入可用；因 B6/B7 与零实测，**不得当作可交付方案或已批准方案** |

---

## 九、待确认与行动清单

| # | 待确认 / 动作 | 责任方 | 验收证据 |
|---|---|---|---|
| **Q-D1** | 主公所说「ApeMind 本身有 DSH」具体是哪个入口与版本？SaaS 租户 / ApeMind Desktop / 私有化包？ | 主公 + 产品 | 版本截图或产品书面确认 |
| **Q-D2** | DSH 是否随 ApeMind 私有化交付？内网 **headless 服务端**能否跑、插件 profile 能否多用户共享？ | 原厂技术 | 部署形态说明 + 内网验证 |
| **Q-D3** | 官网「integration in progress」的完成范围与生产可用版本？C6 如何解释？ | 原厂产品 | 路标/发版说明 |
| **Q-D4** | DSH 安全审计结论、等保适配、第三方插件政策、离线构建路径（C7/C8） | 安全 + 交付 | 官方声明或复核报告 |
| **Q-D5** | 插件由谁开发、知识产权与升级维护责任如何划分？ | 商务 + 法务 | 合同条款草案 |
| **Q-D6** | 若「光明唯一指定」属实，是否经 **DSH 模型路由插件**接入？ | 架构 + 客户 | 模型适配方案 |
| **A1** | 先做 1 号最小验证：在测试环境装一个自研插件，跑通 `apemind` CLI 的 `--dry-run` → 确认 → `--confirm` 全链路，并复现/规避 Issue #40 凭据坑 | 交付 | 一次可回放的执行轨迹 + 退出码 4 截图 |
| **A2** | 用 V1 的 F13/F34 题库，验证插件化后**引用与证据边界不退化** | 交付 | 基线评测报告（含失败题） |
| **A3** | 主公拍板 A/B/C 后，出正式《插件化方案架构设计书》与插件清单规格 | 主公 → 架构 | 拍板记录 |

---

## 附录 · 证据台账（本轮新增）

| # | 来源 | 日期 / 检索日 | 等级 | 支撑结论 |
|---|---|---|:--:|---|
| D01 | apemind.ai 首页「DSH integration is in progress」 | 2026-11-14 | F | C6、B6 |
| D02 | apemind.ai/rsi/en「not a built-in one-click RSI feature」 | 2026-11-14 | F | B5 可插件化 |
| D03 | apemind.ai/enterprise/en 私有化与 citation 边界 | 2026-11-14 | F | B6、平台侧不可插件 |
| D04 | apemind.ai/docs/developers/agent-improvement.html「需外部编排」 | 更新 2026-11-02 | F | 插件 6 号、F54 |
| D05 | github.com/apecloud/apemind-desktop README（版本锁/overlay/状态表/外网构建） | 2026-09-11 | F | B6、C8 |
| D06 | apemind-desktop Issue #11（CLI-first 架构） | 2026-09-14 | F | B7 |
| D07 | apemind-desktop CLI-first 设计文档（唯一能力面/插件禁区/写操作/凭据） | 2026-09-14，含 2026-10-02 基线 | F | B7、F03、F04、纪律 1–5 |
| D08 | apemind-desktop Issue #124（dsh 启动器路径，已关闭） | 2026-10-06 | F | C6 |
| D09 | github.com/deepseek-ai/deepseek-harness README（插件架构/Developer Preview/破坏性变更/safety notice） | 2026-11-14 检索 | F | B6、§1.1 |
| D10 | 技术媒体 / 社区对 DSH 四种模式、Workflow、Goal、session log、模型路由、profile 的拆解 | 2026-08～11 | B | §1.1，待技术侧复核 |
| D11 | github.com/apecloud/apemind-computer Issue #40（DSH 剥离 KEY 环境变量、CLI 未认证、Key 可能进对话） | 2026-09-01 | F | 纪律 5、POC 必测项 |
| D12 | 第三方 DSH 私有化部署与插件生态介绍（容器镜像/内网/profile） | 2026 | B | C8、形态 B 可行性待核 |

> 追溯链：V1「31 项需求 → 五断点 B1–B5 → 分期 S0–S3」→ 本轮「DSH 事实 → B7 边界 → 16 项降为插件化 → 6 插件清单 → 三形态 A/B/C → Q-D1..D6」。
