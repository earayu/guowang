# 国网招标审核 Demo · ApeMind「封装层」能力核实与 D3 构建修订（V5）

> 编制：2026-11-14 12:20（GMT+8）
> 主公本轮令（含截图纠偏）：**「不是 DSH，ApeMind 把 DSH 做了封装；缺的可以部署；请咨询看看 ApeMind 文档」**，并于上一轮拍板 **D3 全业务工作台 / 恢复 Q-D1 / 授权 A1 最小验证**。
> 上游：V2《业务目标可行路径判定》→ V3《基于目标的任务清单·剔除私有化》→ V4《ApeMind × DSH 前端业务工作台构建方案》→ **本轮 V5 修订**。
> 性质：**售前口径修订 + 官方文档核验 + 本机实测记录 + D3 开工依据**。不是方案书、不是验收结论、不是已批准方案。

---

## 〇、执行摘要（结论先行）

**一句话：主公是对的，臣前几轮的落点偏了。DSH 不是交付物，ApeMind 对外的可交付物是「封装后的 CLI + Desktop + 平台侧可部署资产（Skill / Function / MCP / Dataset / Task）」。因此 D3 不再写「自研 DSH 插件」，改写为「本地业务前端 + 经 `apemind` CLI 单面取数 + 把缺失业务能力以 Skill / Function 部署进租户」。**

| 项 | V4（上一轮，需修订） | **V5（本轮，已核实）** |
|---|---|---|
| DSH 定位 | 开源框架，自研插件挂 `$DSH_HOME/profiles/desktop` | **被 ApeMind 封装在内部；对客不暴露 DSH 插件 API** |
| 前端实现 | DSH UI 插件（6 个 `fe-*` 插件） | **独立业务前端**（技术栈不限）+ 平台侧**可部署资产** |
| 唯一能力面 | 从 CLI-first 设计文档推导（B7，二手） | **`apemind` CLI 官方公布、机器可读**：`capabilities --json` 263 条命令 |
| 规则/判定/交付物 | 外置规则引擎 + 工作流 + 审计库 | **Skill / Function / turn consent / dataset eval**（平台原生，可部署） |
| 「缺的可以部署」 | 未展开 | **已落地**：CLI 真装真跑；Skill/Function/MCP/Task 均有部署命令 |
| 不变 | 私有化剔除、O1–O5、L1 demo 档、195 号文辅助性定位、前端静态禁区 | **全部不变** |

**本轮最关键的三条硬证据（均为本机真跑或官方原文）：**

1. **官方 CLI 已下载、校验、执行**：`apemind.exe` **v0.7.56**，13,711,872 bytes，SHA-256 `19c5ffae…15b12b731b` 与官方 `checksums.txt` 一致；`--help` / `--version` / `doctor` / `capabilities --json` / `guide` / `guide platform` 全部 exit 0。落在工作区 `apemind-cli/`，**未跑远程安装脚本、未改系统 PATH、未写入 `%LOCALAPPDATA%`**。
2. **退出码 `4` = 需要确认或冲突**，出自 CLI 自带 `apemind guide platform` 第 128 行【A】；确认三件套 `--dry-run → confirmation_required → --confirm --idempotency-key` 是**官方明文**，不是臣从设计文档推的。
3. **官方文档站搜索索引里 `plugin` / `skill` / `deploy` 关键词合计 0 次**（`docs/_assets/docs.js`），而 CLI 命令树里有 `skill`(14)、`function`(15)、`mcp`(5)、`task`(15)、`turn`(17) —— **扩展面在 CLI 命令与平台资产，不在 DSH 插件**。

> **一句话给客户**：我们不需要客户装 DSH、也不需要改造 ApeMind 平台；只用一个官方 CLI，把业务规则做成 Skill、把结构化交付物做成 Function、把人工确认接到 `turn consent`，前端只负责呈现与收集人工动作。

---

## 一、Q-D1 核实结果（F11 门禁 —— 已核实，解除阻塞）

### 1.1 主公截图与官方发布元数据逐字对齐

