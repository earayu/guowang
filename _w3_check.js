
const EVID = {
  e1:{title:"资格预审版 · 附件2",meta:{"文件":"S1K1_4032视频在线监测装置__…（1525K1）-资格预审.docx","大小":"9,706,361 字节","解析块":"160","位置":"附件2 字第232–253 行","证据强度":"原文直引"},quote:"序号 | 分标名称 | 资格条件要求 | 备注\n1 | 10kV 变压器（非晶合金） | 提供型式试验报告（包含该标段各容量规格），能效满足 GB20052-2020 国标2级及以上 | 通过相应联合资格预审项目\n2 | 10kV 变压器（油浸） | 提供全性能试验检测报告和型式试验报告，符合 GB20052-2020 二级能效 | …\n3 | 10kV 变压器（干式） | 应[提供]型式试验报告（包含该标段各容量规格），能效 GB20052-2020 2级及以上 | …（「提供」二字原文缺失）\n…（其余 23 行均只要求「通过相应联合资格预审项目」，未单独提型式试验）"},
  e2:{title:"资格后审版 · 附件2",meta:{"文件":"S1K1_4032视频在线监测装置__…（1525K1）-资格后审.docx","大小":"9,763,974 字节","解析块":"194","位置":"附件2 字第249–290 行","证据强度":"原文直引"},quote:"分标编号 | 物资名称 | 合同业绩 | 生产设备 | 型式试验报告…\n1525K1-1001002-1004/1005/1006（20kV 变压器）| … | … | … | 1、本体型式试验报告（报告内含能效等级）；2、本体型式试验报告+同型号变压器能效等级报告。注：第1项和第2项须满足其中一项\n1525K1-1102002-4032 / -4038 | 视频/图像在线监测装置 | … | … | 型式试验报告 或 检测报告\n1525K1-1401005-4036（铁塔）/ -1401007-4034（水泥制品）| … | … | … | /（无要求）"},
  e3:{title:"招标公告 3.5(12)",meta:{"文件":"S1K1_4032视频在线监测装置__1525K1招标公告.docx","位置":"三、投标人资格要求 3.5(12) · 解析行 87","证据强度":"原文直引"},quote:"有国家标准或行业标准的，应取得型式试验报告；无相关标准的，应按国家电网公司企业标准出具检验检测报告。境内检测机构须具备 CMA 与 CNAS 资质。\n\n（两版此条逐字相同）"},
  g1:{title:"资格预审",meta:{"证据来源":"1525K1 采购文件 附件2 · 招标公告 3.6","证据强度":"原文直引"},quote:"本项目资格预审版以「通过某年某次联合资格预审项目【含补充预审】」作为资格条件，共引用 15 项以上外部预审项目。"},
  g2:{title:"资格后审",meta:{"证据来源":"1525K1 采购文件 附件2 · 资格后审版","证据强度":"原文直引"},quote:"资格后审版改为「投标时按分标提交资格审查资料评审」，并按分标编号逐行列明业绩、设备、报告要求。"},
  g3:{title:"专用资质业绩要求",meta:{"证据来源":"招标公告 附件2.1 / 附件2.2","证据强度":"原文直引"},quote:"招标公告同时收录「附件2.1：«资格后审»专用资质业绩要求」与「附件2.2：«资格预审»专用资质业绩要求」，正文 3.6 未指明适用哪一个。"},
  g4:{title:"否决投标",meta:{"证据来源":"第三章 评标办法前附表之二 · 否决情形表","证据强度":"原文直引"},quote:"共 46 条：资格评审 25 条、响应性评审 15 条、形式评审 5 条、其他事项 1 条。第 46 行按资格预审 / 后审版本不同。"},
  g5:{title:"初步评审",meta:{"证据来源":"第三章 评标办法","证据强度":"原文直引"},quote:"初步评审标准含形式评审、资格评审、响应性评审三段，否决情形表即挂在这一节之下。"},
  g6:{title:"待澄清事项",meta:{"证据来源":"系统输出 · 由差异清单结构化生成","证据强度":"条款推定"},quote:"指文件之间不一致、需招标人发澄清才能定论的事项。系统产出 9 项，全部标注「候选待核 / 需人工判定」，不构成违规或有效性的终局结论。"},
  g7:{title:"排斥限制竞争",meta:{"证据来源":"招标投标法及实施条例（原文不在知识库内）","证据强度":"条款推定"},quote:"资格或技术条件设置不合理导致排除潜在投标人。系统仅列候选条款并标注「需人工判定是否违规」，不下终局结论。"},
  g8:{title:"联合资格预审",meta:{"证据来源":"1525K1 采购文件 附件2","证据强度":"原文直引"},quote:"由上级或联合组织统一开展的资格预审。预审版引用 2024 年配网 10kV 变压器、金具及交流避雷器、箱式变电站、高压熔断器、开关柜、环网柜等 15 项以上预审项目。"},
  g9:{title:"标包 / 分标",meta:{"证据来源":"货物清单 · 招标公告","证据强度":"原文直引"},quote:"本项目 18 个标包。同批次多个标包含同名文件（如各标包均有预审/后审两版采购文件），须按文件名前缀区分，不得合并。"},
  g10:{title:"型式试验报告",meta:{"证据来源":"附件2 · 招标公告 3.5(12)","证据强度":"原文直引"},quote:"证明产品型号符合标准的试验文件。后审版对 30 余个分标逐行要求，其中 4032/4038 为「型式试验报告或检测报告」二选一，4033 只要求「整机检测报告」。"}
};

const DIFF = [
 {d:"通用要求",pre:"第一章招标公告 3.5(12)：有国标/行业标准的须取得型式试验报告，无标准的按国网企标出检验检测报告；境内机构须 CMA+CNAS（解析行87）",post:"同条 3.5(12)，<em>逐字相同</em>（解析行87）",ev:"e3"},
 {d:"附件2 逐分标",pre:"<em>4 列表</em>（序号1–26）：<em>仅 10kV 变压器三行</em>要求型式试验，且绑定 GB20052-2020 二级能效；其余 23 行（避雷器、箱变、断路器、熔断器、开关柜、环网柜、分支箱、配电箱、电缆、杆塔等）均只要求「通过相应联合资格预审项目」（解析行232–253）",post:"<em>8 列表</em>（按分标编号）：设专列「所投产品须取得的产品型式试验报告或检测报告或鉴定报告」，<em>逐行要求，覆盖 30 余个分标</em>；20kV 变压器三行改为「同型号能效等级报告」可替代，未再写明 GB20052-2020（解析行249–290）",ev:"e1"},
 {d:"4032 / 4038",pre:"附件2 表中<em>无该两个分标的行</em>（全文「视频在线监测 / 图像在线监测」0 命中专用条件）",post:"「型式试验报告 <em>或</em> 检测报告」<em>二选一</em>，另要求制造商、合同业绩 500 万元",ev:"e2"},
 {d:"差异性质",pre:"—",post:"① 型式试验从 3 行扩到 30 余分标；② 能效标准写法由「GB20052-2020 二级」改为「同型号能效等级报告」；③ 在线监测类由「无要求」变为「型式或检测二选一」",ev:"e2"}
];

