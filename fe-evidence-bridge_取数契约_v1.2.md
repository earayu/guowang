# fe-evidence-bridge 取数契约 v1.2 · C8 实时前端落地

> **定位**：v1.1 的实现补订，不是新方案。新增的只有一条——把 `apemind api` 作为**只读 GET** 纳入 CLI 白名单，用于取四类索引状态；其余 v1.1 约束全部沿用。
> **适用**：2026-11-14 14:20 之后，`sgcc_bridge.py` + `国网Demo_演示控制台_V7.html`（V7.2 / C8 实时面板）。

---

## 1. 为什么要订正

v1.1 §3 把 P1 的取数写成 `knowledge list` / `document list --kb`。真跑发现：

| 命令 | 真跑结果 | 局限 |
|---|---|---|
| `document list --kb <cid> --limit 100 --paginate --json` | exit 0，**155 份、全部 `COMPLETE`** | 只给解析 `status`，**不含** `vector/fulltext/graph_index_status` |
| `apemind api /api/v2/collections/<cid>/documents?page=1&page_size=100 --method GET --json` | exit 0，逐份含四类索引状态与时间戳 | 属 `api` 命令，v1.1 白名单未列 |

`apemind api --help` 明示：「复用 CLI 的认证、workspace header、错误和输出合同；**不能修改 Authorization、Cookie 或 Host**，也不能跨服务地址发送凭据」→ 由桥接调该 CLI 命令，**仍然只经 CLI**，不违反 v1.1「前端不得直连 `/api/v2`」。

---

## 2. v1.2 白名单（构建期固化 `bridge/allowlist.json`）

- 源：`apemind capabilities --json` → `data.command_details[]`（263 条），`request_id = 9d789dc53715913988444f48c73a00d8`，`fetched_at = 2026-11-14T06:20:08Z`，`cli_version = v0.7.56`。
- 允许 **15 条只读命令**：`auth status`、`knowledge list`、`document list`、`document get`、`search`、`grep`、`read`、`outline`、`turn list`、`turn get`、`skill list`、`dataset list`、`function get`、`agent kb list`、`api`。
- **禁止 flag（11 个）**：`--confirm`、`--idempotency-key`、`--header`、`--server`、`--account`、`--input`、`--field`、`--raw-field`、`--force`、`--accept-breaking`、`--secret-file`。
- `api` 附加约束：路径正则 `^/api/v2/collections/colcf0af5d45fd7ef6b/documents(\?...)?$`；`--method` 只允许 `GET`；禁止额外位置参数；`--jq` 不得探测 token / request_id。
- `--server` / `--account` 必须禁：**防止凭据被发到别的服务地址或切换账号**，这是 v1.1「不能跨服务地址发送凭据」的代码化。
- **版本漂移阻断**：`apemind --version` 与 allowlist 的 `cli_version` 不一致 → `/bridge/health` 423，且 `/bridge/invoke`、`/bridge/status` 一律不发问。

---

## 3. 桥接服务端点（`sgcc_bridge.py`，只绑 `127.0.0.1:8765`）

| 端点 | 用途 | 真跑读数（14:27） |
|---|---|---|
| `GET /` | 同源提供控制台 HTML | 200，`text/html` |
| `GET /bridge/health` | CLI 版本 / 登录态 / 版本一致性 | 200：`v0.7.56` 一致、`tgotest@apemind.ai`、`token_cached=true`、`auth_exit=0` |
| `GET /bridge/allowlist` | 白名单摘要给页面展示 | 200：15 条命令、11 个禁 flag |
| `GET /bridge/status` | 经 `apemind api` 分页取 155 份并聚合四类状态 | 200：**文档 155**、解析 `COMPLETE 155`、向量/全文/图谱各 `ACTIVE 155`、2 页、CLI `request_id` 2 个 |
| `POST /bridge/invoke` | 严格校验后执行白名单只读命令，CLI 信封原样回传 | 见 §4 |

日志 `sgcc_bridge_calls.jsonl` 只记 `path / args / exit_code / request_id / ms / at`，**不记凭据、不记正文、不记 token**。

---

## 4. 负向测试（真 HTTP 请求，不是源码断言）

| 试探 | 结果 | 拒绝原因 |
|---|---|---|
| `document upload`（未白名单写命令） | **403** | `command_not_in_allowlist` |
| `document list --confirm` | **403** | `flag_not_allowed:--confirm` |
| `api /api/v2/users --method GET` | **403** | `api_path_not_allowed` |
| `api <cid>/documents --method POST` | **403** | `api_method_must_be_get` |
| `document list --kb <cid> --limit 3 --json`（正向） | **200** | 真实返回 3 份文档 |

---

## 5. 前端约束（不变）

- 控制台 P1 内嵌实时卡片；**12 页签不变**，旧 20 项真浏览器核验零回归。
- 页面只 `fetch` 同源 `/bridge/*`；`file://` 打开时探测 `http://127.0.0.1:8765`，失败显示「桥接未运行 · 静态快照模式」，**不填任何猜测数字**。
- 页面不持有 token、不拼 `--confirm`、不出现通过 / 否决 / 赋分 / 定标控件。
- 静态快照（12:58 / 13:06 历史读数）**保留不涂改**；实时读数与快照并列，标明取数时刻与 CLI `request_id`。

---

## 6. 明确不做的

- 不把 `turn create` / `function invoke` / 任何写命令放进 C8 最小集（写操作仍走 P5 人工确认闸门：`--dry-run` → exit 4 → 人决定 → `--confirm --idempotency-key`）。
- 不在桥接里自己解析 DOCX / 建索引 / 算向量；不自建评测评分。
- 不把 `admin audit list` 当可用（exit 5，举证仍走 Turn 事件轨迹）。
- 不因索引四类全绿倒推「图谱增强已验证」：8 题答案产出在收敛前、A5 对照轮未跑。

---

## 7. 启动与复核

```
python sgcc_bridge.py                 # 只监听 127.0.0.1:8765
浏览器打开 http://127.0.0.1:8765/     # 同源，实时卡片可用
node sgcc_c8_realcheck.mjs            # Edge CDP 真导航 / 真点击 / 网络栈核验
node sgcc_console_realcheck.mjs       # 旧 20 项零回归（file:// 快照模式）
```

> 桥接进程只在本机演示期间运行；演示结束即停。它不是业务系统后端，不对外提供服务。