| 项 | 官方读数 | 来源 |
|---|---|---|
| 下载页 | `/download`，导航 **Desktop / CLI / Agent 指南 / 文档** | 官网 `/download` 原始 HTML【A】 |
| Desktop | **v0.2.2-rc.1+apemind.154**，发布 **2026-11-12**；四平台 mac-arm / mac-intel / **windows / linux**；副标题「**已内置 CLI，无需重复安装**」 | `/api/v2/public/desktop-release`【A】＋主公截图 |
| Windows Desktop 资产 | `apemind-desktop-0.2.2-rc.1+apemind.154-win-x64-**unsigned**.exe` | 同上【A】——**未签名，装机需走客户软件白名单** |
| CLI | **v0.7.56**，发布 **2026-11-12**，`enabled:true`，6 个二进制资产 + 2 个安装脚本 | 同上【A】 |
| CLI 安装 | macOS/Linux `curl … install.sh \| APEMIND_VERSION=latest sh`；Windows `$env:APEMIND_VERSION="latest"; Invoke-RestMethod …/install.ps1 \| Invoke-Expression` | `/download` ＋ `/download/cli.md`【A】 |
| CLI 本质 | 「**standalone binary; Node.js, Python and a local server are not required**」「**Installing the CLI does not deploy a local server**」 | `/download/cli.md`【A】 |

### 1.2 臣读到的安装脚本（已下载到工作区，逐行审过，**未执行**）

- `apemind_install_ps1.txt`：解析 `APEMIND_VERSION`（`ap/vX.Y.Z`，`latest` 走 `/api/v2/public/apemind-cli/latest` 指针）；按 `PROCESSOR_ARCHITECTURE` 选 amd64/arm64；下载 `apemind-windows-$Arch.exe` + `checksums.txt`；**SHA-256 校验**；安装到 `%LOCALAPPDATA%\ApeMind\bin\apemind.exe`；把该目录追加到**用户 PATH**；临时目录用 `finally` 清理。
- `apemind_install_sh.txt`：同逻辑，装到 `~/.local/bin`。
- 两条脚本**都不部署服务端、不安装 DSH、不写凭据**；官方还主动提示「one-line commands execute a remote installer，先读脚本」「SHA-256 不是数字签名」。

> 臣的实际部署方式比官方脚本更保守：**直接下载二进制 → 本地算 SHA-256 比对官方清单 → 放工作区目录 → 直接调用绝对路径**，因此**零系统副作用**。

### 1.3 「DSH 封装」的准确含义（本轮口径定稿）

| 层 | 事实 | 对客是否暴露 |
|---|---|---|
| **平台侧（SaaS）** | 官网 `#governance` 仍写 **「DSH integration is in progress.」** | 否；C6 仍有效，**平台侧集成未完成** |
| **客户端侧** | Desktop `v0.2.2-rc.1+apemind.154` 已发布、内置 CLI；CLI `v0.7.56` 独立发布 | **是**，可下载可安装 |
| **内部** | DSH（DeepSeek Harness）作为 Desktop 的运行框架被封装 | **否**；官方文档站无 `plugin` 页面、无插件开发指南 |

> **因此 C6 不是矛盾而是分层**：「平台侧 DSH 集成进行中」与「客户端封装版已可下载」同时成立。对客一页纸须**并列写出**，不得说「DSH 已集成完成」，也不得说「DSH 不可用」。

### 1.4 Q-D1 结论（写死）

**主公所说的「ApeMind 本身有 DSH」，对应的是「ApeMind Desktop（内置 CLI）+ 独立 ApeMind CLI」这一封装发行版，不是 SaaS 网页版里的一个开关，也不是可直接开发插件的裸 DSH。**
→ D3 的前端**不能**依赖「装 DSH 再写插件」；**应**依赖「装官方 CLI + 用平台侧可部署资产」。F11 判定：**已核实，不再阻塞**，但把 F13（C6 书面说明）升为对客必做。

---

## 二、「缺的可以部署」—— 能力面重判（本轮最重要的修订）

> V4 把 6 个 `fe-*` 都写成「DSH 插件」，并认为规则引擎 / 工作流 / 审计库要外置。本轮按 CLI `capabilities --json`（263 条命令）逐项重判。

### 2.1 V4 缺口 → ApeMind 封装层原生承载（逐条）

