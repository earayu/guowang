# C 方案 · 业务界面调用 apemind API：技术设计与实测

> 结论：可行，且已经跑通。核心不是"前端 fetch apemind.ai"，而是**自建一层 BFF（Backend for Frontend）**，密钥与调用都在服务端，前端只跟 BFF 说话。
> 本文所有耗时、限流、返回结构均为 2026-11-14 22:25~22:40 当场实测，不是估算。

---

## 一、拓扑（推荐）

```
客户浏览器（业务界面，你说了算）
        │  只调 BFF，浏览器里没有密钥
        ▼
┌──────────────────────────────────────────┐
│  BFF · sgcc_bff.py（已可跑，330 行）        │
│  ├ 只读 allowlist：8 个库，其余拒绝          │
│  ├ 短缓存 + 并发合并：列表/检索 2~4s → 0.02s │
│  ├ 异步任务队列：抽取 23s 不阻塞请求          │
│  └ 审计 jsonl：谁查了哪家、哪个字段           │
└──────────────────────────────────────────┘
        │  用 api-key 账户跑 CLI（长期有效）
        ▼
┌──────────────────────────────────────────┐
│  apemind CLI（本地二进制，已封装认证/信封）   │
└──────────────────────────────────────────┘
        │
        ▼
   apemind.ai /api/v2 · 8 库 · sgcc-field-extract (v27)
```

**为什么中间必须有一层**：三个理由，缺一不可。
1. 密钥不能进浏览器。api-key 是 30/90/365 天的长期凭证，放进前端等于公开。
2. 官方**没有公开完整的 REST 接口清单**（实测：`/api/v2/collections/{id}/documents` 可通，`/api/v2/functions`、`/api/v2/search` 均被拒）。而 CLI 已经把认证、workspace header、分页、重试、统一信封全封装好了。
3. 性能不允许直连。抽取中位 23 秒、函数限流 4 并发 / 3 rps——前端直连会在第 5 个并发时被拒，且没有任何排队与缓存。

---

## 二、实测读数（这些数字决定了架构，不是风格选择）

| 操作 | 实测耗时 | 说明 |
|---|---|---|
| `knowledge list` | 2.4 ~ 3.6 s | CLI 每次进程启动 + 一次网络往返 |
| `document list`（1 库 4 份） | **1.35 s（冷）→ 0.01 s（热）** | 短缓存生效，命中快两个数量级 |
| `search`（8 命中） | **1.61 ~ 1.97 s** | 带 excerpt + handle 句柄 |
| `read`（按 handle 回读 17 行） | **1.60 ~ 1.87 s** | 原文带行号，可直接引用 |
| `function invoke` 单字段 | **4.0 ~ 8.1 s** | 异步 job，提交仅 0.01 s |
| `function invoke` 中位（历史 207 次） | **23.1 s** | 多字段时更慢（11 字段实测约 40 s） |
| 函数限流 | **4 并发 / 3 rps / burst 6** | 超出服务端直接拒 |

**可复现**：`python bff_smoke.py` 会把这 8 个端点跑一遍，落 `国网Demo_C方案_BFF真跑证据.json`。
本次运行 **9/9 PASS**，其中原文回读取到的证据行是：
`| 投标有效期 | 自投标截止日起60 日历天 | 自投标截止日起90 日 | 不满足 |`
抽取任务 `bid.validity_days` 返回 `verified = true`，函数版本 27，耗时 4.03 s。

**由此推出三条硬性设计**：
- 读类（列表/检索/原文）→ **短缓存 60~300 s + 并发合并**，客户反复点不重复打平台。
- 写重活（抽取/判定）→ **异步 job + 轮询**，前端立即拿到 `job_id`，不阻塞界面。
- 并发 → **单队列串行化**，宁可慢也不撞 4 并发上限。

---

## 三、BFF 接口契约（已实现并逐条验证）

| 方法 | 路径 | 作用 | 实测 |
|---|---|---|---|
| GET | `/api/health` | CLI 登录态、库数、调用统计 | ✅ ok / tgotest@apemind.ai |
| GET | `/api/kbs` | 8 库清单（带 tender/bid 侧别） | ✅ 8 条 |
| GET | `/api/docs?kb=` | 某库文档列表 | ✅ 华中 4 份，全 COMPLETE |
| GET | `/api/search?kb=&q=` | 检索，返回 excerpt + **handle** | ✅ 命中 8，1.97 s |
| GET | `/api/read?handle=` | 按句柄回读原文行 | ✅ 17 行带行号，1.60 s |
| GET | `/api/matrix` | 48 格判定矩阵（快照，可重算） | ✅ 6 家 × 48 格，0.01 s |
| POST | `/api/extract` | 提交抽取任务 → `job_id` | ✅ 0.08 s 受理 |
| GET | `/api/job/{id}` | 查任务状态与结果 | ✅ 8.1 s 完成 |

