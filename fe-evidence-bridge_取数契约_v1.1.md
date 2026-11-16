# `fe-evidence-bridge` 取数契约 v1.1（D3 前端唯一取数通道）

> 修订：2026-11-14 12:40　｜　**取代 v1，v1 留档供追溯**
> 依据：`apemind.exe` **v0.7.56** 本机实跑 + `capabilities --json`（263 条）+ `guide platform` + **本轮登录后 A1 全链路实测**
> 适用：V5 §4 的 L2 业务前端层 / V6 清单 C 组 P1–P7
> 性质：**可开工契约**，不是已实现代码、不是验收结论

## v1.1 修订点（全部来自本轮真跑，非推断）

| 编号 | v1 写法 | v1.1 更正 | 证据 |
|---|---|---|---|
| **R1** | 退出码 4「未登录，未触发」 | **已实测 PASS**：`dry-run exit 0` → 无 `--confirm` **exit 4 `confirmation_required`** → `--confirm --idempotency-key` **exit 6 `not_found`**，每步带 `request_id` | `a1_results.json` |
| **R2** | CLI 未登录、设备码 100s 超时 | **已登录** `tgotest@apemind.ai`（自助批准 200 / exit 0），官方页明示**不创建 API Key** | `a1_device_login_result.json` |
| **R3** | `dataset.*` 未提 scope | 默认授权不含 `dataset.read` → **exit 3 `scope_required`**；带 13 个 scope 重登后 exit 0 | `d3_capability_probe.json` |
| **K1** | 隐含 `function list` | **无此子命令**。真实为 `apply/delete/describe/diff/explain/get/history/init/invoke/logs/pull/rollback/runs/trace/unpublish` | CLI `function list` exit 2 `usage` |
| **K2** | 隐含 `mcp list` | **无此子命令**。真实为 `mcp resources` / `mcp tools`（`tools list` 需 `knowledge.read`） | CLI `mcp list` exit 2 |
| **K4** | P7 写 `audit list` | **`admin audit list` exit 5 `permission_denied`**（scope 已给、账户非管理员）→ 举证改走 **`turn` / `chat` 事件轨迹** | 本轮实测 |
| **R4** | 完成判据只看聚合接口 | **新增事件流判完成**（见 §12）：聚合 `turns/{tid}` 可滞后到 `parts=0` 而答案已生成 | `sgcc_v1_events_parsed.json` |

---

## 1. 定位与硬边界（不变）

**bridge 是前端唯一能碰到 ApeMind 的地方。** 只做三件事：拼白名单命令 → 调 `apemind` CLI → 把 CLI 结构化信封原样交给页面渲染。

| 允许 | 禁止 |
|---|---|
| 调 `apemind` CLI 白名单命令 | ❌ 前端直连 `/api/v2`（fetch / XHR / SDK） |
| 传 `--workspace`、`--kb`、`--json`、`--jq` | ❌ 自己解析 DOCX / .doc、自己建索引、自己算向量 |
| 读 CLI 输出信封（`request_id` 等） | ❌ 读/写凭据、把 token 放进页面状态 / 日志 / URL |
| 把 CLI 的 `next:` / `hint:` 转成页面按钮 | ❌ 覆盖 `Authorization` / `Cookie` / `Host` |
| 收集人工动作交给 `turn consent` | ❌ 前端自行判定「通过 / 否决 / 赋分 / 定标」 |

> 官方依据：`apemind api --help`「复用 CLI 的认证、workspace header、错误和输出合同；不能修改 Authorization、Cookie 或 Host」；capabilities「**the server rechecks every request**」。

---

## 2. 白名单：从 `capabilities.json` 生成（K1/K2 后按真实子命令）

```
源：apemind capabilities --json → data.command_details[]（263 条）
键：command_details[i].path             例 "document list" / "mcp tools call"
值：flags[]、required_oauth_scopes[]    例 ["dataset.read"]、["agent.write"]
```

规则：① 构建期固化 `bridge/allowlist.json`（含 `version` / `fetched_at` / `request_id`）｜② 未知 path 一律拒绝并记 bridge 日志｜③ 带 `confirm` flag 的命令前端**不得自动拼 `--confirm`**｜④ `apemind --version` 与 allowlist 版本不一致时**阻断发问**（防 C10 类版本错配）。

**实测读数**：263 命令 / 36 OAuth scope / **115** 条 `--dry-run` / **29** 条 `--confirm` / **5** 条 `--idempotency-key`。
**D3 关键命令 scope**：`dataset list→dataset.read`｜`function apply→function.read+function.write`｜`skill upload/import、task create、agent update→agent.write`｜`turn consent→turn.write`｜`mcp tools list→knowledge.read`｜`admin audit list→admin.audit.read`（**即使有 scope 仍可能 exit 5**）。

---

## 3. P1–P7 命令映射（v1.1 订正）

