# -*- coding: utf-8 -*-
"""14:33 · C8 / 平台侧最小集 / 核对工作表落地后，同步手册与三份台账（append-only 补记）"""
import io

B = 'c:/Users/linkz/WorkBuddy/PC办公/'


def patch(path, pairs):
    s = io.open(B + path, encoding='utf-8').read()
    for old, new in pairs:
        n = s.count(old)
        assert n == 1, '%s count=%d for %r' % (path, n, old[:80])
        s = s.replace(old, new, 1)
    io.open(B + path, 'w', encoding='utf-8').write(s)
    print('OK patch', path, len(pairs), 'edits')


M = '国网Demo_演示手册_V1.md'
patch(M, [
    ('> **适用**：2026-11-14 14:13 之后的 L1 demo 演示（V7.2 控制台，12 页签 + 四类索引全绿读数）（内部演示者用，**不是对客发放材料**）',
     '> **适用**：2026-11-14 14:33 之后的 L1 demo 演示（V7.2 + **C8 实时取数双模式**，12 页签）（内部演示者用，**不是对客发放材料**）'),
    ('> **性质声明**：控制台是**静态快照演示壳**，不是已实现的业务系统；真实问答在 `apemind.ai` 原生会话。本手册所有读数来自真跑，不预编条款内容、不预填答案。',
     '> **性质声明**：控制台有**两种模式**——直接双击打开是静态快照壳；启动 `sgcc_bridge.py` 并用 `http://127.0.0.1:8765/` 打开时，P1 的 C8 实时卡片会**只经本地桥接调 CLI**取真实读数。两者都不是已实现的业务系统；真实问答仍在 `apemind.ai` 原生会话。所有读数来自真跑，不预编、不预填。'),
    ('## 0. 演示放行判定（2026-11-14 14:13:11 复核）',
     '## 0. 演示放行判定（2026-11-14 14:33 复核 · C8 落地后升级）'),
    ('> 可演示范围 = **15 分钟 L1 技术演示 + 5 分钟业务资产加演**；不放行 = 业务系统已落地 / 验收通过 / 准确率 / 规则自动生效等任何表述。',
     '> 可演示范围 = **15 分钟 L1 技术演示 + 5 分钟业务资产加演 + 3 分钟 C8 实时取数演示**；不放行 = 业务系统已落地 / 验收通过 / 准确率 / 规则自动生效 / 已人工核对等任何表述。'),
    ('| 判定项 | 结论 | 真实依据（14:13 复核） |',
     '| 判定项 | 结论 | 真实依据（14:33 复核） |'),
    ('| 演示入口可开 | ✅ | 控制台 **12 页签**（P0–P7 + 静态禁区 + B1/B2/B3），Edge CDP 真浏览器 **20/20 PASS**，0 JS 异常、0 判定控件 |',
     '| 演示入口可开 | ✅ | 控制台 **12 页签**；旧 20 项零回归 **20/20 PASS**，C8 专项 **15/15 PASS**，0 JS 异常、0 判定控件 |'),
    ('| 业务资产可讲 | ✅ | 术语 68 条 / 规则 46 行 / 省侧 12 条 `REFERENCE_ONLY`；平台 Skill `skil3c96316cf7960d9a3ab5` enabled/v1/28,411 B，回读逐字一致 |',
     '| 业务资产可讲 | ✅ | 术语 68 / 规则 46 / 省侧 12 条 `REFERENCE_ONLY`；平台侧 **Skill** `skil3c96316cf7960d9a3ab5` enabled/v1/28,411 B、**Function** `sgcc-clarification-table` 发布 v1 并真 invoke（231 ms、network off）、**Dataset** `ds674b335d01e44e2694801849daf17b67` 8 条题目骨架 |'),
    ('| 现场可执行 | ✅ | `auth status` 有效、`skill list` exit 0、活查脚本只读可跑、手册逐字稿齐备 |',
     '| 现场可执行 | ✅ | `auth status` 有效；桥接 `/bridge/health` 200（CLI v0.7.56 与 allowlist 版本一致）；逐字稿齐备 |\n'
     '| **C8 实时取数** | ✅ | `sgcc_bridge.py` 只绑 127.0.0.1；P1 实时卡片真渲染 155 / 四类 ACTIVE 155 / 2 个 CLI `request_id`；浏览器网络栈 **无 apemind.ai 直连**；4 类越权试探全部 403 |'),
    ('| **实时问答前端** | ⛔ | C8 未实现，控制台**不发请求**；真问答须切 `apemind.ai` 原生会话 |',
     '| **实时问答 / 业务前端** | ⛔ | C8 只做**只读取数**；控制台不发起提问、不写库，真问答须切 `apemind.ai` 原生会话 |\n'
     '| **逐题人工核对** | ⛔ | 工作表 331 行 / 191 条引用已生成，但**判定列全部留空**，AI 不代判对错 |'),
    ('**现场 3 分钟硬前置**：① 跑 `sgcc_status_check.py` 照数说 ② `apemind auth status`（过期用 `a1_device_login.py` 重登）③ 打开控制台点完 12 个页签。',
     '**现场 4 分钟硬前置**：① 跑 `sgcc_status_check.py` 照数说 ② `apemind auth status` ③ 启动 `python sgcc_bridge.py` 并打开 `http://127.0.0.1:8765/`（不启动则退回快照模式，照常可讲）④ 点完 12 个页签 + 在 P1 点一次「刷新实时读数」。'),
    ('**开场一句话**：「今天是可回放的技术演示：数据、索引、8 题真跑读数、术语与规则资产都在，页面是静态快照壳；规则台账不是规则引擎，判定权始终在人。」',
     '**开场一句话**：「今天是可回放的技术演示：数据、索引、8 题真跑读数、术语与规则资产都在；页面默认静态快照，启动时可只经本地桥接调 CLI 拿实时读数，但**不发提问、不写库**；规则台账不是规则引擎，判定权始终在人。」'),
    ('| **唯一演示入口** | `国网Demo_演示控制台_V7.html` | ✅ 可打开，**12 个页签**（P0–P7 + 禁区 + B1 术语 / B2 规则 / B3 闭环），纯静态零依赖 |',
     '| **唯一演示入口** | `国网Demo_演示控制台_V7.html` | ✅ **12 个页签**；`file://` 快照模式零依赖，或 `http://127.0.0.1:8765/` 实时模式 |'),
    ('| 能力入口（不是前端） | `apemind-cli/apemind.exe` v0.7.56 | ✅ 已登录，263 命令 / 36 scope |',
     '| **C8 本地桥接** | `sgcc_bridge.py` → `http://127.0.0.1:8765/` | ✅ 15 条只读白名单命令；越权全 403；只绑本机 |\n'
     '| 能力入口（不是前端） | `apemind-cli/apemind.exe` v0.7.56 | ✅ 已登录，263 命令 / 36 scope |'),
    ('**当前没有的东西**：接实时数据的可运行业务前端（V6 清单 C8）。`fe-evidence-bridge_取数契约_v1.1.md` 已把命令白名单、scope、退出码、事件流判完成写死，但**代码未落地**。演示时必须说清楚：控制台展示的是已落盘证据与页面布局，**不是实时接口**。',
     '**C8 已落地的是「只读实时取数」**：`fe-evidence-bridge_取数契约_v1.2.md` 固化 15 条白名单，`sgcc_bridge.py` 已实现并真浏览器核验 15/15 PASS。**仍没有的是**：可提问 / 可写 / 可判定的业务前端；控制台不发提问请求、不写库。演示时必须说清：实时卡片展示的是**只读状态读数**，不是实时问答、不是已上线系统。'),
    ('| 6 | 资产页签 | 点 B1 搜「伪命中」、B2 搜「不平衡报价」、B3 看 R1–R6 | 三页真浏览器核验 20/20 PASS；不成功则不讲资产段 |\n| 6 | 话术自检 |',
     '| 6 | 资产页签 | 点 B1 搜「伪命中」、B2 搜「不平衡报价」、B3 看 R1–R6 | 三页真浏览器核验 20/20 PASS；不成功则不讲资产段 |\n'
     '| 7 | **C8 实时（可选）** | `python sgcc_bridge.py` → 浏览器打开 `http://127.0.0.1:8765/` → P1 点「刷新实时读数」 | 不启动桥接就明确说「今天是快照模式」，**不假装有实时数据**；越权试探应 403 |\n'
     '| 8 | 话术自检 |'),
    ('> 检查脚本 `sgcc_status_check.py` 只调 `GET /documents`，不写库、不改配置、不启动索引。',
     '> `sgcc_status_check.py` 只调 `GET /documents`；`sgcc_bridge.py` 只调 CLI 白名单只读命令，二者都不写库、不改配置、不启动索引。'),
    ('**指哪里**：P1 的逐份状态灯表、三段式标识示例（`1525K1 / 4032 / 固化 ID`）。',
     '**C8 实时加演（启动桥接时，约 3 分钟）**：\n'
     '> 「快照之外，我现在点一次『刷新实时读数』。这个按钮不会去连 ApeMind，它只请求本机的 127.0.0.1 桥接，桥接再去调 `apemind` 官方 CLI 的白名单只读命令 —— 认证在 CLI 侧，页面拿不到 token。」\n'
     '> 「看这一行：CLI v0.7.56 与 allowlist 版本一致，账号 tgotest；下面 155 份文档、解析 COMPLETE 155、向量/全文/图谱各 ACTIVE 155，是刚才两条 CLI 调用返回的，带两个 `request_id`；白名单 15 条，禁 flag 里 `--confirm` 永不自动拼。」\n'
     '> 「而且我做过反向验证：让它传 `--confirm`、让它访问越界路径、让它发 POST，桥接全部 403 拒绝，浏览器网络栈里没有任何 apemind.ai 直连。**实时取数 ≠ 实时问答，更 ≠ 自动判定**。」\n\n'
     '**指哪里**：P1 的逐份状态灯表、C8 实时卡片、三段式标识示例（`1525K1 / 4032 / 固化 ID`）。'),
    ('| 门禁 | G3 仍 **1/3**（缺业务方手写 5 问 + 能判对错对接人）；客户书面授权数据外发仍缺 |',
     '| 门禁 | G3 仍 **1/3**（缺业务方手写 5 问 + 能判对错对接人）；客户书面授权数据外发仍缺 |\n'
     '| **C8 桥接（14:27）** | `health` 200（CLI v0.7.56 一致 / tgotest / token_cached）｜`status` 200：155 份、四类各 ACTIVE 155、2 页、2 个 CLI `request_id`｜15 条只读白名单、11 个禁 flag｜4 类越权 403 |\n'
     '| **平台侧最小集** | Function `sgcc-clarification-table` v1（invoke 231 ms、network off、输出 `CANDIDATE`）｜Dataset 8 条题目、`reference_answer` 全 `null`｜Skill enabled/v1/28,411 B、`used_by_bots=0` **未挂 Agent** |\n'
     '| **核对工作表** | 331 行 / **191 条引用行** / 8 题判定列全空；V3 仅 4 摘录、V7 仅 5 摘录、V4 与 sha1 基准冲突单列 |'),
    ('| 图谱能力已验证 | 索引 155 全绿，但答案产出在收敛前、A5 对照轮未跑 → 效果未验证 |',
     '| 图谱能力已验证 | 索引 155 全绿，但答案产出在收敛前、A5 对照轮未跑 → 效果未验证 |\n'
     '| 前端已直连平台 / 业务系统已上线 | 页面只 fetch 127.0.0.1 桥接，桥接只调 CLI；C8 仅只读取数 |\n'
     '| Dataset 已有标准答案 / 8 题可自动评分 | 只有题目与标签，`reference_answer` 全空；业务方核对前不跑 `dataset eval` |\n'
     '| 规则已生效 / Skill 已挂 Agent | Skill 已启用但 `used_by_bots=0`；Function 输出全 `CANDIDATE`、`executable=false` |\n'
     '| 8 题已人工核对 / 引用已回填 | 工作表判定列**全部留空**，AI 不代判；待业务方逐条回读 |'),
    ('| 页面打不开 | 本地文件/预览面板问题 | 用浏览器打开本地 HTML；无外部依赖；也可退回平台原生会话 + 本手册表格照讲 |',
     '| 页面打不开 | 本地文件/预览面板问题 | 用浏览器打开本地 HTML；无外部依赖；也可退回平台原生会话 + 本手册表格照讲 |\n'
     '| 实时卡片显示「桥接未运行」 | `sgcc_bridge.py` 未启动或端口占用 | 明确说「今天是快照模式」；需要实时则启动桥接并改用 `http://127.0.0.1:8765/` |\n'
     '| 桥接提示版本不一致 | CLI 版本与 `bridge/allowlist.json` 漂移 | 已按契约阻断发问；重新生成 allowlist 或对齐 CLI 版本，不绕过阻断 |\n'
     '| 越权请求返回 403 | 白名单按设计拒绝 | 这是**预期行为**，不是故障；现场可主动演示 4 类拒绝 |'),
    ('**给客户留三件**：① 演示控制台 HTML（可自行打开）② `国网真实样本_L1实测基线报告.md`（含 §6 逐题读数与失败轮次）③ `fe-evidence-bridge_取数契约_v1.1.md`（后续前端如何合规取数）。',
     '**给客户留三件**：① 演示控制台 HTML（可自行打开）② `国网真实样本_L1实测基线报告.md`（含 §6 逐题读数与失败轮次）③ `fe-evidence-bridge_取数契约_v1.2.md`（C8 实时取数的白名单与拒绝证据）。'),
    ('- P0-2 C8 前端落地：把控制台从静态快照升级为只经 `fe-evidence-bridge` 调 CLI 的可运行页面\n'
     '- P1 部署 Skill（合规红线指令）/ Function（待澄清事项表）/ Dataset（8 题评测集）最小集',
     '- P0-2 ✅ **C8 只读实时取数已落地**（桥接 + P1 实时卡片，15/15 PASS）；仍缺可提问/可写的业务前端\n'
     '- P1 ✅ **平台侧最小集已部署**：Skill 状态核实（未挂 Agent）/ Function v1 真 invoke / Dataset 8 条**无参考答案**骨架\n'
     '- P0-3 ✅ **逐题核对工作表已生成**（判定列留空）；转为业务方逐条回读与引用回填'),
    ('| `fe-evidence-bridge_取数契约_v1.1.md` | 前端唯一取数通道契约 |',
     '| `fe-evidence-bridge_取数契约_v1.2.md` | **C8 现行契约**：15 条只读白名单、`api` 只读 GET、4 类拒绝证据 |\n'
     '| `sgcc_bridge.py` / `bridge/allowlist.json` | 本地桥接服务与构建期固化白名单 |\n'
     '| `sgcc_c8_realcheck.mjs` / `sgcc_c8_realcheck.json` | C8 真浏览器 15/15 PASS 与截图 |\n'
     '| `sgcc_assets_deploy.py` / `sgcc_assets_deploy_result.json` | Function / Dataset 真部署与回读 |\n'
     '| `国网Demo_逐题人工核对与引用回填工作表_V1.md` | 8 题 / 191 条引用 / 判定列留空 |\n'
     '| `sgcc_fn_clarification/` | 待澄清事项表 Function 源码（纯结构化、全 CANDIDATE） |'),
])