| V4 认为「缺」 | **官方可部署资产** | 真实命令（v0.7.56） | 证据 |
|---|---|---|---|
| F01 规则库 / 版本 / 灰度 / 回滚 | **Skill**（`SKILL.md` 目录 / ZIP / Git 导入；`--version` 更新） | `skill upload --dir\|--file`、`skill import --git-url`、`skill sync`、`skill update --version N`、`skill get/file`、`skill enable/disable`、`agent skill add/remove` | `apemind skill --help`【A】 |
| 结构化判定 / 差异清单 / 交付物生成 | **Function**（`function.json + main.py` → HTTP API；`ctx.llm` / `ctx.api.get` 可用） | `function init/diff/apply/invoke/logs/trace/history/rollback` | `apemind function explain`【A】 |
| F03 人机协同闸门 | **`turn consent`**（`approved\|denied`，写入服务端 Turn 事件）＋ CLI `--confirm`（退出码 4） | `turn watch`、`turn consent TURN_ID --chat-id … --decision approved`、`turn elicit`、`turn answer` | `guide platform` §3【A】 |
| 外部主数据 / 业务工具 | **MCP 工具** | `mcp tools list/describe/call`、`mcp resources list/read` | CLI help【A】 |
| F04 业务级留痕 | **audit**（自己的操作记录）＋ Turn 事件 | `audit list --limit 20`（需 `audit.read`）、`chat export` | `guide platform` §6【A】 |
| F10 / F54 评测回归 | **Dataset 版本化评测** | `dataset version publish`、`dataset eval create --confirm --wait`、`eval compare`、`eval retry` | `guide platform` §4【A】 |
| 定时任务 / 编排 | **Task**（官方明说 RSI 需自有编排，Task 提供承载） | `task create/trigger/pause/delete --confirm/run list` | `guide platform` §4【A】 |
| F13 跨文件矛盾 / F34 溯源 | **CLI 检索句柄** `docID@解析版本:行区间` | `search/grep --kb`、`read HANDLE`、`outline --grep`、`fetch` | `apemind guide`【A】 |
| 两阶段上传坑（R5） | CLI 已封装 | `document upload --wait`＝上传→确认→等索引；或 `upload → document confirm → document wait` | `document upload --help`【A】 |
| 前端唯一取数白名单 | **`capabilities --json`** 机器可读清单 | `apemind capabilities --json` | 本机实测【A】 |

### 2.2 `capabilities --json` 真实读数（本机 exit 0）

| 指标 | 读数 |
|---|---|
| `data.command_details` | **263 条**命令 |
| `local.implemented = true` | **263 / 263** |
| 带 `--dry-run` | **115** |
| 带 `--confirm` | **29** |
| 带 `--idempotency-key` | **5** |
| `required_oauth_scopes` 去重 | **36** 个（如 `agent.read/write`、`chat.read/write`、`dataset.*`、`apikey.*`、`skill.manage`、`function.*`） |
| 输出信封 | `type / server / workspace / fetched_at / request_id` —— **正是 `fe-evidence-bridge` 要的字段** |
| 授权声明原文 | 「`required_oauth_scopes` are local preflight hints; **the server rechecks every request**, and API-key permissions remain server-enforced」 |

> **这条直接改写了 `fe-evidence-bridge` 的实现**：白名单不必人工编，从 `capabilities.json → command_details[].path` 自动生成；`request_id` 由 CLI 信封原生给出，不用前端自己造。

### 2.3 B7（CLI-first）的重新定性

V4 把 B7 当成「限制前端的红线」。核实后应改写为：**B7 不是限制，而是官方已经提供好的、机器可读的单一能力面。**

- 官方 `apemind api PATH` 明确：「复用 CLI 的认证、workspace header、错误和输出合同；**不能修改 Authorization、Cookie 或 Host，也不能跨服务地址发送凭据**」。
- 官方 `capabilities` 给出 `credential_boundary` / `protocol` / `server_api_prefix` 字段。
- → 前端只要**只调 CLI**、不直连 `/api/v2`、不注入凭据，就天然合规；不需要再论证「插件算不算第二套能力入口」。

---

## 三、A1 最小验证（F12）—— **部分通过**，如实列出跑通与没跑通

### 3.1 已真跑（本机，非资料推断）