const DIFF2 = [
 {d:"通用要求",pre:"招标公告 3.5(12)「检验检测报告」（无国标时）；附件2 后编号说明第6条「报告检测项目必须覆盖所投主要产品」、第8条「技术规范书中所列检测报告、认证证书等资质业绩要求对投标人无约束」（解析行87、305、309）",post:"同三条，<em>逐字相同</em>（解析行87、344 区间）",ev:"e3"},
 {d:"附件2 逐分标",pre:"<em>仅序号2（10kV 油浸变压器）</em>要求「全性能试验检测报告和型式试验报告」；其余行<em>无逐分标检测报告要求</em>",post:"<em>逐行要求</em>：表前端子箱「应提供塑壳断路器的检测报告」；4033「提供<em>整机检测报告</em>」；铁塔防坠落导轨装置「提供检测报告」；BWFRP 电缆保护管「有效的检验检测报告」；4032/4038 为「型式或检测」（解析行253–281）",ev:"e2"},
 {d:"口径差异",pre:"检测报告仅出现在通用条与 10kV 油浸变压器行",post:"<em>4033 只要求整机检测报告（不要求型式试验）</em>，与 4032/4038 的「型式或检测」二选一口径不同 —— 同一类产品三种写法",ev:"e2"},
 {d:"影响",pre:"—",post:"投标人若按 4032 的口径准备 4033 的资料，可能被判为报告类型不符。此类差异须澄清，不能由系统推断",ev:"e2"}
];

const DIFF3 = [
 {d:"通用合同业绩",pre:"附件2 后编号「2合同业绩」：提供 <em>2023-01-21 至 2026-01-20</em> 同类产品销售合同及发票，业绩时间以合同签订时间为准、金额或数量以发票为准；含代理商/集货商、母子公司、并购继承规则（解析行275）",post:"同条，<em>逐字相同</em>（解析行310）",ev:"e1"},
 {d:"附件2 逐分标业绩",pre:"4 列表 26 行<em>全部为「通过某年某次联合资格预审项目」型条件</em>（如序号6 一二次融合成套柱上断路器：2025年配网第一次补充联合资格预审合格）；<em>表内无逐分标的数量/金额量化业绩</em>，也<em>没有 4032/4033/4038 三行</em>（解析行232–253）",post:"8 列表设「合同业绩要求」专列，按分标逐行量化；三个在线监测分标首次出现（4032/4038 要求<em>合同业绩 500 万元</em>；4033 要求「有所投产品合同业绩」）",ev:"e2"},
 {d:"差异性质",pre:"业绩以「预审合格」替代，无法看到具体量化门槛",post:"业绩改为<em>可量化、可核对的金额与时间窗</em>，投标人自行判断是否满足",ev:"e1"},
 {d:"待澄清",pre:"—",post:"预审版引用的 15 项以上外部预审项目，其预审结果与合格名单<em>均不在知识库内</em>，无法核验哪些投标人实际已通过",ev:"g8"}
];

const DIFF4 = [
 {d:"型号相关通用条",pre:"型号/代理商条款（解析行对应位置）",post:"<em>逐字相同</em>",ev:"e3"},
 {d:"附件2 唯一差异",pre:"无「同型号」联动要求",post:"20kV 变压器行新增「本体型式试验报告 + <em>同型号</em>变压器能效等级报告」二选一要求",ev:"e2"},
 {d:"代理商条款",pre:"一个制造商对同一品牌同一型号货物委托两个及以上代理商参加同一标包投标的，视为否决情形（GW-HB-FJ-032）",post:"同条，<em>逐字相同</em>",ev:"g4"},
 {d:"影响",pre:"—",post:"「同型号」是后审版新增的型号维度约束，投标人须确认所投型号的能效等级报告是否可取得",ev:"e2"}
];

const RULES=[
["GW-HB-FJ-001","形式评审","投标文件未按招标文件规定的格式填写，内容不全或者关键字迹模糊无法辨认的。未按招标文件要求在招标人招投标交易平台信息系统制作并上传凭证单，或因投标人删除了系统文件导致凭证单索引的核实信息无法查看的。"],
["GW-HB-FJ-002","形式评审","投标人递交两份或多份内容不同的投标文件，或在一份投标文件中对同一招标内容报有两个或多个报价，按招标文件规定提交备选投标方案的除外。"],
["GW-HB-FJ-003","形式评审","对格式文件进行实质性修改或未按格式进行签署的，如由委托代理人签字的，未附有效的法定代表人（单位负责人）授权委托书的。"],
["GW-HB-FJ-004","形式评审","上传招标人招投标交易平台信息系统的电子投标文件无电子签章，或者电子签章无效的，或者电子签章名称与投标人不是同一人的。"],
["GW-HB-FJ-005","形式评审","投标文件主要技术参数或产品型式不满足招标文件要求的；一般技术参数超出允许偏差最大范围的；规定接口要求的产品响应与招标文件不符的。"],
["GW-HB-FJ-006","响应性评审","提交投标文件截止时间后主动撤销投标文件或对投标文件提出实质性修改的。"],
["GW-HB-FJ-007","响应性评审","不按评标委员会要求对投标文件进行澄清、说明或补正的。"],
["GW-HB-FJ-008","响应性评审","投标文件所承诺的交货期不满足招标文件要求的，且招标人不能接受的。"],
["GW-HB-FJ-009","响应性评审","投标人不接受评标委员会依法所作的修正价格的。"],
["GW-HB-FJ-010","响应性评审","报价明显低于其他投标报价，且投标人不能合理说明或者提供相关证明材料，评标委员会认定以低于成本报价竞标的。"],
["GW-HB-FJ-011","响应性评审","招标文件中明确规定了最高限价，投标人的投标价格剔除角和分后的数值超过最高限价的。"],
["GW-HB-FJ-012","响应性评审","投标报价构成招标文件规定为无效报价的；开标一览表中显示为非报价数值的；小数点错误导致单价总价都出现明显错误的。"],
["GW-HB-FJ-013","响应性评审","投标价格出现数值与货币单位不对应，即出现明显的百倍至万倍高于正常水平的报价。"],
["GW-HB-FJ-014","响应性评审","未按招标文件要求提交投标保证金的；以银行汇款形式提供的投标保证金未提供从投标人基本账户转出有效证明的。"],
["GW-HB-FJ-015","响应性评审","投标范围与招标文件要求存在偏差的，且招标人不能接受的。"],
["GW-HB-FJ-016","响应性评审","投标人提出招标人不能接受的条件或偏差的；未按要求填写具体数据信息以及填写的数据信息不满足招标文件规定的。"],
["GW-HB-FJ-017","响应性评审","投标有效期不满足招标文件要求的。"],
["GW-HB-FJ-018","响应性评审","不按国家法律法规规定填报增值税税率或征收率的。"],
["GW-HB-FJ-019","响应性评审","不符合招标文件实质性要求的投标文件。"],
["GW-HB-FJ-020","响应性评审","152507 及 K1 资格后审：「因投标人投标价格超过本包规定投标人报价平均值规定值的」；K1 资格预审版表述不同。"],
["GW-HB-FJ-021","资格评审","投标文件响应与事实不符或虚假投标的（含提供虚假资格证明文件、业绩证明文件、验收报告、故意修改技术要求并响应等）。"],
["GW-HB-FJ-022","资格评审","串通投标或视为串通投标或经核实认定为串通投标、联合围标或有其他违法行为的。"],
["GW-HB-FJ-023","资格评审","《招标投标法》《招标投标法实施条例》《评标委员会和评标方法暂行规定》等规定的其他否决情形。（注：所引法规原文不在知识库内，无法回读其具体内容）"],
["GW-HB-FJ-024","资格评审","本次投标截止日前三年内发生重大质量问题（以主管部门行政处罚决定或司法机关法律文书为准）。"],
["GW-HB-FJ-025","资格评审","未提供符合招标文件要求的联合体协议书的。"],
["GW-HB-FJ-026","资格评审","为招标人不具有独立法人资格的附属机构（单位）。"],
["GW-HB-FJ-027","资格评审","进入清算程序，或被宣告破产，或其他丧失履约能力的情形。"],
["GW-HB-FJ-028","资格评审","被市场监督管理机关在国家企业信用信息公示系统列入严重违法失信企业名单或经营异常名录的。"],
["GW-HB-FJ-029","资格评审","被最高人民法院在「信用中国」网站列入严重失信主体名单或失信被执行人的。"],
["GW-HB-FJ-030","资格评审","投标单位或法定代表人（单位负责人）在投标截止日前三年内存在行贿犯罪记录的。"],
["GW-HB-FJ-031","资格评审","依据《国家电网有限公司供应商关系管理办法》，为制造商且存在导致被暂停/取消中标资格的不良行为且在处理有效期内的。"],
["GW-HB-FJ-032","资格评审","不满足本次招标公告要求的投标人专用资格要求的。"],
["GW-HB-FJ-033","资格评审","不满足本次招标公告要求的投标人其他资格要求的。"],
["GW-HB-FJ-034","资格评审","对于接受代理商投标的项目，一个制造商对同一品牌同一型号货物委托两个及以上代理商参加同一标包投标的；制造商与其授权代理商参加同一标包投标的。"],
["GW-HB-FJ-035","资格评审","招标人有权对厂商进行资质能力核查，经核查不具备生产场地、设备及工艺控制、生产人员、元器件及产品检测能力等的。"],
["GW-HB-FJ-036","资格评审","与招标人存在利害关系且可能影响招标公正性。"],
["GW-HB-FJ-037","资格评审","为本招标项目的代建人。"],
["GW-HB-FJ-038","资格评审","为本招标项目的代理机构。"],
["GW-HB-FJ-039","资格评审","与本招标项目的监理人或代建人或招标代理机构同为一个法定代表人（单位负责人）的。"],
["GW-HB-FJ-040","资格评审","投标人名称与营业执照或资质证书或生产许可证不一致，且未提供相关变更证明。"],
["GW-HB-FJ-041","资格评审","同一标包或未划分标包的同一招标项目中，与其他投标人的法定代表人为同一人。"],
["GW-HB-FJ-042","资格评审","同一标包或未划分标包的同一招标项目中，与其他投标人存在控股、管理关系。"],
["GW-HB-FJ-043","资格评审","被责令停产停业、暂扣或吊销许可证/执照的；被暂停或取消投标资格的；财产被接管或冻结的。"],
["GW-HB-FJ-044","资格评审","对于代理商投标，未取得投标产品制造商有效授权的。"],
["GW-HB-FJ-045","资格评审","与本招标项目的监理人或代建人或招标代理机构存在控股或参股关系。"],
["GW-HB-FJ-046","其他事项","投标人或投标文件符合招标文件中规定否决投标的其他条款的。"]
];