NOTE = '''
---

## 附记 · 14:33 C8 / 平台侧最小集 / 核对工作表落地（追加不改历史读数）

- **C8 只读实时取数已落地**：`sgcc_bridge.py` 只绑 `127.0.0.1:8765`；`bridge/allowlist.json` 从 `capabilities` 固化 **15 条只读命令 / 11 个禁 flag**（`request_id 9d789dc53715913988444f48c73a00d8`）。控制台 **12 页签不变**，P1 内嵌实时卡片，`file://` 未启动时显示快照模式、不填假数。契约升级 `fe-evidence-bridge_取数契约_v1.2.md`（新增 `apemind api` 只读 GET 白名单，理由与边界留痕）。
- **真跑读数**：`health` 200（CLI v0.7.56 与 allowlist 一致 / `tgotest@apemind.ai` / token 只在 CLI 侧）；`status` 200（**文档 155、解析 COMPLETE 155、向量/全文/图谱各 ACTIVE 155**、2 页、2 个 CLI `request_id`）。负向 4 类（未白名单写命令 / `--confirm` / api 越界 / api POST）**全部 403**，正向只读 200。
- **真浏览器核验**：C8 专项 **15/15 PASS**（HTTP 同源真导航、实时读数真渲染、网络栈无 apemind.ai 直连、越权试探 403、0 JS 异常）；旧 20 项零回归 **20/20 PASS**。首轮 14 项中 2 条 FAIL 已核实根因：favicon 404 是服务端真实缺陷（已修为 204）、403 是核验脚本自发的预期拒绝（单列）；「判定按钮」FAIL 是 C8 断言过宽、误把静态禁区页签说明文字当控件（断言对齐旧核验语义，未改页面迎合）。三份报告留痕。
- **平台侧最小集真部署**：Function `sgcc-clarification-table` **发布 v1 并真 invoke**（231 ms、`network.status=off`、输出 `CANDIDATE` / `executable=false`）；Dataset `ds674b335d01e44e2694801849daf17b67` **8 条题目骨架、`reference_answer` 全 `null`**；Skill 核实 enabled/v1/28,411 B / **`used_by_bots=0` 未挂 Agent**（挂载会改 Agent 行为，须单独做同 8 题 A/B 零回归）。
- **逐题人工核对与引用回填**：生成 331 行工作表 + 机器可读 JSON，**191 条引用行**，8 题的判定/依据页码/回填引用/核对人/日期**全部留空**；AI 不代判对错、不写标准答案。V3 仅 4 摘录、V7 仅 5 摘录、V4 与本地 sha1 基准冲突、V6 故意失败题判据均单列。
- **禁语新增**：「前端已直连平台 / 业务系统已上线」「Dataset 已有标准答案 / 8 题可自动评分」「规则已生效 / Skill 已挂 Agent」「8 题已人工核对 / 引用已回填」。
- **放行判定升级**：有条件 GO 范围 = 15 分钟 L1 技术演示 + 5 分钟业务资产加演 + **3 分钟 C8 实时取数演示**；仍 NO-GO：实时问答/写操作业务前端、规则自动生效、图谱增强效果、答案正确性（G3 仍 1/3）、生产上线。
'''