| # | 动作 | 真实读数 |
|:--:|---|---|
| 1 | 取 latest 指针 | `v0.7.56` |
| 2 | 下载 `apemind-windows-amd64.exe` | HTTP 200，**13,711,872 bytes**，7.6 s |
| 3 | SHA-256 校验 | 官方 `19c5ffae2519ce328792eb88cd0b687733c11776e1a6b81434a28c15b12b731b` ＝ 本地计算值，**MATCH True** |
| 4 | `apemind --version` | `v0.7.56`，exit 0 |
| 5 | `apemind --help` | 21,751 字符 / 304 行 / **276 条命令**，exit 0 |
| 6 | `apemind capabilities --json` | 60,342 字符，263 条 `command_details`，exit 0 |
| 7 | `apemind guide` / `guide platform` | 1,756 / 8,894 字符，exit 0；**退出码 4 定义在此** |
| 8 | `apemind doctor` | exit 0，`status: warn`：`config_dir = C:\Users\linkz\AppData\Roaming\apemind`、`accounts: 0`、`server: https://apemind.ai` |
| 9 | `apemind auth status --json` | `{"logged_in":false,"accounts":[],"current":""}` ＋ `request_id` |
| 10 | 写/删探针 10 次（`api POST/GET`、`agent update --dry-run`、`knowledge/skill/api-key/agent/dataset item/document delete`、`admin audit retention set`） | **全部 exit 3**，`code=authentication_required`，错误信封含 `exit_code:3 / request_id / fetched_at / server / type:error / workspace:null` |
| 11 | `turn consent --help`、`function --help/explain`、`skill --help`、`document confirm --help`、`api-key create --help` | 全部 exit 0，契约已读 |

### 3.2 官方明文（非本机触发）

- `apemind guide platform` 第 128 行：**「退出码 `4` 需要确认或冲突」**；第 33 行：「删除、撤销、暂停、取消发布等不可逆操作必须加 `--confirm`，否则返回 `confirmation_required` **且不发请求**」；第 34 行：错误信封顶层返回 `idempotency_key`。
- `apemind guide`（检索）列的是 `0/2/3/5/6/7/8/9`，**没有 4** —— 因为检索类命令不触发确认，两处不冲突（记为 **C12 范围差异**）。
- → **V4 写的「确认三件套 + 退出码 4」方向正确**，但出处应由「CLI-first 工程设计文档」改为 **CLI 自带 `guide platform`**，且须说明 `4` 同时表示「或冲突」。

### 3.3 Issue #40 凭据坑 —— 设计规避已证实，运行时未验证

| V4 的担心 | 封装层的实际设计 | 证据 |
|---|---|---|
| DSH 子进程按 `KEY\|PASSWORD\|SECRET\|TOKEN` 剥离环境变量致 CLI 未认证 | CLI **不依赖环境变量传凭据**：`auth connect --api-key-stdin`（stdin 读取）、`auth login`（浏览器 OAuth）、`auth login --device`（设备码） | `auth --help`【A】 |
| Key 可能被 agent 打进对话 | `api-key create --secret-file FILE`：**只写新文件、不覆盖、不输出 stdout、不自动切换账户、不进 Agent 日志/版本库**；官方禁令「Never put passwords or access tokens in prompts or command-line arguments」 | `api-key create --help` ＋ `/download/cli.md`【A】 |
| 配置里藏凭据 | `apemind config`：「**配置只保存客户端行为，不保存认证材料**」 | `config --help`【A】 |
| 前端可直连 API 绕过鉴权 | `apemind api` 禁止改 `Authorization/Cookie/Host`，服务端逐次重鉴权 | `api --help` ＋ capabilities 授权声明【A】 |

> **判定**：凭据路径在**设计层已被封装层规避**；但本轮**未登录、未起子进程**，所以「运行时不复现」**未实测**，不得写成「已解决」。

### 3.4 未跑通 / 阻塞项（反假绿）