const CLARIFY=[
[1,"资格审查方式未定：预审版为「在相关联合资格预审项目中预审合格」，后审版为「投标时按分标提交资格审查资料评审」；招标公告两附件并列，正文 3.6 未指明适用","招标人（按采购文件 2.3/2.4 在 ECP 平台发澄清或修改）；评标委员会按澄清后版本执行","1525K1 招标公告 3.6（解析行89）、附件2.1「资格后审」（行317）、附件2.2「资格预审」（行430）；预审版附件2（行232）；后审版附件2（行249）","项目立项/招标方案中资格审查方式的确定文件；招标澄清、答疑或修改通知","高"],
[2,"两版采购文件内嵌「附件2：专用资质业绩要求」表格结构不同：预审版为 4 列表，后审版为 8 列表","招标人","预审版附件2 表头及行1–21+（解析行236–255）；后审版附件2（行249，其分标行与公告附件2.1 行382–394 一致）","指明以哪一表为投标编制依据的澄清文件","高"],
[3,"三个在线监测分标（4032 / 4033 / 4038）仅在后审版附件2 有专用条件行；预审版附件2 表及全文未见该三分标条件（全文 0 命中）","招标人（补列条件或澄清该三分标是否不适用预审）","公告附件2.1 行382–394；预审版附件2 行236–255（未见该三分标）；货物清单_1525K1_4032 第1行","预审版下该三分标的资格条件行（如应有）；澄清通知","高"],
[4,"附件编号不一致：招标公告称「附件2.1（后审）/附件2.2（预审）」，两版采购文件内嵌表格均只称「附件2」","招标人 / 采购文件编制单位","公告行317、430；预审版行232「附件2」；后审版行249「附件2」","—（编号更正随澄清文件出具）","中"],
[5,"指向不明：两版前附表 3.5.3「见招标公告资格要求」、评标办法「资格不符：不满足本次招标公告要求的专用资格要求」——公告存在两个附件时指向何者未定","招标人（澄清）；评标委员会（按澄清后版本执行）","预审版前附表 3.5.3（解析行416）、后审版同条（行450）；预审版评标办法资格评审行（行1269）、后审版同（行1361）","澄清通知","中"],
[6,"附件引用无法闭环：3.9.1/3.9.2 引「投标邀请书附件3/附件4」，5.1 引「招标公告附件3」，但内嵌「附件3」为实物ID标签要求，知识库中无「投标邀请书」","招标人（补齐附件或更正引用）","预审版/后审版 3.9.1、3.9.2（行99）、5.1（行139）、内嵌附件3（预审版行313 / 后审版行348）","「投标邀请书」及其附件3、附件4；「电子投标文件编制及上传说明」对应附件","中"],
[7,"预审版引用的预审条件无法核验：附件2 表以 15 项以上外部「联合资格预审【含补充预审】」项目的「预审合格」为资格条件","招标人（补充被引项目文件）；投标人（若预审版有效，需按分标提交预审合格证明）","预审版附件2 行236–255（序号1–21+ 各行）","各被引「联合资格预审」项目的招标公告及预审结果（合格供应商名单）","中"],
[8,"（范围说明）152507 批次无双版并列：其招标公告仅一份「附件2：专用资质业绩要求」（后审表），采购文件仅单版","—","152507 招标公告 附件2（行272）；152507 采购文件前附表 3.5（行391）、3.5 资格审查资料（行715）","无（无双版差异）","低"],
[9,"（额外发现，非双版差异）货物清单项目名为「2026年物资类用户受托工程项目」，与采购文件/公告标题「2025年…框架协议（1525K1）」年份不一致，证据不足，不能判断系笔误还是执行年度","招标人","货物清单_1525K1_4032 第1行（分标 1525K1-1102002-4032）；两版采购文件题名","项目立项或批复文件（核对项目名称与年度）","低"]
];