for f in ['国网Demo_任务完成情况汇报与口径收束_V7.md',
          '国网Demo_业务术语_专家评审规则_业务闭环_V8.md',
          '国网Demo_基于目标的开工任务清单_V6_已开工.md']:
    s = io.open(B + f, encoding='utf-8').read()
    io.open(B + f, 'w', encoding='utf-8').write(s.rstrip() + '\n' + NOTE)
    print('OK append', f)

log = '.workbuddy/memory/2026-11-14.md'
s = io.open(B + log, encoding='utf-8').read()
s += ('\n## 14:33 C8 三项落地（同日追加）\n'
      '- 修复上一回合遗留坏装配脚本（新增 once 放错阶段导致重建失败），控制台可从备份源重复重建；14:13 四类 155 全绿真值已同步进控制台与手册，12:58 历史快照保留不涂改。\n'
      '- **C8**：`sgcc_bridge.py` 本地桥接（127.0.0.1:8765）+ `bridge/allowlist.json`（capabilities 固化 15 只读命令）+ P1 内嵌实时卡片，`apemind api` 只读 GET 纳入契约 v1.2；真跑 health/status 200、四类 155、4 类越权 403；Edge CDP **15/15 PASS**、旧 20/20 零回归、浏览器网络栈无 apemind.ai 直连。\n'
      '- **平台侧最小集**：Function `sgcc-clarification-table` 发布 v1 并真 invoke（231ms、network off、CANDIDATE）；Dataset `ds674b335d01e44e2694801849daf17b67` 8 条题目、reference_answer 全 null；Skill 核实 enabled 但未挂 Agent（used_by_bots=0）。\n'
      '- **逐题核对工作表**：331 行 / 191 条引用行 / 8 题判定列全空；AI 不代判、不写标准答案，G3 仍 1/3。\n'
      '- 首轮 C8 核验 2 条 FAIL 均已查实根因并留痕：favicon 404 服务端缺陷已修、预期 403 单列、判定按钮断言过宽对齐旧语义（未改页面造绿）。\n')
io.open(B + log, 'w', encoding='utf-8').write(s)
print('OK append', log)