- ❌ **服务端 `--dry-run → confirmation_required(exit 4) → --confirm --idempotency-key` 全链路未跑**：CLI `logged_in=false`，认证先于确认预检（10 次探针全部 exit 3）。
- ❌ **设备码登录尝试失败（真实读数）**：`apemind auth login --device` 后台运行 **100 s 后 `subprocess.TimeoutExpired`**（12:18:26→12:20:27），无 stdout 输出、需人工在浏览器批准设备码；本会话为非交互环境，臣**未获批、未擅自绕过**。故 `auth status` 仍 `logged_in=false, accounts=0`。
- ❌ 未创建一个可回放的真实写操作轨迹；未验证 `turn consent` 在真实 Turn 上的行为。
- ❌ 未安装 Desktop（Windows 资产 **unsigned**，需客户软件白名单；本轮 L1 单机 demo 用 CLI 即可，不装）。
- ❌ 未联系原厂；全部为**公开文档 + 公开端点 + 官方二进制**的静态与本机核验。
- **A1 门禁判定：🟡 部分通过** —— 部署、能力面、契约、凭据边界已核实；**服务端写链路待一次登录**。

### 3.5 补齐 A1 的最短路径（一步）

主公在本机任选其一（臣不擅自创建持久凭据）：

```
# 方式 A：浏览器授权（推荐，最小副作用）
apemind auth login

# 方式 B：无浏览器 / 设备码
apemind auth login --device
```

登录后臣用同一工作区 CLI 跑 `a1_verify_after_login.py`（本轮已备好），一键产出：dry-run 响应 → 退出码 4 → `--confirm --idempotency-key` 结果 → `auth status` → `doctor`，全部落盘为可回放 JSON。
若主公授权代管凭据，也可用 `apemind auth login --scope apikey.write` + `api-key create --secret-file` 建**最小权限临时 Key**（用完 `api-key revoke --confirm` 撤销），但**本轮未做**。

---

## 四、D3 构建方案修订（口径改了，页面不变）

### 4.1 三层架构改名

```
L2 业务前端层   独立前端（技术栈不限）   P1..P7 / 三段式对象树 / 三栏体检 / 双版对照 / 确认抽屉 / 状态机
                    │ 只发「问题」、只收「CLI 结构化结果」；不解析原文、不直连 /api/v2
                    ▼  fe-evidence-bridge（白名单由 capabilities.json 生成；信封带 request_id）
L1 封装层       apemind CLI v0.7.56  +  平台侧可部署资产
                    Skill（审查规则/差异指引，版本化）
                    Function（差异清单 / 待澄清事项表，可 invoke / rollback）
                    turn consent（人工同意·否决，写服务端 Turn 事件）
                    MCP tools（外部主数据只读） · Dataset eval（回归） · Task（编排）
                    │ OAuth 由 CLI 自管；凭据不进前端、不进环境变量
                    ▼
L0 证据层       ApeMind SaaS 平台   知识库 / 向量·全文·图谱 / Agent / 引用 / 组织权限 / 调用审计
                                    —— 平台侧一行不改
```

### 4.2 六个 `fe-*` 重新落地（不再是「DSH 插件」）

| V4 名称 | V5 落地形态 | 承载页面 | 平台侧部署件 |
|---|---|---|---|
| `fe-shell` | 前端模块 | P1 / P2 | — |
| `fe-evidence-bridge` | 前端唯一取数通道 | 全部 | 白名单 ← `capabilities --json` |
| `fe-review` | 前端模块 ＋ 人工动作 | P3 / P4 / P5 | **Skill**（审查规则）+ **`turn consent`** |
| `fe-deliverable` | 前端渲染 | P6 | **Function**（生成待澄清事项表） |
| `fe-trace-eval` | 前端模块 | P7 | **dataset eval** ＋ `audit list` |
| `fe-rule-assets` | 前端展示规则 ID/版本 | P3 依据卡 | **Skill**（`skill update --version`）＋ 规则生效审批仍归客户 |

> **不变**：Finding 状态机 `CANDIDATE → CONFIRMED/MODIFIED/REJECTED` 强制 `actor + timestamp + 意见`；前端**静态禁区**（无「通过 / 否决 / 赋分 / 定标」控件）；195 号文第十一条翻译成 UI 约束；**业务判定权与法定责任仍在人**。

### 4.3 P1–P7 页面布局：保留，只改「谁在算」

V4 §5 的七页是从 O1–O5 与 R1–R7 正向推导出来的，**与实现技术无关，因此全部保留**。逐页「谁在算」改为：