// ---------------- lifecycle ----------------
const LIFE = {"stages": [{"id": "L1", "name": "需求与采购计划", "phase": "标前", "legal": ["1358 号文：标前环节主体责任", "国网：采购计划审查（越权采购、未批先招）"], "roles": ["项目部门（需求提报）", "物资部（计划归口）", "经研院/设计单位"], "artifacts": ["采购需求计划", "物资品类与固化 ID", "分标分包策略"], "pains": ["P4 源头质量差", "P9 规则复用难"], "can": ["按品类调采购标准与固化 ID 做一致性比对", "识别越权采购、未批先招、目录外采购等计划形态问题", "把历史负面案例转成可检索的审查要点"], "cannot": ["替代计划审批", "决定分标分包方案", "调整采购方式"], "gate": "物资部计划专责审核签字；超权限上会", "status": "ASSET_ONLY", "evidence": ["术语库 G1 批次与对象 7 条", "术语库 G6 技术规范书与源头质量 5 条"], "note": "有术语与痛点映射，未用真实计划数据跑过；本轮样本不含计划文件。", "platform": ["知识库检索", "术语资产（Skill）"]}, {"id": "L2", "name": "招标文件与技术规范书编制", "phase": "标前", "legal": ["1358 号文：招标文件合规审查机制", "195 号文：招标文件「先体检、再发布」", "国网：范本 + 固化 ID + 采购标准"], "roles": ["物资部（招标文件）", "项目部门（技术规范书）", "代理机构"], "artifacts": ["招标文件", "技术规范书", "评标办法（含评分标准）"], "pains": ["P4 参数不细/品牌型号冲突", "P2 评标标准漏项与歧义", "P6 排他性条款"], "can": ["范本与采购标准对照，提示缺项与措辞不规范", "识别品牌型号指向、排他性表述，并给出判断依据与修改建议", "评标办法结构化成评审项（客观项/主观项分离）"], "cannot": ["代拟招标文件定稿", "设定评分权重", "认定条款违法违规"], "gate": "招标文件审查会签；技术规范书由项目部门签认", "status": "ASSET_ONLY", "evidence": ["规则库 46 条（评标办法前附表之二·否决情形）", "术语库 G6 5 条 / G3 9 条"], "note": "规则与术语已资产化，但\"文件体检\"未对真实招标文件跑过完整一轮；本轮只覆盖否决情形，未覆盖评分办法。", "platform": ["知识库检索", "规则资产（Skill）", "术语资产（Skill）"]}, {"id": "L3", "name": "标前审阅 · 文件体检", "phase": "标前", "legal": ["195 号文：招标文件检测、提示判断依据与修改建议", "1358 号文：排斥限制潜在投标人审查"], "roles": ["物资部（招标文件复核）", "代理机构", "法律/合规"], "artifacts": ["审阅问题清单", "双版差异清单", "修改建议"], "pains": ["P4 源头质量差", "P2 尺度不一", "P5 追溯举证难"], "can": ["同一笔采购内多版本文件逐项比对，给出各自条款位置与解析行号", "跨文件一致性核对（保证金/限价/质保期/交货期）", "每条结论可回读原文，标出证据强度与仍缺文件"], "cannot": ["认定条款违规", "出具审查结论", "要求修改或退回"], "gate": "物资部复核人确认；问题清单转澄清或修改，须招标人签发", "status": "VERIFIED", "evidence": ["V1 真跑：双版 4 维度差异，9,706,361 / 9,763,974 字节，解析行 87 / 232–253 / 249–290", "V7 真跑：9 项待澄清事项，含责任方与「仍缺文件」", "155 份入库、四类索引各 155 ACTIVE（14:13 活查）"], "note": "本阶段是 demo 主战场，有完整真跑读数；但结论均为 AI 输出，未经业务方核对（G3 仍 1/3）。", "platform": ["知识库 + 三类索引", "跨文件比对（V1）", "结构化出表（Function）", "实时状态（C8 桥接）"]}, {"id": "L4", "name": "发标与澄清答疑", "phase": "招标", "legal": ["1358 号文：招标文件澄清与修改的时限与形式要求", "国网：澄清答疑线上留痕"], "roles": ["招标人", "代理机构", "潜在投标人"], "artifacts": ["澄清答疑文件", "补遗书", "投标邀请书"], "pains": ["P5 追溯举证难", "P6 违规干预插手"], "can": ["把审阅问题转成「待澄清事项表」：事项 / 责任方 / 依据 / 仍缺文件", "核对澄清文件与原文是否闭环（引用编号、附件是否齐备）", "生成答疑台账供人工确认后发布"], "cannot": ["代发澄清文件", "判断答复是否满足法定时限", "与投标人直接交互"], "gate": "招标人签发澄清/补遗；代理机构发布并留痕", "status": "VERIFIED", "evidence": ["V7 真跑 139.7 s / 3,623 字符 / 5 条摘录，产出 9 项待澄清表", "Function sgcc-clarification-table 已发布 v1，invoke 231 ms 输出 table/candidate_count/executable=false"], "note": "结构化产出已真跑；但澄清文件本身不在库内，未验证\"澄清后闭环\"这一段。", "platform": ["Function 结构化出表", "知识库检索"]}, {"id": "L5", "name": "投标与开标", "phase": "开评标", "legal": ["1358 号文：开标记录与投标文件接收", "国网 ECP 全流程在线"], "roles": ["投标人", "招标人", "监督人员"], "artifacts": ["投标文件", "开标记录", "投标保证金信息"], "pains": ["P3 围串标隐蔽化", "P1 体量海量"], "can": ["结构化解析投标文件（含 .doc 老格式、扫描件、嵌套表格）", "提取报价、工期、业绩等客观要素供初评使用"], "cannot": ["替代开标程序", "接收或拒收投标文件", "认定串标"], "gate": "开标由招标人主持、监督在场；开标记录签字", "status": "ASSET_ONLY", "evidence": ["附测真跑：.doc（OLE2）已收录、解析 complete、原文可引用", "跨包同名技术规范书可区分（4006 / 4033 标包）"], "note": "仅验证了文件可解析可引用，未用真实投标文件跑过要素提取；本轮样本是招标文件而非投标文件。", "platform": ["文档解析", "知识库索引"]}, {"id": "L6", "name": "初评 · 资格与响应性", "phase": "开评标", "legal": ["1358 号文：评标报告审查", "195 号文：全面提取要素、解析响应度", "国网：否决情形统一裁量"], "roles": ["评标委员会（技术/商务专家）", "招标人代表", "监督"], "artifacts": ["初步评审表", "否决投标情形核对表", "澄清通知"], "pains": ["P1 单份 ≥10–15 分钟", "P2 尺度不一", "P4 否决条款歧义"], "can": ["逐条回读否决情形原文，形成可核对的规则台账", "把投标响应与条款逐项对位，标出可能不满足项（候选）", "命中只产 CANDIDATE，附原文位置供专家判断"], "cannot": ["判定是否构成否决", "作出否决决定", "替代评标委员会表决"], "gate": "评标委员会逐项审议并签字；否决须依规说明理由", "status": "VERIFIED", "evidence": ["V5 真跑 192.9 s / 72 条摘录 / 13,472 字符，逐条回读 46 行否决情形表（turn2b0c5bc86a956549）", "规则库 46 条：资格 25 / 响应 15 / 形式 5 / 其他 1，全部 CANDIDATE"], "note": "规则回读已真跑；但\"投标响应逐项对位\"未跑（无真实投标文件），这是本阶段最大缺口。", "platform": ["知识库检索", "规则资产（Skill）", "拒答能力（V6）"]}, {"id": "L7", "name": "详评 · 评分办法与尺度", "phase": "开评标", "legal": ["195 号文：智能辅助评标、评分不一致预警", "1358 号文：异常价格判定标准"], "roles": ["评标委员会", "招标人代表"], "artifacts": ["评分表", "评分汇总", "评分依据说明"], "pains": ["P2 打分畸高畸低", "P1 阅标时间不足"], "can": ["把评分办法拆成客观项/主观项，客观项逐项取数核对", "同一标包内不同投标人横向对比同一指标，提示明显偏离（不评分）", "给出评分依据定位，供专家复核"], "cannot": ["赋分", "确定权重", "调整专家评分", "替代专家独立评审"], "gate": "专家独立打分并签字；复核人复核；监督在场", "status": "DESIGN_ONLY", "evidence": ["无：本轮 46 条规则只覆盖否决情形，未覆盖评分办法（明确缺口）"], "note": "这是能力缺口最大的一环，也是各省竞争最激烈的一环（山东/浙江/河南/吉林已规模化）。不得演示\"AI 打分\"。", "platform": ["暂无"]}, {"id": "L8", "name": "评标报告核验", "phase": "定标", "legal": ["1358 号文（强制新增）：审查评标报告、客观因素评分不一致、畸高畸低", "195 号文：评分不一致/分值计算错误/偏离过大自动预警"], "roles": ["招标人", "评标委员会", "监督"], "artifacts": ["评标报告", "评分复核记录", "异常情况说明"], "pains": ["P8 缺复核工具", "P2 尺度不一"], "can": ["核对评分汇总与分项是否一致、算术是否正确", "标出客观项评分与投标文件事实不符之处（候选）", "生成复核提示清单，标注依据条款"], "cannot": ["修改评标报告", "认定专家违规", "要求重新评审"], "gate": "招标人审查评标报告并签字；发现问题依规处理", "status": "DESIGN_ONLY", "evidence": ["无：平台侧无评分数据结构，无法核验"], "note": "需要评分表结构化数据才能做，属跨系统集成前提。本轮不承诺。", "platform": ["暂无"]}, {"id": "L9", "name": "定标与中标候选人核验", "phase": "定标", "legal": ["1358 号文：中标候选人核验、定标全过程记录可追溯", "国网：公示节点黑名单比对"], "roles": ["招标人（定标）", "物资部", "监督"], "artifacts": ["中标候选人公示", "定标记录", "核验报告"], "pains": ["P7 资质业绩真伪", "P3 围串标", "P6 廉洁风险"], "can": ["核验候选人资质、业绩、发票与库内材料的一致性（需外部数据源）", "黑名单/失信名单比对（需对接）", "整理定标过程记录为可追溯台账"], "cannot": ["确定中标人", "作出定标决定", "替代招标人主体责任"], "gate": "招标人依法定标并签发；公示期满无异议方可发中标通知书", "status": "DESIGN_ONLY", "evidence": ["无：未接入黑名单/征信/发票任一外部数据源"], "note": "外部数据源接入是硬前提，属集成范畴，本轮明确不做。", "platform": ["暂无"]}, {"id": "L10", "name": "合同签订与履约", "phase": "履约", "legal": ["1358 号文：履约环节主体责任、合同变更管理"], "roles": ["物资部（合同）", "项目部门", "供应商"], "artifacts": ["合同", "供货单", "履约验收记录"], "pains": ["P7 货不对板", "P5 数据孤岛"], "can": ["合同摘要与中标通知书、标准合同核心要素比对", "到货与选购一致性核对（需订单数据）"], "cannot": ["签署合同", "认定违约", "办理结算"], "gate": "合同由授权代表签署；验收由项目部门签认", "status": "DESIGN_ONLY", "evidence": ["无：本轮样本不含合同与订单"], "note": "各省已有成熟案例（宁夏合同审查 3 天→2 小时），但与我方本轮 demo 无关。", "platform": ["暂无"]}, {"id": "L11", "name": "异议投诉与监督", "phase": "监督", "legal": ["1358 号文：异议投诉处理、插手干预登记报告", "国网：全程在线监督、四隔离"], "roles": ["监督部门", "纪检监察", "招标人"], "artifacts": ["异议处理记录", "投诉答复", "干预登记表"], "pains": ["P6 廉洁保密", "P5 举证困难"], "can": ["把全过程操作留痕整理为可导出的举证材料", "检索历史相似异议与处理口径"], "cannot": ["处理异议", "作出投诉答复", "认定违规干预"], "gate": "监督部门/纪检按程序办理并留痕", "status": "DESIGN_ONLY", "evidence": ["无：平台 55 条 org/role/audit 命令全程未配置、未验证"], "note": "组织权限与审计是这条线的前提，当前完全空白——这是产品化的硬缺口之一。", "platform": ["暂无（audit 相关命令 exit 5，权限未开）"]}, {"id": "L12", "name": "归档与后评价", "phase": "监督", "legal": ["1358 号文：档案完整安全、常态化招标后评价"], "roles": ["物资部（档案）", "项目部门"], "artifacts": ["采购档案", "后评价报告"], "pains": ["P9 知识复用难", "P5 追溯"], "can": ["按档案目录核对齐全性", "把后评价结论沉淀为可检索的规则与负面案例"], "cannot": ["替代档案验收", "出具后评价结论"], "gate": "档案验收签字；后评价由物资部组织", "status": "DESIGN_ONLY", "evidence": ["无：未做档案目录核对实验"], "note": "规则资产化的长期价值在这里（把案例变成规则），但本轮未实现回流。", "platform": ["暂无"]}]};
// 仅这三段有真跑产出，才允许跳转；其余不挂假入口
const LIFE_LINK = {L3:'overview', L4:'clarify', L5:'bid', L6:'bid'};
const LSTAT = {VERIFIED:['t-grn','真跑验证'], ASSET_ONLY:['t-amb','资产就绪'], DESIGN_ONLY:['t-gry','设计未实现']};
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function renderLife(id){
  const x = LIFE.stages.find(s=>s.id===id) || LIFE.stages[2];
  const [cls,lab] = LSTAT[x.status];
  let h = '';
  h += '<div class="st">'+x.id+' · '+esc(x.name)+'<span class="ln"></span><span class="tag '+cls+'">'+lab+'</span></div>';
  h += '<div class="ldet">';
  // 左：事实
  h += '<div class="lbox"><h4>这一段在做什么</h4>';
  h += '<div class="lkv"><div class="k">法定依据</div><div class="v">'+x.legal.map(esc).join('<br>')+'</div>';
  h += '<div class="k">参与角色</div><div class="v">'+x.roles.map(esc).join(' · ')+'</div>';
  h += '<div class="k">产出物</div><div class="v">'+x.artifacts.map(esc).join(' · ')+'</div>';
  h += '<div class="k">对应痛点</div><div class="v">'+x.pains.map(esc).join(' · ')+'</div>';
  h += '<div class="k">平台支撑</div><div class="v">'+x.platform.map(esc).join(' · ')+'</div>';
  h += '</div>';
  h += '<div class="lgate"><b>人工门禁：</b>'+esc(x.gate)+'</div>';
  h += '</div>';
  // 右：AI 能力
  h += '<div class="lbox"><h4>AI 在这一段的能力边界</h4>';
  h += '<div class="mini" style="margin-bottom:4px">可做</div><ul class="llist can">'+x.can.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>';
  h += '<div class="mini" style="margin:8px 0 4px">不可做</div><ul class="llist cannot">'+x.cannot.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>';
  h += '</div>';
  h += '</div>';
  // 证据
  h += '<div class="lbox" style="margin-top:14px"><h4>本段证据与诚实标注</h4>';
  h += '<ul class="llist" style="margin-bottom:8px">'+x.evidence.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>';
  h += '<div class="lnote">'+esc(x.note)+'</div>';
  const go = LIFE_LINK[x.id];
  if (go) {
    h += '<div style="margin-top:12px"><span class="tag t-blu" data-go="'+go+'" style="cursor:pointer;padding:4px 12px">查看本段真实产出 →</span></div>';
  } else {
    h += '<div class="mini" style="margin-top:12px">本段尚无真实产出，<b style="color:var(--ink)">不做跳转</b>——避免把设计当成果。</div>';
  }
  h += '</div>';
  document.getElementById('lifeDetail').innerHTML = h;
  document.querySelectorAll('#lifeDetail [data-go]').forEach(b=>{
    b.onclick=()=>{
      const t=b.dataset.go;
      document.querySelectorAll('.nav a').forEach(z=>z.classList.remove('on'));
      document.querySelector('.nav a[data-v="'+t+'"]').classList.add('on');
      document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
      document.getElementById('v-'+t).classList.add('on');
      document.querySelector('.main').scrollTop=0;
    };
  });
}
document.querySelectorAll('.lchip').forEach(c=>{
  c.onclick=()=>{
    document.querySelectorAll('.lchip').forEach(z=>z.classList.remove('on'));
    c.classList.add('on');
    renderLife(c.dataset.s);
  };
});
renderLife('L3');
document.querySelectorAll('.lchip').forEach(c=>{ if(c.dataset.s==='L3') c.classList.add('on'); });
document.getElementById('lifeEntry').onclick=()=>{
  document.querySelectorAll('.nav a').forEach(z=>z.classList.remove('on'));
  document.querySelector('.nav a[data-v="life"]').classList.add('on');
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
  document.getElementById('v-life').classList.add('on');
  document.querySelector('.main').scrollTop = 0;
};