**真实返回样本（荆州 · 行16 判否的证据链）**：

检索 → `handle = doc54ae2d994464bd00@b5495bf8:86-102`
回读 → 第 88 行：
```
| 投标有效期 | 自投标截止日起60 日历天 | 自投标截止日起90 日 | 不满足 |
```
抽取 → `bid.validity_days = 60日历天`，`verified = true`，出处「我方承诺投标有效期为自投标截止日起60日历天」，函数版本 27，run_id `fnrun64e571be85fb67ac`。

这条链是**同一条实时链路**串起来的：检索找位置 → 回读看原文 → 函数抽字段。客户点开任何一格，走的都是这个。

---

## 四、"实时"要分层，别追求全都实时

这是方案里最需要你确认的取舍。**全实时会让界面等 23 秒，客户会以为系统卡死。**

| 层 | 内容 | 实时度 | 做法 |
|---|---|---|---|
| L1 | 文档列表、检索、原文回读 | **真实时 2 秒内** | 直接调，短缓存 |
| L2 | 字段抽取（单家 1~6 字段） | **准实时 8~25 秒** | 异步 job + 进度条 |
| L3 | 48 格判定矩阵 | **预计算 + 可重算** | 展示快照，点"重算"后台跑 |

演示时的说法（也是实情）：**"检索和原文是即时的；字段抽取是后台任务，因为我们每个值都要回读原文校验，不猜；判定表是算好的，你要重算我可以现在跑，大概一分钟。"**

这比假装全即时更可信——评标系统本来就该有"分析任务"这个概念。

---

## 五、密钥与安全（三步，其中一步需要你授权）

**第 1 步：创建 api-key（需要一次带 scope 的登录）**
当前 OAuth 授权不含 `apikey.write`，实测报 `scope_required`。所以要重新登录一次并带上 scope：

```bash
apemind auth login --scope apikey.write     # 走设备码，你在浏览器里点一次确认
apemind api-key create --description "demo-bff" --secret-file ./bff_key.txt --expires-in-days 90
```
密钥只写进 `--secret-file`（不打印到 stdout、不覆盖已有文件）。**这个文件不能进版本库、不能贴到聊天里。**

**第 2 步：后端用 api-key 账户**
```bash
printf '%s' "$(cat bff_key.txt)" | apemind auth connect --api-key-stdin --account demo
# 之后所有调用加 --account demo，凭证 90 天有效，不受 9 分钟 OAuth token 影响
```

**第 3 步：前端只拿短期口令**
BFF 支持 `BFF_TOKEN` 环境变量，前端带 `X-Demo-Token` 头。演示期间发一个口令给客户，演示结束就换掉——比给 api-key 安全两个数量级。

BFF 本身的只读约束：库走 allowlist（8 个之外一律 400）、禁 `--confirm/--force` 类写操作、审计落 `sgcc_bff_audit.jsonl`。

---

## 六、前端怎么改（W3 只要动 4 处）

目前 W3 的 48 格数据是 `build_w3_v2.py` **内嵌注入**的常量。改实时只需把常量换成 fetch，DOM 渲染逻辑完全不用动。

```js
const BFF = 'http://127.0.0.1:8787';
const H = { 'X-Demo-Token': window.__DEMO_TOKEN || '' };
const j = async (u, o) => {
  const r = await fetch(BFF + u, { headers: H, ...o });
  if (!r.ok) throw new Error((await r.json()).error || r.status);
  return r.json();
};

// ① 矩阵：把内嵌常量换成接口
const MATRIX = await j('/api/matrix');

// ② 点开一格 → 实时取原文（客户最看重这一步）
async function openCell(bidder, rule) {
  const cell = MATRIX.rows.find(r => r.short === bidder).cells[rule];
  const { hits } = await j(`/api/search?kb=${cell.kb}&q=${encodeURIComponent(cell.query)}`);
  const doc = await j(`/api/read?handle=${encodeURIComponent(hits[0].handle)}`);
  renderDrawer(doc);                     // 17 行原文 + 行号，2 秒内
}

// ③ 现场重算抽取（异步 + 进度）
async function reExtract(body) {
  const { job_id } = await j('/api/extract', {
    method: 'POST', headers: { ...H, 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  for (;;) {
    await new Promise(r => setTimeout(r, 2000));
    const jb = await j('/api/job/' + job_id);
    if (jb.state === 'done')   return jb.result;
    if (jb.state === 'failed') throw new Error(jb.error);
    showProgress('正在抽取并回读原文…');   // 8~25 秒，必须有反馈
  }
}

// ④ 断网/后端挂了 → 退回离线快照，演示不中断
try { MATRIX = await j('/api/matrix'); }
catch (e) { MATRIX = window.__MATRIX_FALLBACK; banner('当前为离线快照'); }
```