| 页面 | 谁在算（V5） | 页面特有约束（回指） |
|---|---|---|
| P1 批次·标包导航台 | CLI `document list` / `capabilities` | 三段式标识、逐份状态灯、未入库状态（R1 R3 R4） |
| P2 体检发起台 | CLI `turn create` / `task trigger` | **空库拦截**：先校验 `document confirm` 已完成（R5） |
| P3 三栏体检页 | CLI `search/grep/read` 句柄回读 | 伪命中标记；每条 `候选·需人工判定`（R6 R7） |
| P4 双版矛盾对照 | **Function**（结构化比对）＋ CLI 原文 | 左右分栏、四项对齐、复用标记（R1 R2） |
| P5 人工确认抽屉 | **`turn consent`** ＋ CLI `--confirm`（退出码 4 可见） | dry-run 差异、幂等键、`request_id`（O5） |
| P6 待澄清事项表 | **Function** 输出 → 前端表格 | 含「仍缺的文件」列（O2） |
| P7 轨迹与评测 | `audit list` / `turn list` / `dataset eval compare` | 失败题独立「证据不足」卡（R3 R4 R6） |

**七页可预览线框已产出**：`国网Demo_D3_七页面线框.html`（本轮交付，含静态禁区检查清单）。

---

## 五、口径冲突台账（新增 3 条，沿用 C1–C9）

| # | 冲突 | 处理 |
|---|---|---|
| **C10** | 官方 `docs/developers/agent-improvement.html` 示例写 `apemind agent update … --confirm`，但 **v0.7.56 `agent update --help` 只有 `--dry-run/--input/--workspace`，无 `--confirm`** | 对客材料**以 CLI `--help` 为准**；`--confirm` 只用于不可逆命令与 `apemind api`。已请原厂核文档版本 |
| **C11**（C6 细化） | 官网 `#governance`「DSH integration is in progress」vs Desktop/CLI 已发布可下载 | **并列说明**：平台侧集成未完成、客户端封装已发布；不得说「已集成完成」 |
| **C12** | `guide`（检索）退出码清单无 `4`，`guide platform` 有 `4 = 需要确认或冲突` | **非冲突，范围不同**；对客统一写「不可逆操作未确认 → 退出码 4」 |

---

## 六、F01–F15 任务状态刷新（D3 已拍板）

| # | 任务 | V4 状态 | **V5 状态** |
|---|---|---|---|
| F01 | 155 份三类索引收敛 | 进行中 | **进行中**（12:06:53：向量/全文 155 ACTIVE；图谱 50 ACTIVE / 32 RUNNING / 73 PENDING） |
| F02 | 收敛后跑 V1–V7 + 附测 8 题 | 待依赖 | **待依赖**（题库未跑，不与索引抢配额） |
| F03 | 定 D1/D2/D3 | 待拍板 | ✅ **已完成：D3** |
| F04 | `fe-evidence-bridge` 取数契约 | 待依赖 | ✅ **已出**（本轮交付，基于 263 条 capabilities） |
| F05 | `CANDIDATE` 状态机 + P5 确认抽屉 | 待依赖 | 🟡 契约已定，**待登录验退出码 4** |
| F06 | P1 三段式对象树 + 状态灯 | 待依赖 | 🟡 **线框已出**，待 F02 读数 |
| F07 | P3/P4/P7 与失败题卡 | 待依赖 | 🟡 **线框已出**，待 F02 |
| F08 | P6 交付物 + 录屏 | 待依赖 | 待依赖 |
| F09 | 前端静态禁区检查 | 待依赖 | 🟡 **检查清单已随线框给出**，待实现后扫描 |
| F10 | 评测集版本化与回归 | 待依赖 | 🟡 承载件已明确为 `dataset eval` |
| **F11** | **Q-D1 入口版本** | 阻塞 | ✅ **已核实**（§1）；结论是「用封装层，不用裸 DSH」 |
| **F12** | **A1 最小验证** | 阻塞 D3 | 🟡 **部分通过**（§3）；服务端写链路待登录 |
| F13 | C6 / C11 对客一页纸 | 待核 | **升为对客必做** |
| F14 | PPT / 一页纸 / 逐字稿 | 待依赖 | 待 F02 |
| F15 | G3 剩余 2/3（手写 5 问 + 对接人） | 阻塞 | **仍阻塞**（缺人，非技术可解） |