// nav
document.querySelectorAll('.nav a').forEach(a=>{
  a.onclick=()=>{
    document.querySelectorAll('.nav a').forEach(x=>x.classList.remove('on'));
    a.classList.add('on');
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
    document.getElementById('v-'+a.dataset.v).classList.add('on');
    document.querySelector('.main').scrollTop=0;
    closeDrawer();
  };
});

// tables
function renderRules(cat){
  const t=document.getElementById('ruleTable');
  t.querySelectorAll('tr:not(:first-child)').forEach(r=>r.remove());
  RULES.filter(r=>cat==='all'||r[1]===cat).forEach(r=>{
    const tr=document.createElement('tr');
    tr.className='ck';
    tr.innerHTML='<td class="mono">'+r[0]+'</td><td><span class="tag t-blu">'+r[1]+'</span></td><td>'+
      (r[2].length>96?r[2].slice(0,96)+'…':r[2])+'</td>'+
      '<td><span class="tag t-gry">候选待核</span></td><td><span class="ev t"><i></i>原文直引</span></td>';
    tr.onclick=()=>openDrawer(r[0],{
      '规则编号':r[0],'类别':r[1],'来源':'第三章 评标办法前附表之二 · 否决情形表',
      '适用范围':'18 个标包采购文件（同表同文）','状态':'CANDIDATE（未经业务确认）','证据强度':'原文直引'
    },r[2],'系统可做：检索命中本条 · 回读原文 · 列为候选待核 · 给出条款位置。\n系统不可做：判定该条是否成立、否决投标、赋分、替代评标委员会。');
    t.appendChild(tr);
  });
}
renderRules('all');