| 页面 | 动作 | 白名单命令（v0.7.56 真实子命令） | 模式 |
|---|---|---|:--:|
| P1 批次·标包导航台 | 列知识库 / 文档与索引状态 | `knowledge list`、`document list --kb` | 只读 |
| P2 体检发起台 | 空库拦截（两阶段上传坑） | `document list --kb` 校验 `confirm` 已完成 | 只读 |
| P2 | 发起体检 | `turn create --chat-id … --message …` / `task …` | 写（人工发起） |
| P3 三栏体检页 | 检索 / 精确词 / 原文回读 | `search QUERY --kb`、`grep PATTERN --kb`、`read HANDLE…`、`outline DOC --grep` | 只读 |
| P4 双版对照 | 结构化差异 | `function invoke <slug> --field …` + `read` 双份原文 | 混合 |
| P5 确认抽屉 | 预演 → 人决定 → 提交 | `--dry-run` → **exit 4** → `--confirm --idempotency-key`；工具同意走 `turn consent … --decision approved\|denied` | 写 |
| P6 待澄清事项表 | 生成 / 导出 | `function invoke`（表生成） | 混合 |
| **P7 轨迹与评测** | 轨迹 / 回归 | **`turn list --chat-id`、`turn get`、`dataset eval get/compare`**；**不用 `admin audit list`** | 只读 |

> **P4/P6 的 Function 是平台侧可部署资产**（`function init/diff/apply/invoke/rollback`），不是前端计算。
> **P7 的审计举证**：账户非管理员，`admin audit list` exit 5；改用 Turn 事件轨迹（含 `request_id`），并在页面标注「轨迹举证 ≠ 平台管理员审计日志」。

---

## 4. 输出合同（CLI 原生信封，前端不得改写）

```json
{"type":"result | error","server":"https://apemind.ai","workspace":"orge… | null",
 "fetched_at":"2026-11-14T04:33:56Z","request_id":"fa8048e8d08265bcfd8b4b65306c2e82",
 "data":{…},"error":{"code":"confirmation_required","message":"…"},"exit_code":4}
```

`request_id` 从 P3 引用卡 → P5 人工动作 → P7 轨迹时间线**必须可关联**；前端不得自造。写操作失败时顶层 `idempotency_key` 重试须保持账户/服务/工作空间/请求内容四者不变。

---

## 5. 退出码表（**本轮全部真跑**）

| 码 | 含义 | 前端必须怎么显示 | 本轮实测 |
|:--:|---|---|:--:|
| `0` | 成功（**含空结果**） | 正常渲染；空结果不写成「查到了」 | ✅ `--help` / `doctor` / `capabilities` / `guide` / **S4 dry-run** |
| `2` | 参数错误 | 显示 CLI 给的正确用法，不重试 | ✅ `function list` / `mcp list` usage |
| `3` | 需要登录 / 授权 | 显示「请登录或 `auth login --scope …`」，**禁止自动重试** | ✅ 未登录 10 探针 + `dataset list` scope_required |
| **`4`** | **需要确认或冲突** | **P5 抽屉必须显式出现**，展示 dry-run 差异与幂等键，不得被前端吞掉 | ✅ **S5 `confirmation_required`** |
| `5` | 无权限 | 显示缺失 scope 与 `auth login --scope …`；**仍失败则标「账户权限不足」** | ✅ `admin audit list` permission_denied |
| `6` | 不存在 / 句柄过期 | 引用卡标「原文已变更，请重新检索」 | ✅ S6 `not_found` |
| `7` | 限流 | 退避重试，不把限流当「无证据」 | — |
| `8` | 服务故障 | 显示故障，不落到结论 | — |
| `9` | 部分失败 | 逐项标注失败项，不得当完整结果 | — |

> `guide`（检索指引）只列 0/2/3/5/6/7/8/9 不含 4，因检索命令不触发确认；`guide platform` 第 128 行明确 4 —— 两处不冲突（C12 已解释）。

---

## 6. 确认三件套（O5 的技术落点，**已实测**）

```
1) 前端发起 → bridge 拼 <写命令> --dry-run
2) CLI 返回 changes / grants，不发请求              ← S4 exit 0，body 里 confirmed=false
3) 需确认却未带 --confirm → exit 4 / confirmation_required   ← S5
4) P5 抽屉展示差异 + 幂等键 + request_id，等人点「确认 / 修改 / 驳回」
5) 人确认 → --confirm --idempotency-key <KEY> → 提交        ← S6 闸门放行（占位 ID 得 exit 6）
6) 工具级同意另走 turn consent --decision approved|denied    ← 命令契约已核，真 Turn 未验
```

**前端静态禁区**（可静态扫描）：无「一键通过 / 自动否决 / 赋分 / 定标」控件｜无 `fetch('/api/v2…')` / SDK｜无 `Authorization` / `Cookie` / `token` 出现在页面状态、localStorage、日志、URL｜无自动拼 `--confirm` 的代码路径。