---

## 七、门禁、边界与如实披露

| 项 | 结论 |
|---|---|
| **不变红线** | 195 号文第（十一）条辅助性定位；**AI 不自动判定 / 否决 / 赋分 / 定标**；法定责任不转移；剔除私有化不变；O1–O5 限 **L1 demo 档** |
| **新增实施边界** | Windows Desktop 资产 **unsigned** → 本轮 L1 只用独立 CLI，不要求客户装 Desktop；若日后要装，须走客户软件白名单 |
| **凭据边界** | 前端不接触凭据；CLI 用 OAuth / stdin / secret-file；`apemind api` 禁止改认证头；服务端逐次重鉴权 |
| **本轮实测** | CLI 部署 ✅ / 能力清单 ✅ / 退出码 3 ✅ / 官方退出码 4 定义 ✅ / 凭据设计边界 ✅ / **服务端写链路 ❌** / **题库 ❌** / **国网页面实现 ❌** |
| **零实测项** | 国网真实环境、内网、国产算力、模型备案、光明大模型、TB 级批量并发、DSH 运行时子进程、Desktop 安装 —— **全部未测** |
| **证据等级** | 【A】官方下载页 / CLI 安装指南 / CLI 自带 help·guide / 发布元数据 / 本机二进制实跑；【B】无（本轮未引二手报道）；【分析判断】D3 页面与资产映射 |
| **未涉及** | 报价、工期、合同条款、性能承诺、插件人天、法律意见 |
| **质量门禁** | 🟡 **有条件通过**：可作售前口径修订与 D3 开工依据；**不得当作可交付方案、已批准方案或验收结论**，不得表述「已满足国网要求 / 可上线 / 准确率 XX%」 |

---

## 八、请主公示下（下一步最少动作）

| # | 动作 | 为什么 | 前置 |
|:--:|---|---|---|
| **1** | 在本机跑一次 `apemind auth login`（或 `--device`） | 解锁 A1 服务端写链路，拿到真实退出码 4 与可回放轨迹 | 无 |
| 2 | 授权向原厂核 **C10 / C11** 书面口径 | 文档示例与 CLI 版本不一致；DSH 集成状态对客必须说准 | 无 |
| 3 | 确认 G3 剩余 2/3（业务方手写 5 问 + 能判对错的对接人） | F15 仍是唯一人工阻塞，文件已超额到位 | 客户 |
| 4 | 索引收敛后臣自动续跑 8 题 → 补基线报告 §6 | 让 P3/P4/P7 有真实读数可渲染 | F01 |

---

## 附录 · 本轮新增文件与追溯链

| 文件 | 作用 |
|---|---|
| `apemind-cli/apemind.exe` | 官方 CLI v0.7.56（SHA-256 已校验），工作区内，零系统副作用 |
| `apemind_cli_help.txt` / `apemind_capabilities.json` | 276 条命令树 / 263 条机器可读能力清单（含 `request_id`） |
| `apemind_guide_SKILL.md` / `apemind_guide_platform.md` | CLI 自带 Agent 指引与平台操作指引（退出码 4、确认三件套原文） |
| `apemind_install_ps1.txt` / `apemind_install_sh.txt` | 官方安装脚本原文（已审、未执行） |
| `fe-evidence-bridge_取数契约_v1.md` | 前端唯一取数通道契约（本轮交付） |
| `国网Demo_D3_七页面线框.html` | P1–P7 可预览线框 + 静态禁区清单（本轮交付） |
| `a1_verify_after_login.py` | 登录后可一键回放的 A1 验证脚本（本轮交付） |
| `sgcc_poll_stdout.log` | 155 份索引后台真实读数 |

> 追溯链：调研报告「31 项需求」→ V1「五档 / B1–B5」→ V1.1「B6/B7 / 16 项插件化」→ V2「G-A~D / L1~L3」→ V3「O1–O5 / T01–T17 / 剔除私有化」→ V4「DSH 前端七页 / F01–F15」→ **V5「封装层核实 → 能力面重判 → D3 构建修订 → A1 部分通过」**。