function renderClarify(){
  const t=document.getElementById('clarifyTable');
  CLARIFY.forEach(c=>{
    const tr=document.createElement('tr');
    tr.className='ck';
    const tg=c[5]==='高'?'t-red':c[5]==='中'?'t-amb':'t-gry';
    tr.innerHTML='<td class="num">'+c[0]+'</td><td>'+c[1]+' <span class="tag '+tg+'">'+c[5]+'</span></td>'+
      '<td>'+c[2]+'</td><td style="font-size:11.5px;color:var(--ink3)">'+c[3]+'</td><td style="font-size:11.5px">'+c[4]+'</td>';
    tr.onclick=()=>openDrawer('待澄清事项 · 第 '+c[0]+' 项',{
      '序号':'第 '+c[0]+' 项 / 共 9 项','影响级别':c[5],'责任方':c[2],'依据':'见下方','仍缺文件':c[4],
      '状态':'候选待核 · 需人工判定'
    },c[1]+'\n\n【依据文件与条款位置】\n'+c[3],'系统只提示判断依据，不替代招标人、评标委员会的判断。本条不代表该事项已构成违规或缺项。');
    t.appendChild(tr);
  });
}
renderClarify();

// bid sheet（真实规则骨架，响应列留空）
const BID_ROWS=[
 {row:1,id:'GW-HB-FJ-001',cat:'形式评审',sub:'格式内容',t:'投标文件未按招标文件规定的格式填写，内容不全或者关键字迹模糊无法辨认的；未按招标文件要求在招标人招投标交易平台信息系统制作并上传凭证单的…'},
 {row:3,id:'GW-HB-FJ-003',cat:'形式评审',sub:'文件签署',t:'对格式文件进行实质性修改或未按格式进行签署的，如由委托代理人签字的，未附有效的法定代表人授权委托书的…'},
 {row:23,id:'GW-HB-FJ-023',cat:'资格评审',sub:'资格不符',t:'未提供符合招标文件要求的联合体协议书的。'},
 {row:24,id:'GW-HB-FJ-024',cat:'资格评审',sub:'主体不符',t:'为招标人不具有独立法人资格的附属机构（单位）。'},
 {row:8,id:'GW-HB-FJ-008',cat:'响应性评审',sub:'投标报价',t:'投标人不接受评标委员会依法所作的修正价格的。'},
 {row:46,id:'GW-HB-FJ-046',cat:'响应性评审',sub:'投标报价',t:'因投标人投标价格超过本包规定投标人报价平均值规定值的（预审版另含「或不平衡报价的」，两版标注不一致）。',vd:true}
];
function renderBid(){
  const box=document.getElementById('bidSheet');
  const be=document.getElementById('bidEntry');
  if(be) be.onclick=()=>{document.querySelector('.nav a[data-v="bid"]').click();};
  if(!box) return;
  let h='<table><tr><th style="width:44px">条号</th><th>核查项（基准条款）</th><th style="width:92px">段</th><th style="width:150px">投标响应</th><th style="width:104px">候选结论</th><th style="width:70px">依据</th></tr>';
  BID_ROWS.forEach(r=>{
    const cls=r.cat==='形式评审'?'t-blu':r.cat==='资格评审'?'t-red':'t-amb';
    const vd=r.vd?' <span class="tag t-amb">两版不一致</span>':'';
    h+='<tr class="ck" data-b="'+r.row+'"><td class="num">'+r.row+'</td>'+
       '<td style="font-size:12px">'+esc(r.t)+vd+'</td>'+
       '<td><span class="tag '+cls+'">'+r.cat.slice(0,2)+'</span><span class="bidsrc">'+r.sub+'</span></td>'+
       '<td class="mini">待投标文件入库</td>'+
       '<td class="mini">未执行</td>'+
       '<td><span style="color:var(--brand2);font-size:11.5px">查看原文</span></td></tr>';
  });
  h+='</table>';
  box.innerHTML=h;
  box.querySelectorAll('[data-b]').forEach(tr=>{
    tr.onclick=()=>{
      const r=BID_ROWS.find(x=>String(x.row)===tr.dataset.b);
      openDrawer('否决情形第 '+r.row+' 条 · '+r.cat+' / '+r.sub,{
        '规则编号':r.id,'段位':r.cat+' · '+r.sub,'台账状态':'CANDIDATE（待业务方确认）',
        '依据章节':'第三章 评标办法 → 评标办法前附表之二：初步评审标准 → 否决情形表',
        '适用标包':'18 个标包采购文件同表同文'+(r.vd?'；本条按版本不同':''),
        '投标响应':'未执行 —— 库内无投标文件','候选结论':'未执行'
      },r.t,'这一行是评审基准，不是审批结论。投标文件入库后，系统按本条去投标文件里找对应响应并标出「未见响应 / 响应不符 / 表述含糊」，只产 CANDIDATE；是否构成否决由评标委员会依招标文件审议。');
    };
  });
}
renderBid();