第 ④ 条很重要：**现场断网时界面不能白屏**，退回今天已经做好的离线快照，客户看不出差别，你也不会冷场。

---

## 七、部署形态（三选一）

| 形态 | 说明 | 适用 |
|---|---|---|
| **同机** | BFF 跑在你笔记本，客户看你屏幕 / 连你热点 | 最快，零运维，**本轮推荐** |
| 内网主机 | BFF 部署在客户内网一台机器，界面走 http://内网IP:8787 | 客户要自己点、要"部署在你们内网" |
| 云主机 + 域名 | 加 Nginx + HTTPS，公网可访问 | 正式交付形态，需备案与运维 |

演示阶段强烈建议**同机**：少一个网络环节就少一个故障点。若客户要自己上手点，用内网主机形态，注意 BFF 现在只绑 `127.0.0.1`，要改成绑内网网卡并加 `BFF_TOKEN`。

---

## 八、工作量分解（按已跑通的部分扣减）

| 项 | 状态 | 剩余 |
|---|---|---|
| BFF 骨架（8 端点、缓存、队列、审计） | ✅ **已完成并实测** | 0 |
| api-key 创建与接入 | 待你做一次授权登录 | 0.5 h |
| W3 改造成 fetch + 抽屉实时化 | 未开始 | 1.5~2 h |
| 前端体验：骨架屏、进度、降级横幅 | 未开始 | 3~4 h |
| 部署（内网主机或云机 + 守护进程） | 未开始 | 2~4 h |
| **判定函数化**（让"重算"是真算而非模型比对） | 未开始 | 4~6 h |

**MVP（能演示"真实时"）= 第一到第四行，约 5~7 小时。**
判定函数化属于"把它从能演变成能验"，可以第二轮做。

---

## 九、风险与边界

| # | 风险 | 影响 | 应对 |
|---|---|---|---|
| 1 | 官方 REST 端点未公开 | 若客户坚持要纯 HTTP SDK，需向平台方索取 OpenAPI | 当前用 CLI 封装，功能等价；对外声称"接口封装层"，不谎称官方 REST |
| 2 | 抽取 23 秒 / 4 并发 | 多客户同时点会排队 | BFF 单队列 + 前端进度 + 文案预设期望 |
| 3 | CLI 每次 2~4 秒启动 | 列表类接口偏慢 | 已加缓存；必要时改常驻进程 |
| 4 | BFF 单点 | 挂了界面就断 | `/api/health` + 前端降级到离线快照 |
| 5 | api-key 泄漏 | 全库可读 | 只存服务端、只在 secret-file、90 天到期、演示后撤销 |
| 6 | 抽取抖动（同版本偶发 NOT_FOUND） | 现场偶发空值 | job 失败可重试；界面显示"未取到"而非猜值 |
| 6b | 同一字段两次 `value_text` 表述不同（实测 `"60"` 与 `"60日历天"`，`value_num` 都是 60） | 界面若直接显示文本会显得不一致 | **界面只显示数值 + 原文引用，不依赖文本措辞**；已在 BFF 保留两者 |
| 7 | 部署机出网访问 apemind.ai | 内网受限就打不通 | 提前实测 `curl https://apemind.ai` |

---

## 十、下一步（需要你点头的三件）

1. **授权一次**：跑 `apemind auth login --scope apikey.write`（设备码，你点一下确认），我接着建 key 并接到 BFF。
2. **定部署形态**：同机 / 内网主机 / 云机 —— 决定我按哪种写启动与守护。
3. **定改造范围**：只做 L1 真实时（检索+原文，2 小时出效果）／加 L2 抽取重算（再 3 小时）／连判定函数一起做（再 4~6 小时）。

已交付可跑件：`sgcc_bff.py`（起服务即用，`python sgcc_bff.py`，默认 `127.0.0.1:8787`）。