---

## 7. 凭据边界（Issue #40 的封装层答案）

| 场景 | 官方做法 | 前端 |
|---|---|---|
| 人机登录 | `apemind auth login` / `--device`（本轮自助批准，**不创建 API Key**） | 不参与 |
| 无浏览器脚本 | `auth connect --api-key-stdin` | 不参与 |
| 创建密钥 | `api-key create --secret-file FILE`（只写新文件、不进 stdout、不进 Agent 日志） | 不参与 |
| 客户端配置 | `apemind config`「只保存客户端行为，不保存认证材料」 | 不参与 |

> Issue #40（DSH 子进程剥离 `KEY|PASSWORD|SECRET|TOKEN`）在封装层由「凭据不进环境变量 / 命令行 / stdout」规避。**设计已证实**；本轮登录后未起子进程，**运行时仍未实测**。

---

## 8. 降级与诚实呈现（防假绿）

| 情形 | 前端必须显示 |
|---|---|
| 图谱未全绿（12:36：**81 ACTIVE / 32 RUNNING / 42 PENDING**） | 「基于向量 + 全文检索；图谱未全量可用」，不得标「三类索引全绿」 |
| `search` 仅 medium/weak 或 `no strong hits` | 「证据不足」，不得拼凑 |
| `grep` 出现 `scanned the first …` | 「仅扫描前 20 个知识库」 |
| 库外题（V6 打分表 / 技术得分） | P7 独立「**证据不足**」卡；正文含「技术得分」3 次属**术语伪命中**须标记 |
| `.doc` 22 份 / `.sign` 18 份未入库或不可读 | P1 独立「未入库 / 无法解析」状态 |
| 同名文件（18 标包 14 份同名公告） | 引用必须带 `批次 + 标包 + 固化 ID` |
| **聚合接口滞后**（§12） | 以事件流 `finish` 判完成；页面不因聚合 RUNNING 显示「无答案」 |
| **工具输出错误**（V1 实测 1 次） | 逐项标注「该次工具调用失败」，不得当完整证据链 |

---

## 9. 验收指标

| 指标 | 目标 | 本轮 |
|---|:--:|:--:|
| 单一取数符合率 / 白名单符合率 / `request_id` 关联率 / 候选标记率 | 100% | 待前端实现 |
| 退出码 4 可见率 | 100% | ✅ **CLI 侧已实测触发** |
| 静态禁区 | 0 个自动判定类控件 | 待前端实现 |
| 同名引用可追溯率 | 10/10 | V1 回答已主动区分标包并声明「未做全文逐行比对，不能确认 8 份 100% 相同」 |

---

## 10. 部署门禁（v1.1 新增，开工前必做）

1. `apemind auth status --json` → `logged_in=true`；token 约 9 分钟过期、有 refresh，**每次部署前复验**。
2. scope 不足 → `python a1_device_login.py <scope...>` 自助重登（设备码批准 200，无需人工点浏览器）。本轮已申请 13 个：`dataset.read/write/create/export/publish`、`function.read/write/invoke`、`agent.write`、`turn.write`、`audit.read`、`admin.audit.read`、`organization.read`。
3. 复验：`dataset list` ✅ / `mcp tools list` ✅ / `admin audit list` ❌ exit 5（**已知边界，非部署失败**）。
4. 版本漂移：`apemind --version` 必须 v0.7.56，否则重生成 allowlist。

---

## 11. 事件流完成判据（v1.1 新增，R4）

**实测事实**：V1 题事件流已 `finish`×2、`text-end`×8、产出 **5,670 字符答案 / 22 次工具调用 / 20 条原文摘录**，而聚合 `turns/{tid}` 仍 `status=RUNNING, parts=[]`。

因此前端/跑题链路：
- **完成判据**：SSE `/turns/{tid}/events` 出现 `finish` 且 `text-end` → 判 COMPLETED；聚合接口读数**并列保留**，不覆盖、不当作报错。
- **证据主源**：事件流的 `text-delta` 拼答案、`tool-input-available/output-available` 拼轨迹、`data-source-excerpt` 拼原文引用。
- **失败项保留**：`tool-output-error`（V1 有 1 次）必须逐项标注。
- 可回放实现：`sgcc_events.py` / `sgcc_run_qa_v2.py`。

---

## 12. 未验证 / 待办

- ❌ `turn consent` 在真实 Turn 上的行为（命令契约已核）。
- ❌ Skill / Function 的**部署与 invoke**（只核到命令契约与 scope）。
- ❌ 任何前端实现（线框已出，代码未落）。
- 🔄 V2–V8 题库后台运行中；V1 已完成并落盘。
- 🔄 图谱索引长尾未收敛。

> **门禁**：🟡 有条件通过。契约可作为开工依据，**不得当作已实现、已验收或可上线**。