/* ---------------- 受审结果矩阵（数据来自 F3 真跑证据，静态嵌入） ---------------- */
const BID_CASE = {"meta": {"section": "152507-1102002-4004", "fn": "国网Demo_F2受审侧抽取_真跑证据_V1.json", "rulesTotal": 46, "machineRules": 25, "machineRunnable": 7, "fnVersion": 21}, "rows": [{"bidder": "华中某某电气有限公司", "expect": "全合规", "shouldFail": null, "fail": 0, "cells": {"4": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "10": {"state": "RESPONDED", "reason": "逐物料对位：4 条物料全部未超各自限价，报价合计 15024870 <= 限价合计 16694300", "items": [{"item_no": "100034915900360", "cap_yuan": 10000000, "bid_yuan": 9000000, "delta_yuan": -1000000, "state": "合规"}, {"item_no": "100035912200010", "cap_yuan": 4533100, "bid_yuan": 4079790, "delta_yuan": -453310, "state": "合规"}, {"item_no": "100035912500010", "cap_yuan": 340000, "bid_yuan": 306000, "delta_yuan": -34000, "state": "合规"}, {"item_no": "100035917800010", "cap_yuan": 1821200, "bid_yuan": 1639080, "delta_yuan": -182120, "state": "合规"}], "over": [], "basis": "item"}, "11": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "13": {"state": "RESPONDED", "reason": "情形不适用：tender.bond_required 在文件中明确为免收/不设，本条否决情形不成立", "items": null, "over": null, "basis": null}, "16": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "17": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "39": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}}}, {"bidder": "襄阳某某开关有限公司", "expect": "违规-签章名不一致", "shouldFail": "GW-HB-FJ-004", "fail": 1, "cells": {"4": {"state": "NOT_RESPONDED", "reason": "判定式不成立", "items": null, "over": null, "basis": null}, "10": {"state": "RESPONDED", "reason": "逐物料对位：4 条物料全部未超各自限价，报价合计 15024870 <= 限价合计 16694300", "items": [{"item_no": "100034915900360", "cap_yuan": 10000000, "bid_yuan": 9000000, "delta_yuan": -1000000, "state": "合规"}, {"item_no": "100035912200010", "cap_yuan": 4533100, "bid_yuan": 4079790, "delta_yuan": -453310, "state": "合规"}, {"item_no": "100035912500010", "cap_yuan": 340000, "bid_yuan": 306000, "delta_yuan": -34000, "state": "合规"}, {"item_no": "100035917800010", "cap_yuan": 1821200, "bid_yuan": 1639080, "delta_yuan": -182120, "state": "合规"}], "over": [], "basis": "item"}, "11": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "13": {"state": "RESPONDED", "reason": "情形不适用：tender.bond_required 在文件中明确为免收/不设，本条否决情形不成立", "items": null, "over": null, "basis": null}, "16": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "17": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "39": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}}}, {"bidder": "宜昌某某输变电有限公司", "expect": "违规-单条物料超最高限价", "shouldFail": "GW-HB-FJ-010", "fail": 1, "cells": {"4": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "10": {"state": "NOT_RESPONDED", "reason": "逐物料对位：100035912200010 报 4600000 超限价 4533100（超 66900）", "items": [{"item_no": "100034915900360", "cap_yuan": 10000000, "bid_yuan": 9000000, "delta_yuan": -1000000, "state": "合规"}, {"item_no": "100035912200010", "cap_yuan": 4533100, "bid_yuan": 4600000, "delta_yuan": 66900, "state": "超限"}, {"item_no": "100035912500010", "cap_yuan": 340000, "bid_yuan": 306000, "delta_yuan": -34000, "state": "合规"}, {"item_no": "100035917800010", "cap_yuan": 1821200, "bid_yuan": 1639080, "delta_yuan": -182120, "state": "合规"}], "over": ["100035912200010"], "basis": "item"}, "11": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "13": {"state": "RESPONDED", "reason": "情形不适用：tender.bond_required 在文件中明确为免收/不设，本条否决情形不成立", "items": null, "over": null, "basis": null}, "16": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "17": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "39": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}}}, {"bidder": "荆州某某智能装备有限公司", "expect": "违规-投标有效期不足", "shouldFail": "GW-HB-FJ-016", "fail": 1, "cells": {"4": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "10": {"state": "RESPONDED", "reason": "逐物料对位：4 条物料全部未超各自限价，报价合计 15024870 <= 限价合计 16694300", "items": [{"item_no": "100034915900360", "cap_yuan": 10000000, "bid_yuan": 9000000, "delta_yuan": -1000000, "state": "合规"}, {"item_no": "100035912200010", "cap_yuan": 4533100, "bid_yuan": 4079790, "delta_yuan": -453310, "state": "合规"}, {"item_no": "100035912500010", "cap_yuan": 340000, "bid_yuan": 306000, "delta_yuan": -34000, "state": "合规"}, {"item_no": "100035917800010", "cap_yuan": 1821200, "bid_yuan": 1639080, "delta_yuan": -182120, "state": "合规"}], "over": [], "basis": "item"}, "11": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "13": {"state": "RESPONDED", "reason": "情形不适用：tender.bond_required 在文件中明确为免收/不设，本条否决情形不成立", "items": null, "over": null, "basis": null}, "16": {"state": "NOT_RESPONDED", "reason": "判定式不成立", "items": null, "over": null, "basis": null}, "17": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "39": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}}}, {"bidder": "黄石某某电力科技有限公司", "expect": "违规-税率不在法定集合", "shouldFail": "GW-HB-FJ-017", "fail": 1, "cells": {"4": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "10": {"state": "RESPONDED", "reason": "逐物料对位：4 条物料全部未超各自限价，报价合计 15024870 <= 限价合计 16694300", "items": [{"item_no": "100034915900360", "cap_yuan": 10000000, "bid_yuan": 9000000, "delta_yuan": -1000000, "state": "合规"}, {"item_no": "100035912200010", "cap_yuan": 4533100, "bid_yuan": 4079790, "delta_yuan": -453310, "state": "合规"}, {"item_no": "100035912500010", "cap_yuan": 340000, "bid_yuan": 306000, "delta_yuan": -34000, "state": "合规"}, {"item_no": "100035917800010", "cap_yuan": 1821200, "bid_yuan": 1639080, "delta_yuan": -182120, "state": "合规"}], "over": [], "basis": "item"}, "11": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "13": {"state": "RESPONDED", "reason": "情形不适用：tender.bond_required 在文件中明确为免收/不设，本条否决情形不成立", "items": null, "over": null, "basis": null}, "16": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}, "17": {"state": "NOT_RESPONDED", "reason": "判定式不成立", "items": null, "over": null, "basis": null}, "39": {"state": "RESPONDED", "reason": "判定式成立", "items": null, "over": null, "basis": null}}}], "cols": [["4", "签章"], ["10", "限价"], ["11", "报价算术"], ["13", "保证金"], ["16", "有效期"], ["17", "税率"], ["39", "法人不重"]], "blocked": [{"field": "bid.price_total", "rules": ["GW-HB-FJ-009", "GW-HB-FJ-046"]}, {"field": "bid.qualification_fields", "rules": ["GW-HB-FJ-030", "GW-HB-FJ-031"]}, {"field": "bid.format_completeness", "rules": ["GW-HB-FJ-001"]}, {"field": "bid.voucher_index_viewable", "rules": ["GW-HB-FJ-001"]}, {"field": "bid.alternative_declared", "rules": ["GW-HB-FJ-002"]}]};
function renderBidCase(){
  const tbl=document.getElementById('bidCaseTbl');
  if(!tbl) return;
  const ORDER=BID_CASE.cols.map(c=>c[0]);
  BID_CASE.rows.forEach((r,ri)=>{
    const tr=document.createElement('tr');
    let h='<td>'+esc(r.bidder)+'</td><td class="mini">'+esc(r.expect)+'</td>';
    ORDER.forEach(k=>{
      const c=r.cells[k];
      if(!c){h+='<td class="mini" style="color:var(--ink3)">未跑</td>';return;}
      let tag,color;
      if(c.state==='NOT_RESPONDED'){tag='判否';color='t-red';}
      else if(c.state==='RESPONDED'){tag='通过';color='t-grn';}
      else if(c.state==='UNCERTAIN'){tag='待澄清';color='t-amb';}
      else {tag='人判';color='t-gry';}
      let extra='';
      if(k==='10'&&c.over&&c.over.length) extra=' <span class="mini" style="color:var(--red)">超'+c.over.length+'条</span>';
      h+='<td><span class="tag '+color+'" data-c="'+ri+':'+k+'" style="cursor:pointer">'+tag+'</span>'+extra+'</td>';
    });
    h+='<td class="num">'+r.fail+'</td>';
    tr.innerHTML=h;
    tbl.appendChild(tr);
  });
  tbl.querySelectorAll('[data-c]').forEach(el=>{
    el.onclick=()=>{
      const [ri,k]=el.dataset.c.split(':');
      const r=BID_CASE.rows[ri], c=r.cells[k];
      const meta={'投标人':r.bidder,'剧本':r.expect,'结论':c.state,
                  '依据':'判定式由抽取字段直接计算，不经模型',
                  '对位口径':c.basis==='item'?'按行项目号逐条对位':c.basis==='total'?'仅取得标包总价':'—'};
      let body=c.reason||'';
      let quote=null;
      if(c.items&&c.items.length){
        const lines=c.items.map(x=>'  '+x.item_no+'  限价 '+(x.cap_yuan||0).toLocaleString()+
          '  报价 '+(x.bid_yuan==null?'未报价':x.bid_yuan.toLocaleString())+
          '  差额 '+((x.delta_yuan||0)>=0?'+':'')+(x.delta_yuan||0).toLocaleString()+
          '  ['+x.state+']').join('\n');
        quote='行项目号 / 限价 / 报价 / 差额 / 状态\n'+lines;
      }
      openDrawer('行'+k+' · '+r.bidder,meta,quote,body);
    };
  });
}
renderBidCase();

// diff tabs
const DIFFS=[DIFF,DIFF2,DIFF3,DIFF4];
function renderDiff(i){
  const box=document.getElementById('diffBody');
  const rows=DIFFS[i];
  let h='<table><tr><th style="width:104px">比对维度</th><th>资格预审版（位置）</th><th>资格后审版（位置）</th><th style="width:66px">依据</th></tr>';
  rows.forEach(r=>{
    h+='<tr><td><b>'+r.d+'</b></td><td>'+r.pre+'</td><td>'+r.post+'</td><td><span class="cite" data-ev="'+r.ev+'" style="font-size:10.5px">查看原文</span></td></tr>';
  });
  h+='</table>';
  box.innerHTML=h;
  box.querySelectorAll('[data-ev]').forEach(el=>{
    el.onclick=()=>{const e=EVID[el.dataset.ev];openDrawer(e.title,e.meta,e.quote,'两版此条逐字相同或差异如上所述；均为解析文本行号，非 PDF 页码。');};
  });
}
renderDiff(0);
document.querySelectorAll('[data-tab]').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('[data-tab]').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    renderDiff(+b.dataset.tab);
  };
});
document.querySelectorAll('[data-rtab]').forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll('[data-rtab]').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');
    renderRules(b.dataset.rtab);
  };
});

// drawer
const drawer=document.getElementById('drawer');
function openDrawer(title,meta,quote,foot){
  document.getElementById('dTitle').textContent=title;
  let h='<div class="meta">';
  for(const k in meta){h+='<div class="k">'+k+'</div><div class="v">'+meta[k]+'</div>';}
  h+='</div><div class="mini" style="margin-bottom:6px">原文摘录</div><div class="quote">'+quote.replace(/\n/g,'<br>')+'</div>';
  if(foot) h+='<div class="note" style="margin-top:14px">'+foot.replace(/\n/g,'<br>')+'</div>';
  h+='<div class="mini" style="margin-top:14px;line-height:1.8">行号为解析文本行号，非 PDF 页码。原文摘录未经业务方逐条核对。</div>';
  document.getElementById('dBody').innerHTML=h;
  drawer.classList.add('open');
  document.querySelector('.main').classList.add('pushed');
}
function closeDrawer(){drawer.classList.remove('open');document.querySelector('.main').classList.remove('pushed');}
document.getElementById('dClose').onclick=closeDrawer;

// evidence in other views
document.querySelectorAll('[data-ev]').forEach(el=>{
  if(el.classList.contains('cite')&&el.closest('#diffBody')) return;
  el.onclick=()=>{
    const e=EVID[el.dataset.ev];
    if(!e) return;
    openDrawer(e.title,e.meta,e.quote,'本条为术语口径说明或原文摘录，用于对齐理解，不构成对规则的解释或扩张。');
  };
});

// ask
document.getElementById('btnAsk').onclick=()=>{
  alert('演示环境说明：\n\n当前前端为只读白名单，不能直接发起新提问。\n现场即兴提问请切换到平台原生会话；\n本页展示的是已跑测的真实结果。\n\n可即兴跑通的题型：40 秒内出答案（如「有没有这份文件」「老格式能不能读」「某条款在哪」）。');
};
document.getElementById('btnDemo').onclick=()=>{
  document.getElementById('qbox').value='两版采购文件在型式试验要求上有什么差异？';
};
document.querySelectorAll('.sample span').forEach(s=>{
  s.onclick=()=>{document.getElementById('qbox').value=s.dataset.q;};
});
