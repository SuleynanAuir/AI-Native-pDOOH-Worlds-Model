> 本文包含历次本地验收记录。GitHub 仅提交最新 `output/modal-ui/` 界面示例；其他 `output/` 链接需在本地运行后查看。快速启动见 [README.md](../README.md)。

# AI-Native pDOOH Screen Planning

> 输入原始屏幕库存、屏幕照片、目标国家的社会学资料、可选消费者调研和总预算；从“什么人可能经过、是否容易看见”出发，输出屏幕筛选、重要性评估与预算分配方案。

## 1. 我们实际拥有的输入

平台不预设完整的 Campaign Brief、广告创意或个人级用户数据。当前输入只有以下五类。

### 1.1 Original Frame Excel（必选）

参考文件为 [`data/test.xlsx`](../data/test.xlsx)。系统只依赖表头和字段语义，不依赖示例中的具体数值。

工作簿的五个 Sheet 各有明确作用：`UnfilteredFrames` 是输入库存，`FilteredFrames` 是筛选结果，`Proposal` 是预算方案，`PICS` 是代表性图片，`POI` 则通过 `ADDRESS_COUNTRY`、`Location`、`POI` 补充目标区域和地点范围。

其中 `UnfilteredFrames` 是原始屏幕池；表头提供的信息可以分为六组：

| 信息组 | Excel 表头 | 能回答的问题 |
|---|---|---|
| 媒体与屏幕身份 | `SSP`、`MARKET`、`VIOOH_ID`、`ASSETUUID`、`VISUAL_UNIT_CODE` | 屏幕属于哪个市场、媒体来源和唯一资源 |
| 目标区域 | `GEOM`、`ADDRESS_THOROUGHFARE`、`ADDRESS_ADMINISTRATIVE_AREA`、`ADDRESS_LOCALITY`、`ADDRESS_POSTAL_CODE`、`ADDRESS_COUNTRY`、`ADDRESS_ISO3_COUNTRY_CODE`、`LATITUDE`、`LONGITUDE`、`IATA` | 本次分析对应哪个国家、地区、城市或机场区域 |
| 屏幕形态 | `PRODUCT_FORMAT_NAME`、`DIGITAL_SPEC_WIDTH`、`DIGITAL_SPEC_HEIGHT`、`WIDTHXHEIGHT`、`ASPECT_RATIO`、`DIGITAL_SPEC_MOTION_TYPE`、`DIGITAL_SPEC_FPS`、`DIGITAL_SPEC_ROTATION`、`SLOT_DURATION` | 屏幕有多大、什么比例、能否播放动态内容、单次展示多长 |
| 场所与周边 | `VENUE_TAXONOMY_ID`、`VENUE_TAXONOMY_VALUE`、`CLOSEST_POI`、`DISTANCE_TO_CLOSEST_POI` | 屏幕位于什么场所，附近是什么地点，离核心 POI 多远 |
| 商业与曝光 | `IMPRESSIONS`、`FLOORCPM`、`MEDIAOWNERCURRENCY`、`VIOOHSELECTOPTIN`、`SCORE_P` | 屏幕已有多少曝光、底价、币种、可售状态与既有评分 |
| 图片关联 | `FRAMEIMAGEPATH` | 到哪里取得该屏幕对应的现场照片 |

源文件同时出现 `CLOSEST_POI` 与拼写变体 `CLOEST_POI`。系统将二者映射为同一字段，但保留原始列以便追溯。

这份 Excel 首先锁定目标区域。例如，可通过 `MARKET + ADDRESS_COUNTRY + ADDRESS_ADMINISTRATIVE_AREA + ADDRESS_LOCALITY` 选定某个国家的某个地区，再用经纬度、邮编或 `IATA` 做进一步确认。

`SCORE_P` 只作为已有参考分进行对照，不会直接替代平台对曝光、可见性、位置、市场和成本的重新判断。

### 1.2 国家社会学资料（必选）

与 Excel 锁定区域对应的文献资料，包括：

- 当地消费能力与消费结构。
- 对价格、品质、品牌和体验的态度。
- 文化价值观、生活方式与社会观念。
- 不同年龄或生活阶段的消费差异。
- 当地对户外广告、公共空间和商业表达的接受方式。

这些资料帮助平台解释“这个区域的人为什么消费”，而不只是“这里有多少人”。

### 1.3 公司内部消费者调研（可选）

可附上本公司对该地区消费者的群体画像或市场调研，用来：

- 补充公开文献没有覆盖的细分群体。
- 修正过于宽泛的全国性结论。
- 对消费偏好、场景和人群判断进行二次校正。

如果没有这部分资料，平台使用国家/区域社会学文献作为基础；不会自动编造公司内部画像。

### 1.4 总预算与币种（必选）

输入形式：

```text
Total Budget: 500,000
Currency: GBP
```

屏幕原始价格使用 `FLOORCPM + MEDIAOWNERCURRENCY`。如果预算币种与媒体币种不同，方案会锁定汇率来源和时点，同时保留原币价格与统一预算币种，避免混用。

### 1.5 每块屏幕的现场照片（必选）

照片通过屏幕 ID 或 `FRAMEIMAGEPATH` 与 Excel 记录对应。照片主要用来判断：

- 屏幕在现场是否醒目。
- 屏幕相对道路、人行区域和主要视线的位置。
- 是否存在树木、建筑或其他广告牌遮挡。
- 屏幕大小在实际环境中的视觉占比。
- 周边更接近商业、通勤、休闲、交通还是其他场景。

照片用于理解屏幕和环境，不用于识别或分析照片中的具体个人。

---

## 2. 中间过程

```text
Original Frames
  → 锁定目标区域
  → 清洗并筛选可用屏幕
  → 还原屏幕现场与周边环境
  → 理解区域消费与文化背景
  → 推演可能经过的人群
  → 评估每块屏幕的重要性
  → 在总预算内组合屏幕与 SOT
  → 输出 Proposal
```

### 第一步：从 Original Frames 锁定分析范围

平台先使用国家、行政区、城市、邮编、机场代码与经纬度确定目标区域，并生成 `FilteredFrames`。

筛选同时检查：

- 屏幕 ID 是否完整且唯一。
- 经纬度是否与国家和地区一致。
- 屏幕是否允许进入 VIOOH Select。
- 图片、曝光、底价、币种和场所字段是否可用。
- 重复、缺失或明显异常的记录是否需要人工确认。

### 第二步：还原每块屏幕的真实场景

Excel 提供“屏幕是什么”，照片和位置提供“屏幕在哪里、看起来怎样”。

平台将以下内容合并：

```text
经纬度与地址
+ Venue Type
+ Closest POI 与距离
+ 屏幕尺寸、比例、方向和动态能力
+ 现场照片
= Screen Context
```

由此区分道路、商业街、办公区、交通枢纽、机场、住宅区等不同环境。

### 第三步：从路人视角评估曝光机会

这里的“路人”是可能经过某类地点的代表性群体，不是真实个人。

平台会回答：

- 什么样的人可能经过这个场所？
- 他们更可能步行、乘车、候车还是停留？
- 屏幕是否位于自然视线范围内？
- 屏幕尺寸和观看距离是否足以形成有效观看机会？
- 原始 `IMPRESSIONS` 与现场环境是否相互支持？
- 多块屏幕是否集中在相同区域，造成重复投入？

社会学资料提供区域层面的消费与文化背景；可选内部调研进一步修正人群判断。

### 第四步：为屏幕建立重要性评估

每块屏幕的权重来自以下维度，而不是只按曝光量排序：

| 维度 | 主要依据 |
|---|---|
| Exposure Potential | `IMPRESSIONS`、场所客流特征、可能经过的人群 |
| Visibility | 屏幕尺寸、比例、位置、照片中的视线与遮挡 |
| Location Value | Venue、POI 类型、POI 距离、区域角色 |
| Market Relevance | 当地消费力、观念、文化价值观；可选内部画像 |
| Cost Efficiency | `FLOORCPM`、媒体币种与预算币种 |
| Availability | `VIOOHSELECTOPTIN`、数据完整性和资源有效性 |

平台会同时给出总分和各维度原因，避免产生一个无法解释的黑盒排名。

### 第五步：在预算内形成组合

平台根据屏幕评分、底价、曝光、SOT 与总预算比较不同组合：

- 优先覆盖更多区域的组合。
- 优先选择高价值场所的组合。
- 优先提高可交付曝光的组合。
- 平衡屏幕质量、曝光与成本的组合。
- 对关键屏幕不可用时的替代组合。

若未提供具体投放日期或 Campaign 天数，平台可以先输出预算级推荐；最终交易报价与曝光交付仍需确认 `Date` 和 `Campaign days`。

---

## 3. 输出

参考工作簿已经体现了三类核心输出。

### 3.1 FilteredFrames：候选屏幕池

保留原始 Frame 字段，并增加：

- 是否进入候选方案。
- 数据质量与缺失提示。
- Screen Context。
- 屏幕重要性总分。
- Exposure、Visibility、Location、Market、Cost 和 Availability 分项评分。
- 入选或未入选原因。

### 3.2 Proposal：预算与投放建议

输出字段与 `test.xlsx` 的 `Proposal` 表头对齐：

| 输出组 | 字段 |
|---|---|
| 方案范围 | `Date`、`Country`、`POI`、`Venue type` |
| 价格基准 | `Floor price 2026 CPM`、`VIOOHSELECTCPMLOCAL`、`Floor price 2026 CPM (VS)`、`Floor price 2026 CPM (USD)` |
| 资源规模 | `Screen no.`、`Monthly impressions`、`Campaign days` |
| 推荐决策 | `Suggested screen no`、`Suggested SOT` |
| 交付与成本 | `Impression deliverable`、`Media Budget (USD)`、`DSP fee`、`Total investment` |

如果预算不是 USD，主方案应以用户输入币种为主，同时保留 USD 参考列。

### 3.3 PICS：代表性屏幕图片

输出字段与参考工作簿的 `PICS` 表头对齐：

```text
Market
Country
VenueType
PickedImageCount
Image1
Image2
Image3
```

图片用于展示每个市场和 Venue Type 中具有代表性的屏幕环境，让 Planner 能直观看到推荐资源实际处于怎样的场景。

### 3.4 推荐说明

每个方案还需要回答：

- 为什么选择这个国家、地区与 POI。
- 为什么这些 Venue Type 更重要。
- 哪些屏幕由曝光驱动，哪些由场景与可见性驱动。
- 预算主要分配到了哪些屏幕和场所。
- 建议屏幕数与 SOT 如何影响曝光交付。
- 哪些判断来自 Excel，哪些来自照片，哪些来自社会学文献或内部调研。
- 缺失哪些信息可能改变最终结果。

---

## 4. 整体输入输出

```text
INPUT
├── Original Frame Excel
├── 国家消费力、观念与文化价值观文献
├── 可选：公司内部消费者群体画像调研
├── Total Budget + Currency
└── 每块屏幕的现场照片

PROCESS
├── 区域锁定与 Frame 筛选
├── 屏幕现场与 POI 场景还原
├── 区域消费者与文化背景理解
├── 可能路人与曝光机会推演
├── 屏幕重要性评分
└── 预算、屏幕数与 SOT 组合

OUTPUT
├── FilteredFrames
├── Screen Importance Scorecard
├── Proposal
├── PICS
└── 推荐理由、风险与数据来源
```

## 一句话总结

> 从 Original Frame 表头锁定区域与可售屏幕，结合现场照片和当地社会学资料判断“什么人可能经过、屏幕是否容易被看见”，再依据曝光、场景、消费背景、底价与总预算，输出建议屏幕数、SOT、可交付曝光、媒体预算、DSP fee 和总投资。

详细技术设计见 [README.md](../README.md)。


## 当前代码：正式库存规划流程

`/planning` 为完整规划工作台，首页 `/` 为 OASIS 人群模拟 UI。原有可调参数的路人模拟保留在 `/audience-demo`；旧社交模拟入口在 `/legacy`，需设置 `ENABLE_LEGACY_SIMULATION=true` 并安装旧引擎依赖及配置密钥。

### 启动与配置

```bash
# 仅使用屏幕规划，无需安装 Zep / OASIS
python3 -m pip install -r backend/requirements-planning.txt
npm ci --prefix frontend
# 两个终端分别运行
python3 backend/run.py
npm run frontend
```

如已安装完整项目依赖，原来的 `npm run dev` 也可继续使用。

在根目录 `.env` 中配置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_NAME`。可复制 `.env.example`；真实 `.env` 已被 Git 忽略。图片请求优先使用 `MULTIMODAL_VISION_API_KEY`、`MULTIMODAL_VISION_BASE_URL`、`MULTIMODAL_VISION_MODEL`，未填写时回退主配置。设置 `MULTIMODAL_ENABLED=true` 和 `MULTIMODAL_VISION_API_STYLE=chat`。文本与图片模型均须支持 JSON 输出；图片模型还须支持 OpenAI Chat Completions 的 `image_url`。

DeepSeek 配置示例：主模型 `deepseek-v4-flash`，图片模型 `deepseek-flash`，地址 `https://api.deepseek.com/v1`。`MULTI_DISCUSSION_*` 可保留给其他模块，但此屏幕规划流程不依赖讨论专家路由，也不依赖 Zep；未配置的 `LLM_BOOST_*` 不需要添加。未配置模型时，Excel 清洗、参数评分、预算组合及导出仍可使用；没有证据的可见性和市场分数明确标记为中性先验 50。接口验证失败不会保存虚构的模型结果。

飞书图片可下载后上传，也可配置服务端 `FEISHU_TENANT_ACCESS_TOKEN`，在界面输入有权限访问的文件 token（Drive file / 文档 media）。文件夹链接不是图片，不会被直接当作视觉证据；无需在浏览器填写访问令牌。

### 操作流程

1. 上传包含 `UnfilteredFrames` 的 `.xlsx`，或点击“使用 data/test.xlsx 测试”。表头按语义归一化，兼容 `CLOSEST_POI/CLOEST_POI`；每条记录保留原始字段。缺失/重复 ID、非正曝光/CPM、未确认可售、无效坐标等会排除，并显示原因。
2. 输入国家、城市、市场、场所与 POI 筛选。可选地理边界为 `[最小纬度, 最小经度, 最大纬度, 最大经度]`；未提供边界时明确提示尚未验证国家/城市与坐标的一致性，不冒充已完成地理核验。
3. 可选上传区域资料或消费者调研（PDF/TXT/MD）。扫描 PDF 需先 OCR。照片按屏幕 ID 或原图片路径文件名关联；也可指定 ID 上传单张、关联公开 HTTPS 图片或导入飞书图片。
4. 勾选屏幕，设置分析重点，执行多模态分析。输出事实、视觉观察、推测、观看距离不确定性与代表性人群的路过/停留/观看反应。没有图片不给视觉评分，没有资料不给市场评分；引用必须属于实际输入来源。不识别个人、不凭图片生成客流人数或群体占比。
5. 手动输入预算、币种、日期/天数、库存曝光统计周期、DSP 费率、CPM 加价率、SOT 步长与上限。汇率格式如 `{"USD":1,"GBP":1.25}`，表示 **1 单位原币对应多少 USD**。涉及非 USD 汇率必须填写来源和日期；缺少媒体币种汇率的屏幕会排除，不能混币计算。
6. 按道路/通勤、商业/购物或均衡场景选择权重，并可修改六个维度。默认重点为可见性 28%、位置 22%、市场 22%；`SCORE_P` 仅参考。支持额外的自定义目标权重。
7. 比较覆盖、场所价值、曝光、均衡、替代和可选自定义方案。替代方案默认排除均衡方案投入最高的屏幕，也可指定不可用 ID。
8. 导出所选方案。库存、图片或资料更新后旧导出失效，必须重新计算。项目保存于 `backend/uploads/planning/<project_id>/`，浏览器可恢复上次项目。

### 计算与边界

- 估算曝光 = `IMPRESSIONS × 规划天数 / 原始曝光周期天数 × SOT`。默认原始周期为 30 天，必须按实际数据来源确认；不是实测去重人数。
- 统一币种 CPM = `FLOORCPM × (1 + CPM加价率) × USD每媒体币种 / USD每预算币种`。
- 媒体预算 = `估算曝光 / 1000 × 统一币种 CPM`；DSP 费用 = `媒体预算 × DSP费率`。
- 分配器按离散 SOT 步长，以加权分项收益/成本逐步选择，按约 0.01 度区域网格降低重复投入收益。每步金额使用 Decimal 向上取整到分，整体预算向下取整到分，确保不超支。取整预留单独列出。
- 这是可解释贪心组合，不承诺全局最优。区域网格不是人群交集模型；价格仍需媒体确认，未提供的税费、最低起订条件不在模型中。
- 缺少开始日期或天数时，标记为预算级建议；使用显式的预算估算天数，导出 `Impression deliverable` 留空，估算值单独列出。
- 模型分数是未校准推测，不是广告效果预测。观察与人群推断均附来源；没有数据时保留未知，不编造内部调研或消费者数量。

### 导出结构

`FilteredFrames` 保留全部原始行并标记候选、入选、排除原因及风险，便于审计；`Screen Scorecard` 给出六维分数、权重和证据；`Proposal` 对齐源工作簿字段，以逐屏幕行记录 SOT 与金额；`PICS` 按市场/国家/场所收集最多三张代表性图片，已上传/飞书下载的图片嵌入工作簿，外链保留来源；`Audit` 保存输入、公式、预算余额、汇率和风险；`POI` 保留原工作簿范围。

`Proposal` 的 `Total investment` 以用户预算币种为主，另列 `Total investment (USD)` 与媒体 USD 参考值。`DSP fee` 沿用实际样本的费率语义，另列 DSP 金额。库存只有 FLOORCPM 时，VIOOH Select 参考列按用户显式加价计算，不假定样本中的 20% 加价或 15% DSP 费率。

### 接口与验证

接口前缀 `/api/planning`：`POST /import`（workbook 表单文件）、`POST /sample`、`GET /<id>`、`POST /<id>/documents`、`POST /<id>/photos`、`POST /<id>/image-link`、`POST /<id>/feishu-image`、`POST /<id>/analyze`、`POST /<id>/plan`、`GET /<id>/export?strategy=balanced`。

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_audience_simulation.py backend/tests/test_screen_planning.py -q
npm run build
```

测试使用真实 `data/test.xlsx`：149 条原始记录，其中 144 条通过基本清洗，5 条因曝光非正数被排除。测试覆盖表头别名、原始字段保留、重复/区域/异常校验、跨币种计算、预算不超支、SOT 边界、替代排除、缺证据降级、模型请求与来源校验、Excel 公式缓存、上传与旧结果失效。自动化测试使用受控响应；本次另外使用已配置的 DeepSeek 图片接口完成了真实 API 联调，飞书服务尚未进行真实凭据联调。


### 本次全流程验证结果

使用 `output/planning-smoke/synthetic-inventory.xlsx` 的 8 条合成库存、2 张明确标记的合成图片、1 份模拟地区资料，从浏览器上传开始验证了分析、评分、跨币种计算、方案对比和下载。重复 ID 两条、非正曝光一条、不可售一条、目标区域外一条被排除，留下 3 个候选。

先通过本地模拟模型验证传输链路，再实际调用 DeepSeek `deepseek-flash` 分析两张图片。模型识别了第二张图的部分遮挡，并把缺少真实研究依据的市场评分留为未知；此过程中修复了 `score: null` 被误判为请求失败的问题。

测试参数为 500 GBP、14 天、15% DSP 费率、10% CPM 加价、最大 SOT 60%，汇率均为测试值。真实 API 结果驱动的均衡方案选中 2 块屏幕，总投资 **491.20 GBP**（USD 参考 **614.00**），预算余额 **8.80 GBP**。6 个方案均未超预算。结果仅验证系统链路，不是实际广告投放结论。

- [真实 API 联调导出的 Excel](../output/planning-smoke/deepseek-balanced.xlsx)
- [完整评分与方案 JSON](../output/planning-smoke/deepseek-results.json)
- [独立工作簿验证结果](../output/planning-smoke/deepseek-verification.json)

45 项后端测试通过，前端生产构建通过；浏览器验证了上传、详情、方案计算、下载、参数修改后的失效保护、刷新恢复及移动端布局。工作簿另外通过独立读取库验证公式缓存、预算上限、USD 参考值与嵌入图片。真实模型联调仅发送合成测试数据。

## OASIS 人群模拟可视化平台

首页 `/` 与 `/world` 现在进入人群模拟 UI，库存规划移至 `/planning`。界面提供场景地图、代表性画像编辑、屏幕交互连线、逐轮事件流、Agent 决策解释、群体筛选、回放时间轴与 JSON 导出。

这里使用真实 **OASIS 0.2.5** 的 `SocialAgent`、`AgentGraph`、`env.step` 与 `INTERVIEW` 动作调用 DeepSeek；OASIS 原生 SQLite `trace` 记录是决策来源。空间位置、路径和屏幕遇见顺序由本项目场景适配层生成，**不是 OASIS 的物理行人引擎，也不是真实轨迹或客流预测**。每轮传入该 Agent 的最近行为及同屏幕附近上一轮群体反应，形成有上下文的观看推演。

默认用 **100 个代表性 Agent 表示 10,000 人**，默认按所选地区与场所生成 12 类合成人群，搭配 3 个屏幕、一天 24 个小时轮次。代表数支持 4–200，总人群支持不小于代表数且不超过 100 万，可模拟 1–3 天；每个非空群体至少有一个代表，因此默认 12 类时至少需要 12 个 Agent。用户可编辑群体名称、相对占比、来源和画像，增加或移除群体（最多 40 类）。预览人群只执行代码分配，不调用 LLM。

画像包含生活阶段、消费能力、经济背景、家庭构成、偏好、需求、价格敏感度、移动方式和注意力情景；群体内再区分时间压力、注意习惯、采购计划、当前需求、决策习惯和渠道偏好。早期通用模板包含职场、家庭、学生、退休等情景；新模拟按地区资料与场所任务重新生成人群构成，不固定使用这份名单。这些分类和占比均是用户可校正的假设，不是地区人口统计，也不依据照片识别个人阶层。

整数权重采用最大余数法，先分配群体人口，再分配代表数及其代表人数，保证 `sum(agent.represented_population) == total_population`，并避免产生零权重 Agent。每个代表画像的真实 OASIS 决策按其代表人数加权，注意人数为 `sum(weight × 是否注意)`，平均停留为 `sum(weight × 停留秒数) / 出场且反应已知的权重总和`。未知输出保留为未知，不补造群体反应。加权人数是情景外推，**100 个代表仍只有 100 个决策单元，不能视为 1 万次独立观测，也不能把各轮相加当成去重触达**。

点击“运行 OASIS”会实际调用已配置的 LLM，每小时只为排程出场的 Agent 调用一次 LLM，未出场记录由代码生成并标注 `scenario_schedule`，没有 OASIS trace_id；增大总人群不增加请求数。worker 以 8 路并发、每批最多 16 个 Agent 执行 OASIS 动作并显示批次进度；一个界面轮次对应一个情景小时，包含该小时所有出场代表的决策，对应多个原生 OASIS step；原生引擎步数不等于小时数。暂停/停止在当前界面轮次结束后生效，回放控件只播放已有记录，不额外调用模型。随机种子控制示意场景布局；LLM 决策不是固定种子的确定性结果。

每次经过还携带可检查的 `encounter` 条件：正面/侧面/背向/等候四种合成路线等概率抽样，临时遮挡按屏幕情景遮挡率抽样，可观看窗口根据时间压力在 1–30 秒的候选区间选取；通勤高峰上限为 5 秒，夜间消费窗口下限为 8 秒，均为情景假设。这些是明确记录的场景假设，不是实地测量。没有视线时只能路过，观看不能超过机会窗口；违反约束的模型输出标记未知。旧版窗口按时段调整；本地模板则保留画像时间压力窗口，由具体到访任务和地区资料支持模型决策，避免把机场早间一律当成上班通勤。场景条件不依收入或代表人数设定，反应由 OASIS Agent 调用 LLM 决定，不强制生成某种反应比例。未提供广告内容时不得编造屏幕上的优惠或购买反应。

可勾选“使用最近规划库存”，从已计算的库存候选中取最多三块屏幕，带入场所、可见性评分与已有场景分析。初始 Agent 仍为代表性假设，不从真实个人信息生成。

### 按国家、社区与场所生成本地人群

`/world` 的“区域与社区人群模型”先设置国家、城市、社区/服务范围和场所类型，再生成 4–20 类本地角色并分配到代表性 Agent。支持车站、商超、购物中心、机场、街道公共空间、办公园区及自定义场所。新界面不允许直接把通用画像当成某地居民；旧运行仍可回放。

地区和社区资料可粘贴摘录，也可从当前规划项目载入已上传资料；每份资料记录标题、链接、国家、城市和可选社区范围。仅处理适用来源，其他城市、其他指定社区、未标明适用国家/城市的资料会排除并显示原因。链接只作引用，不自动抓取；资料内容、统计时点与适用范围仍需用户核对。城市级资料不会自动成为指定社区的调查结论。测试库存原始地址、城市和 POI 全部保留，界面提示字段可能存在市场范围或地点冲突，不据此自动确定社区。

画像新增社区关系、到访目的、语言环境、文化关联、社区生活联系、场所观看机会、本地化依据与来源 ID。国家名称本身不能推出个人民族、宗教、语言、收入或偏好；缺少文化/社区证据时标记假设和资料缺口。消费能力、家庭构成、相对人数和活动系数都按合成情景处理，不冒充人口统计。

本地群体的五类时段 `activity_factors` 由场所任务和资料辅助推演，允许在群体编辑器中调整；这些参数实际参与 24 小时出场排程，不再依赖旧版固定群体 ID。每次 OASIS 决策传入地区、社区、场所、适用资料摘录、该代表的本地角色与引用。示意屏幕分区随场所变化（如候车区域、商超收银区域、机场到达通道），没有现场证据时可见性保留未知。库存模式只选择与当前国家、城市、场所匹配的候选屏幕。

生成结果保存在 `backend/uploads/audience_templates/<id>.json`。模板绑定完整地区输入及资料的 SHA-256；改变国家、城市、社区、场所或资料后，服务端拒绝复用旧模板，UI 提示重新生成。手工修改群体会作为当前运行配置保存，已有运行不会被改写。API 为 `POST /api/world/local-audiences`、`POST /api/world/location-inventory` 与 `GET /api/world/locality-options`；预览/运行携带 `locality` 与 `template_id`，每次由服务端校验绑定和引用。

本地化验证使用测试库存中出现的 Emeryville 城市名称，并另行参考 [市政府交通资料](https://www.emeryville.org/Services/Getting-Around-Emeryville/Public-Transit) 与 [公共艺术资料](https://www.emeryville.org/Recreation/Public-Art)。具体候车区域与商超都是合成场所，不把库存中未经核对的地址当成真实社区位置。两份来源为城市级资料，模型与 UI 明示缺少指定社区调查，未据此认定语言、收入或家庭结构。

- [验证输入与来源摘要](../output/oasis-locality/locality-input.json)
- [真实 LLM 车站人群模板](../output/oasis-locality/station-template.json)
- [同地区商超人群模板](../output/oasis-locality/supermarket-template.json)
- [两类场所的角色、任务与活动系数对比](../output/oasis-locality/venue-comparison.json)
- [本地画像模拟 UI](../output/oasis-locality/local-audience-ui.png)
- [本地化全天回放](../output/oasis-locality/locality-replay.json)
- [原生 OASIS、地区上下文与权重核验](../output/oasis-locality/verification.json)
- [区域绑定与浏览器验收](../output/oasis-locality/ui-verification.json)

该本地化全天运行包含 100 个代表、30,000 人情景规模、24 小时，原生数据库有 950 次 INTERVIEW 和 100 次 sign_up，另有 1,450 条未出场排程。每条原生决策的地区、社区、场所、本地画像与来源上下文均已核对，未发现无效输出。社区/场所变更后旧模板阻断、资料排除、活动参数编辑、循环回放和移动端均已通过浏览器验收。

### 24 小时时间轴、节日与循环回放

每个模拟日按 00:00–23:00 生成 24 个小时快照，支持 1–3 天、可选起始日期。默认上班高峰 07:00–10:00，下班高峰 17:00–19:00，夜间消费 19:00–23:00；区间左闭右开，允许跨午夜，三种重点时段不能重叠。界面按时段着色，浅柱表示排程人数，亮线表示已有记录的加权注意人数；未推演小时使用斜纹，不能当成模型结果。

节日提供圣诞节、元旦/跨年、春节、国庆假期、黑色星期五与自定义活动。可修改名称、描述、每日生效小时、通勤活动系数和休闲消费系数。节日由用户选择，不根据日期自动判断法定假日；多日模拟按所选有效小时重复该活动。预设系数只是合成假设，不是当地消费数据。

排程出场概率为 `min(0.98, 时段基准 × 节日活动系数 × 群体活动系数)`，固定场景种子可复现。基准为上班 0.72、下班 0.80、夜间 0.62、日间 0.35、深夜/清晨 0.05；通勤类在上下班系数为 1.2，其他群体早间为 0.7，家庭照护/退休等夜间系数为 0.75，其余为 1。新本地模板使用各群体的 `activity_factors` 覆盖这套旧版群体系数。这些可审计的默认假设不依收入、总人数或真实个人身份推断。每小时保留全部代表和原始人数权重，未出场为 `away`，既不是 `passing`，也不进入平均观看时长的分母。`presence`、`slot`、`encounter` 与行为记录一起导出。节日与时段同时作为 LLM 决策上下文，不能仅靠人口系数冒充节日下的模型反应。

默认开启循环回放，完成全天推演后自动播放；新版街区回放先展示上班高峰，经过 23:00 后返回 00:00；多天则完成最后一天后返回第一天。支持暂停、1×/2×/4×速度、点击小时定位、关闭循环及跟随最新记录。循环与预览不启动新运行、不调用 LLM；尚在生成的回放到达最新记录会等待，不提前伪造余下小时。旧运行记录保留原轮次含义，新增界面默认使用全天模式。

### OASIS 环境

OASIS 在独立子进程中运行，避免旧图谱依赖阻塞规划后端。默认解释器为 `backend/.venv-oasis/bin/python`，其他位置可设置 `OASIS_PYTHON`。

```bash
python3 -m venv backend/.venv-oasis
backend/.venv-oasis/bin/python -m pip install -r backend/requirements-world.txt
python3 backend/run.py
# 另一个终端
npm run frontend
```

当前机器已修复 OASIS 的 NumPy/SciPy 与 ARM64 pandas/igraph 依赖，并在独立环境中验证运行；worker 禁用不需要的 TensorFlow 集成，推荐系统使用 random 模式，避免下载无关的社交文本嵌入模型。

运行保存在 `backend/uploads/worlds/<run_id>/`：`state.json` 为 UI 轮次回放，`oasis.db` 为 OASIS 原生数据库，`control.json` 为轮次控制，`worker.log` 为本地排错记录。服务端不把 API 密钥写入公开回放。

当前全天验证：**100 个代表性 Agent、30,000 人情景规模、12 类人群、圣诞节 24 小时**。原生 OASIS 数据库包含 100 次 sign_up、1,057 次 INTERVIEW；另有 1,343 条明确标注来源的未出场排程事件，共 2,400 个逐小时 Agent 状态和 25 个快照（含初始帧）。已逐条核对原生 prompt 的小时、节日上下文及决策，核对每小时人数权重、出场人数、汇总与视线约束，没有无效模型输出。

- [夜间消费场景截图](../output/oasis-day-cycle/oasis-day-night.png)
- [上班高峰与节日配置截图](../output/oasis-day-cycle/oasis-day-morning.png)
- [完整全天回放记录](../output/oasis-day-cycle/oasis-day-replay.json)
- [原生数据库与时间上下文核验](../output/oasis-day-cycle/verification.json)
- [循环回放浏览器验收](../output/oasis-day-cycle/ui-verification.json)
- [此前两轮人群规模验证](../output/oasis-population/verification.json)

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_audience_world.py backend/tests/test_audience_cohorts.py backend/tests/test_day_cycle.py backend/tests/test_local_audiences.py -q
node --test frontend/src/utils/worldPlayback.test.js
# 核对某次真实运行，输出可审计统计（run_id 替换为实际运行 ID）
PYTHONPATH=backend python3 backend/scripts/verify_audience_world.py backend/uploads/worlds/<run_id>
```

### 周边街区步行与出场（schema 5）

`/world` 新运行使用连通的街区步行网络，覆盖住宅、办公、沿街店铺、公园、餐饮、社区服务、目标场所、公共交通接续点和四个外围步行出口。行人先按任务生成出行，再检查路线与屏幕的距离；不再给每个出场的人轮流分配屏幕、围绕屏幕摆放位置。路线只能沿图中的人行通道和指定过街连接移动，不穿过建筑。背景是合成空间，并未匹配实际 GIS 或机场等场所的真实平面与管制区域。

每个小时为排程代表生成一次有起止分钟的出行情景，包括穿行、办事、顺路多点浏览、停留、过街等候、步行离开，以及下车步行/步行接续交通。出行由本地画像的到访目的、时段、固定种子和情景参数生成，不按收入或国籍推断移动行为。UI 可调整全程步行抽样概率（默认 0.75）和顺路浏览概率（默认 0.40）；明确的普通步行穿行画像保持步行，因此最终比例不保证等于输入概率。未来生成的本地模板提示词也包含周边普通路人、不进场所者与步行离开者。

步速假设为 0.8–1.6 m/s、比例尺 0.6 m/图单位、过街等候 4–20 秒、任务停留 1–6 分钟。过长的多点行程会减少可选停留点，使一次出行在该小时内结束，保留 `curtailed_optional_stops` 标记；每个小时的行程是代表画像的抽样出行，不是跨小时连续跟踪的真实个人日记。模型尚未校准步行占比、路网、距离或人数，也未实现行人避碰、车辆运行与真实信号灯调度。

只有路线进入屏幕 65 图单位的情景半径时，才调用原生 OASIS `INTERVIEW`，传入起终点、途中任务、最近距离与相遇分钟。当前每次出行仅分析沿途首块近邻屏幕，其余机会留在 `screen_opportunities` 中，不宣称已计算多屏曝光。视向与遮挡仍是标明来源的抽样假设。OASIS 给出停留观看时，其返回秒数会插入路线成为实际回放停顿；其余步行速度保持不变。空间路径由项目的规则适配层生成，观看决策来自 OASIS，不能把两者统称为实测物理仿真。

`away` 表示该小时没有出行，`unexposed` 表示在周边活动但路线没有进入任何屏幕的情景半径，`passing` 才表示进入相遇条件后未注意。前两类不调用 LLM；`unexposed` 保留出行人数但不进入平均观看时长分母，事件来源标为 `spatial_route`。每个小时仍保留全部代表和原人数权重。地图顶部的“此刻在场”按当前分钟计算，“本小时出行/离开”是该小时的代表行程次数，不是实时人流或去重人数。

新版回放每小时默认压缩为 12 秒，支持 1×/2×/4×、分钟拖动、小时定位、路线显示和全天循环。人员到入场分钟才出现，到离场分钟后消失，不通过跨小时直线动画跳到另一块屏幕。完成的新运行打开时从上班高峰进入展示，循环仍覆盖 00–23 点。旧记录保持原画面与旧回放速度。

相关文件：`backend/app/audience/mobility.py`、`frontend/src/components/NeighborhoodMap.vue`、`frontend/src/utils/neighborhoodPlayback.js`。导出 JSON 保存路网、每小时原始路线、观看停留修正、出行汇总以及原生决策引用。

验证命令：

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_neighborhood_mobility.py backend/tests/test_audience_world.py backend/tests/test_day_cycle.py backend/tests/test_audience_cohorts.py backend/tests/test_local_audiences.py backend/tests/test_audience_simulation.py backend/tests/test_screen_planning.py -q
node --test frontend/src/utils/worldPlayback.test.js frontend/src/utils/neighborhoodPlayback.test.js
```

本次实际运行 `1158c4a3c659478d89b7892c94dd9c0d` 使用现有 Emeryville 合成场所本地模板，100 个代表、30,000 人情景权重，24 小时共 950 段代表出行。708 段全程步行；按离开方式统计，833 段步行离开、117 段交通接续（包含先下车后步行离开的行程，因此与全程步行数不同）；372 段顺路多点浏览，73 段未接近屏幕。全部 28 个路网节点均被访问。以上是逐小时行程次数，不能累加解释为人数。

原生 OASIS 数据库有 100 次 sign_up、877 次 INTERVIEW，另有 73 条空间路线记录、1,450 条未出场排程。877 条模型输出全部有效，20 次观看停留已插入连续路线。逐条核对了原生 prompt、回应、地区上下文、原始路线、观看停顿、权重与小时汇总。后端 106 项测试、前端 5 项回放测试、生产构建及桌面/手机浏览器验收通过。

- [街区步行界面](../output/oasis-neighborhood/neighborhood-ui.png)
- [全街区路线图](../output/oasis-neighborhood/neighborhood-routes.png)
- [未接近屏幕的普通步行者](../output/oasis-neighborhood/neighborhood-pedestrian.png)
- [手机界面](../output/oasis-neighborhood/neighborhood-mobile.png)
- [完整可回放 JSON](../output/oasis-neighborhood/neighborhood-replay.json)
- [原生 OASIS 逐条核验](../output/oasis-neighborhood/verification.json)
- [步行与街区覆盖统计](../output/oasis-neighborhood/mobility-verification.json)
- [浏览器验收结果](../output/oasis-neighborhood/ui-verification.json)

### 车辆、更多步行样本与动态 Impressions

街区视图加入双向通行的轿车、出租车、公交车及厢式车，车辆在道路上连续移动；车色、长度与外观随类型变化。默认基准车流为 180 辆/小时，UI 可设为 0–600。深夜、上班、下班、夜间、日间分别使用 0.18、1.5、1.6、1.2、1.0 的情景系数，并结合节日活动系数，最多 1,800 辆/小时。车辆按车道错峰入场，同车道使用一致的 24–36 km/h 抽样速度。载客人数含驾驶员：轿车 1–4、出租车 1–3、公交 8–30、厢式车 1–2，均是假设值。没有车辆驾驶/乘客观看的额外 LLM 决策，也未建模交叉口信号、车辆避碰或公交上下客。

“每个代表展开行人”支持 1、2、4、6、8、10。默认 100 个 OASIS 代表对应最多 400 个步行样本，可调到 1,000；代表上限 200 时最多 2,000 个样本。展开样本具有独立的规则生成路线、步速、停留和进入时间，并用背包、提袋、手机、公文包等六种外观增加区分。它们继承原地区与社区画像，**按整数分摊原代表人数权重**，不会凭显示密度增加总人口或 OASIS 独立样本数。原代表的观看记录仍可在观察窗查看，展开样本不被冒称为额外的模型决策。

在原有三块屏幕之外，增加两块沿街演示广告牌，注明示例创意和合成来源；它们不属于上传库存或预算推荐。五块牌在地图和统计卡显示动态累计 `模拟 Impressions · 曝光机会`，并拆分行人权重、车内假设人数。

计数规则：代码计算路线与广告牌的最近经过点；进入该牌的合成半径时，每趟行程 × 每块牌最多生成一个事件。原屏幕默认半径为 65 图单位，新增道路广告牌为 105 图单位。行人事件计其分配权重，车辆事件计假设载客人数。统计覆盖沿途各牌，**不表示看见、注意、实际广告播放或去重触达**，也不等于原有 OASIS 注意人数；跨屏、跨小时可重复计次。步行和车辆人群是独立情景样本，不能合并声称为去重人数。

计数按当前回放时刻从事件前缀求和，不在动画刷新时递增。暂停不增加，快进不漏计，倒退会减回对应时刻，全天循环会从零重新播放，不重复追加上一遍事件。带车辆的回放 1× 为 30 秒/模拟小时，提供 0.25×、0.5×、1×、2×、4×、8×、16×、32× 八档。人车设置可直接应用到已完成运行，不需要重新调用 OASIS。

API：`POST /api/world/runs/<rid>/traffic` 接收 `traffic_options` 并为既有运行生成派生回放；`POST /api/world/traffic-preview` 使用预览配置，不调用 LLM。派生结果按运行轮次和参数单独缓存为 `traffic-<hash>.json`，不修改原 `state.json` 或 `oasis.db`。导出的完整 JSON 带 `traffic_replay`，保存所有样本、车辆、广告牌、经过事件、公式、假设与来源运行 ID。

本次以已验证的 100 代表、30,000 人、24 小时运行 `1158c4a3c659478d89b7892c94dd9c0d` 为来源，在原生记录上生成并实际回放交通情景。默认 4 倍展开、180 辆基准车流得到 3,800 段步行样本行程、3,914 段车辆行程、19,314 个过牌事件。已逐小时核对人数权重，逐条重算过牌时刻、牌 ID 和计数；浏览器验证播放增量、暂停、倒退、循环、密度变更、关闭/恢复车辆、八档速度、导出与手机布局。没有改写原生 OASIS 记录。

- [车辆、广告牌及动态计数 UI](../output/oasis-traffic/traffic-ui.png)
- [完整桌面界面](../output/oasis-traffic/traffic-desktop.png)
- [手机界面](../output/oasis-traffic/traffic-mobile.png)
- [交通派生回放](../output/oasis-traffic/traffic-replay.json)
- [原生记录与交通一起导出](../output/oasis-traffic/world-with-traffic.json)
- [经过事件与权重核验](../output/oasis-traffic/verification.json)
- [动态播放浏览器验收](../output/oasis-traffic/ui-verification.json)

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_traffic.py -q
node --test frontend/src/utils/trafficPlayback.test.js
PYTHONPATH=backend python3 backend/scripts/verify_traffic_replay.py output/oasis-traffic/traffic-replay.json backend/uploads/worlds/1158c4a3c659478d89b7892c94dd9c0d/state.json
```

本次回归结果：119 项后端测试、8 项前端回放测试通过；生产构建通过。现有的构建分包体积提示仍存在。

### FilteredFrames.GEOM → Mapricot 区域地图 → 本地人群与 OASIS

`/world` 先显示全库存区域地图，再显示单屏局部模拟。读取 `data/test.xlsx` 或上传工作簿时，严格使用 **FilteredFrames**；GEOM 按经度、纬度解析并保留全部原字段、媒体市场、地址与原 POI。支持 WKT POINT/Z/SRID=4326、GeoJSON Point；缺失 GEOM 才回退独立经纬度，无效 GEOM 不悄悄换坐标。重复位置合并查询，但每条 Frame 保留独立 key、屏幕 ID 与关联。

本次使用用户指定并授权的 Mapricot。服务端官方 Python 客户端 `Mapricot(...).geocoding.reverse(...)` 与 `client.places.nearby(lat, lon, radius=600, limit=20)` 逐坐标查询，三个并发，成功证据缓存 7 天。没有 Nominatim / Overpass 回退。Mapricot 仅接收坐标、半径与查询参数；完整工作簿与预算不发送给地图商。SDK 在缺少系统 CA 的 macOS Python 环境使用 certifi 证书链，仍然验证 TLS。

```dotenv
LOCATION_PROVIDER=mapricot
MAPRICOT_API_KEY=your-server-key
LOCATION_LOOKUP_ENABLED=true
```

密钥只放在被 Git 忽略的本地 `.env`。前端通过后端获取样式及 TileJSON；后端移除样式中携带的密钥并重写数据源地址。公共瓦片、字体、图标来自 Mapricot 官方域名。没有接受任意 URL 的代理。保留 Mapricot、OpenStreetMap 及 POI 返回的 OpenAddresses / Overture / GeoNames 等署名。[官方 API 文档](https://mapricot.com/docs/api-reference/)与[地图文档](https://mapricot.com/docs/map-tiles/)。

地图使用 MapLibre，支持整个库存的屏幕点、缩放浏览街道/建筑、所选屏幕附近设施、前五个 POI 的直线关联，以及建筑视角。立体高度仅使用瓦片提供的高度字段，缺失时保持平面。选择重叠位置的不同 Frame 可用下拉框或逐屏关联表。可切换空间分区，分别查看周边设施和人群推演；屏幕原 POI 始终保留为未确认线索，不冒称已验证原始名称。

每坐标最多返回最近 20 个设施，因此不是完整 POI 普查。距离由代码使用坐标重算；距离不代表入口距离、人行可达或屏幕朝向。反查仅到行政区域时明确返回粒度，不把城市中心当屏幕地址。约 2 km 空间索引分区按坐标与反查城市组织，**不是行政社区边界**；周边底图可继续向外浏览。

大模型按分区分析设施支持的生活任务、路人/非消费者/工作人员/访客、移动方式、消费需求假设及早高峰/日间/晚高峰/夜间的差异。每个角色必须引用该分区提供的真实设施或地址来源；请求中使用短引用别名，服务端校验并还原 Mapricot ID，防止长 ID 抄写错误及跨区域引用。分批生成并保存进度。没有社区调研时明确缺口；不得由地点推断真实人口占比、收入、家庭、文化或宗教。

单屏“核实坐标并用大模型分析”会读取选中坐标附近的地图瓦片（仅当前视野，不批量离线下载），解码道路/建筑几何，并把已完成的上级分区推演送入该屏幕的环境分析。应用时保留地图事实、局部模型推演、上级分区推演三类来源，按所需数量生成人群模板，再分配代表 Agent 与人数权重。`geolocation_id` 绑定服务端记录，浏览器不能注入路网；改变地区或地图证据会阻止复用。库存内容变化也会改变区域记录指纹。

局部模拟使用所选 Frame 的实际位置，不额外添加合成广告牌。Mapricot 瓦片道路在同层交点连接，桥梁/隧道分别处理，保留附近连通组件；道路中心线、人行入口和通行权限不完整时明确属于制图代理假设，**不能用于导航，也不是实测人行道**。车辆沿地图道路片段移动。人群、速度、停留、车辆载客、观看半径和 Impressions 仍是情景参数；地图查证不会把曝光机会变成实测观看量。

API：

- `POST /api/world/geo-inventory`：本地读取 FilteredFrames。
- `GET /api/world/location-config`：不含密钥的功能状态。
- `GET /api/world/mapricot/style`、`tilejson`：经清理的地图配置。
- `POST /api/world/regions`：启动全库存查询；返回任务 ID。
- `GET /api/world/regions/<id>`：地图、逐屏关联、分区与进度。
- `GET /api/world/regions/latest/<inventory_id>`：恢复与当前库存完全匹配的最近任务。
- `POST /api/world/regions/<id>/analyze`：异步区域人群推演。
- `POST /api/world/locate-frame`：输入 inventory_id、frame_key、radius_m、可选 region_id，建立局部场景。

真实查证结果：`data/test.xlsx` 的 144 条记录全部成功；109 个不同坐标；140 条反查为 San Francisco、4 条为 South San Francisco；2,016 个去重返回设施；13 个空间分区，模型完成 69 个带来源引用的区域角色假设。这些设施数量不是人口/客流，69 个角色也不是人群占比。第一块屏幕实际落在 Gough Street 附近，库存城市 `Sacramento et al` 的冲突在 UI 明示。此前离线测试与未授权公共地图的阻断记录仅为历史验证，不代表当前 Mapricot 结果。

产物：

- [实际区域总图](../output/mapricot-region/region-overview.png)
- [实际屏幕、道路与周边设施](../output/mapricot-region/screen-streets-pois.png)
- [手机地图](../output/mapricot-region/regional-mobile.png)
- [区域证据与逐屏关联](../output/mapricot-region/region-evidence.json)
- [单屏地图与区域上下文](../output/mapricot-region/selected-frame-context.json)
- [本地人群模板](../output/mapricot-region/audience-template.json)

验证包括坐标去重但保留屏幕、距离/坏坐标过滤、缓存、停用查询、无未授权提供方回退、浏览器密钥清理、来源范围验证、空 POI/失败状态、瓦片坐标转换及桥梁分层连接；另做真实接口与桌面/手机浏览器验收。运行命令：

```bash
PYTHONPATH=backend python3 -m pytest backend/tests/test_audience* backend/tests/test_day_cycle.py backend/tests/test_geolocation.py backend/tests/test_local_audiences.py backend/tests/test_neighborhood_mobility.py backend/tests/test_screen_planning.py backend/tests/test_traffic.py backend/tests/test_mapricot.py -q
node --test frontend/src/utils/*Playback.test.js
npm --prefix frontend run build
```

旧社交/Zep 测试在当前系统 Python 上存在既有 `zep_cloud.BatchAddItem` 依赖版本导入问题，不能声称全仓库测试通过；上述独立规划、地图及人群模拟回归不依赖该旧模块。

本次真实 OASIS 完整运行 ID：`fe81e042a09f4599a958e02ab69fce15`。首块 Gough Street 屏幕使用 12 类本地画像、100 个代表 Agent、30,000 人情景权重，运行 24 小时。942 段代表出行中 540 段形成屏幕相遇并调用原生 OASIS INTERVIEW；402 段在周边活动但未进入屏幕半径，1,458 条为该小时未出场排程。540 条原生模型回复均有效，已逐条核验 SQLite trace、提示中的区域来源、小时配置、回放与权重。

默认四倍行人展开及 180 辆/基准小时得到 3,768 段步行样本行程、3,914 段车辆行程、2,409 个过牌事件。代码重算得到全天 165,596 次加权模拟曝光机会（164,550 行人权重计次 + 1,046 车内假设人数计次），不是实际观看或去重触达。真实地点模式只计算选中的一块库存屏幕，区域总图上的其余 143 块未被冒称为已运行观看决策。较大路网使用边索引替代逐步全表扫描，默认派生回放实测约 3.8 秒生成。

- [真实地点 OASIS 人车回放截图](../output/mapricot-region/oasis-real-map-simulation.png)
- [区域人群分析界面](../output/mapricot-region/regional-audience-analysis.png)
- [另一城市分区](../output/mapricot-region/south-san-francisco.png)
- [原生决策核验](../output/mapricot-region/native-verification.json)
- [交通与过牌事件核验](../output/mapricot-region/traffic-verification.json)
- [完整模拟及派生回放 JSON](../output/mapricot-region/world-replay.json)
- [实际浏览器验收](../output/mapricot-region/ui-verification.json)

相关后端回归 146 项、前端回放 8 项、生产构建通过；路网索引优化后出行/交通 23 项再次通过。生产构建仍提示较大 JS 分包（MapLibre 已动态导入）。页面使用地图加载状态避免把尚未取得瓦片的灰色背景当作完成。

### 四宫格：不同地点的独立场景对比

`/world` 新增「单场景 / 四宫格」切换，首次进入默认四宫格。每格从场景库选择地点，默认按坐标挑选不同地点，不复制一个场景凑满四格；不足时保留空位。选择会保存在浏览器本地，可单独放大再返回四格、查看轨迹及人物画像摘要。桌面为 2×2，手机按单列排列。

四格共用模拟天数/小时/分钟时间轴，支持暂停、拖动、0.5×–32×、全天循环；关闭同步后每格可分别选择小时、分钟及播放状态。切小时会等待当前数据就绪，不把上一小时的人群显示在新时段。日期按原运行显示，相同相对小时不代表同一个日历日期。每格曝光使用该场景自身事件的累计前缀计算；不添加全场景人数或曝光总和，不声称去重覆盖。全部地点仍为地图几何上的情景推演。

「从库存添加场景」支持当前规划工作簿、默认 test.xlsx 或上传新的 XLSX，严格读取 FilteredFrames。添加流程复用坐标查证、区域背景、当地画像和全天人车路径生成；新场景明确标注为「地图人群预览 · 未运行 OASIS 决策」。已完成的原生运行可以导入，标注为「OASIS 已完成回放」，原始 state.json 和 oasis.db 均不修改。

新增 `backend/app/audience/comparison.py` 和 `/api/world/comparison-scenes` 接口：

- `GET /comparison-scenes`：轻量场景目录。
- `POST /comparison-scenes/import`，`{run_id}`：幂等导入已完成 OASIS 记录，拒绝未完成运行。
- `POST /comparison-scenes/preview`：已有服务端查证记录和画像模板的预览配置，不接受浏览器注入路网。
- `GET /comparison-scenes/<id>`：静态几何、场景来源、群体、逐屏计数事件。
- `GET /comparison-scenes/<id>/hours/<round>`：按小时获取行人和车辆；超出该场景时段返回错误，不复制其他小时。

数据保存在 `backend/uploads/scene_library/`。场景包先写入临时目录再整体发布，避免读取半成品。四格按需读取当前小时，各格只缓存三个小时；切场景取消旧请求并核验请求序号，避免慢响应覆盖新选择。静态道路/建筑绘制使用 Vue memo，各 SVG 使用独立 pattern ID，避免多图 ID 冲突。

相关验证：`backend/tests/test_comparison.py` 覆盖逐小时独立数据、不可变原记录、导入幂等、来源标记、无效 ID 与越界小时；`frontend/src/utils/comparisonPlayback.test.js` 覆盖不同地点默认选择和小时/全天循环。真实四地点验收产物见 `output/oasis-four-scenes/`。

四地点实际运行已完成（每格 100 个代表、30,000 人情景权重、24 小时；互不合并人数）：

- `filtered-1`：San Francisco · Gough Street 周边 400 米（情景范围） · GEOM 定位；原生运行 `fe81e042a09f4599a958e02ab69fce15`，540 条经 SQLite 核验的观看决策，无效回复 0。
- `filtered-2`：San Francisco · Stockton Street 周边 400 米（情景范围） · GEOM 定位；原生运行 `f66c4b564d124472993b9698d3947de5`，885 条经 SQLite 核验的观看决策，无效回复 0。
- `filtered-3`：San Francisco · King Street 周边 400 米（情景范围） · GEOM 定位；原生运行 `4bcc47b9658f4740a1019b17c507af4a`，811 条经 SQLite 核验的观看决策，无效回复 0。
- `filtered-4`：San Francisco · Market Street 周边 400 米（情景范围） · GEOM 定位；原生运行 `4b2ac1caaf204aec8ac09ebecddb4f46`，781 条经 SQLite 核验的观看决策，无效回复 0。

关联产物：[四格运行与来源](../output/oasis-four-scenes/verified-scenes.json)、[四宫格实际界面](../output/oasis-four-scenes/four-scenes-desktop.png)、[单格放大](../output/oasis-four-scenes/focused-scene.png)、[手机布局](../output/oasis-four-scenes/four-scenes-mobile.png)、[浏览器验收记录](../output/oasis-four-scenes/ui-verification.json)。四份原始运行分别保留在 `backend/uploads/worlds/`，未合并、未覆盖。

本次相关后端回归 152 项、前端回放 10 项及生产构建通过。额外修复了多地点生成中长地图 ID 的模型引用问题：使用短别名并映射回真实 ID；画像数量不符时最多向模型请求一次修正，仍不符则拒绝，不通过复制角色凑数。四宫格运行状态改为轻量轮询，切回单场景时才恢复完整记录。可用 `/world?layout=quad` 直接进入四宫格。

模拟工作台现采用浅色背景、黑色正文和浅灰细边框，四宫格、单场景及配置面板保持一致。四格地图取消原有最高 300px 的限制，按列宽和原始地图比例展开（1800px 宽桌面下约 451px 高）；压缩辅助文字及间距，累计数字仍为 24px，地图内广告牌数字样式和计数逻辑保留。手机仍使用单列布局。浅色界面验收见 [实际截图](../output/oasis-four-scenes/light-theme-desktop.png) 与 [布局记录](../output/oasis-four-scenes/light-theme-verification.json)。

### 广告内容、当地态度与更密集车流

四宫格新增广告面板：Nike Running、Nike Football 或自定义品牌、标题、文案、主题和公开 HTTPS 资料入口。界面区分正在编辑的草稿与已应用广告；广告按全天循环播放的情景处理。点击「检索资料并应用到所选场景」启动后台任务，完成后同时应用到参与分析的各格；新选地点没有对应分析时保留原始回放。可以「仅应用车流」复用已完成的广告研究与个人评分，避免重复模型请求。

`campaign_research.py` 实际读取资料页，让 LLM 从已检索标题中选取文章，再抓取网页并引用分析。默认 Nike 入口是官方 Newsroom；旧金山演示另取 Nike 历史社区跑活动、SFMTA 街区资料、Hayes Valley 社区协会资料。记录来源链接、发布日期、读取日期、资料适用范围、官方宣称与资料缺口；未知日期不以读取日期替代，结束活动不当作当前日程，新品未来上市不说成已经销售。该检索是来源限定的网页研究，不是全网搜索或当地品牌偏好民调；其他城市不会继承旧金山资料。

`campaign.py` 按原场景的每个代表画像、个人任务和适用资料调用 LLM，生成好感度、兴趣、低/中置信度、原因和来源。每批校验 Agent ID 覆盖、唯一性、评分范围、null 与引用。模型态度是叠加在原 OASIS 行程上的独立分析，不伪称原运行已看过新广告。原运行与场景库保留，每次实验另存 `backend/uploads/campaign_experiments/<id>/`，当前小时独立加载。

数字继续累计几何曝光机会；颜色根据已经过屏幕的**有评分行人曝光权重**计算 `Σ(评分×曝光权重)/Σ(有评分曝光权重)`，在红→琥珀→绿之间连续变化。灰色表示未知。车辆乘员没有画像，故计入曝光但不进入态度分母；0 分不同于未知。切换兴趣/好感仅改变颜色，不改变曝光数量。点击行人可看个人理由，点击广告牌可看群体汇总；群体表为全部画像加权，地图颜色为截至回放时刻经过者加权。倒放、暂停与循环重新按事件索引求值，不额外累加。

车流改用共享坐标与地图层级连接的单向道路行程；限制私人/禁行道路，并在有官方资料的旧金山 Market Street 范围内排除普通私家车。几何细分点不当作信号灯，保留路口并简化共线点。高峰速度较低，路口等候为显式情景假设。默认广告演示基准为区域合计 1,800 辆/小时（可设 0–3,000），早晚高峰 1.5–1.6 倍，夜间活动 1.2 倍、深夜 0.18 倍，并保留节日系数；这些不是现场实测流量，尚未模拟真实车道、信号时制、避碰、营运许可或上下客区。

已完成四个实际地点各 100 名代表的 LLM 广告评分（共 400 个），结合 7 个实际网页来源。在 08:23.3，同屏可见车辆从 Gough/Stockton/King/Market 的 4/3/2/3 辆提高至 64/78/52/39 辆；本小时各 2,700 段模拟车行。当前完成实验 `50c80c66a5b4478bb7eb736f3c618405` 可用 `/world?layout=quad&campaign=50c80c66a5b4478bb7eb736f3c618405` 打开。原始评分实验 `f26a130a8aa842339b10c0e55f5b58b2` 保留；最终实验复用其评分并更新道路车流。

相关后端回归 **166 项**、前端回放 **12 项**及生产构建通过。浏览器已验证四格评分与源事件一致、指标切换不改变数量、个人解释、草稿不覆盖当前广告、来源链接与手机无横向溢出。产物：[四格广告界面](../output/campaign-simulation/campaign-desktop.png)、[放大场景](../output/campaign-simulation/campaign-map-focused.png)、[个人态度](../output/campaign-simulation/agent-attitude.png)、[来源界面](../output/campaign-simulation/research-evidence.png)、[数据校验](../output/campaign-simulation/data-verification.json)、[浏览器校验](../output/campaign-simulation/ui-verification.json)。

### 群体想法与个人模拟评论

四宫格每格新增「他们会怎样想，又会怎样说？」文字面板，点击「阅读文字」可切换群体，阅读身份/偏好/消费能力分析、组内差异与购买阻力，并查看具体代表的内心想法、可能评论、预算判断和条件性行动。地图上点击行人会展开对应个人文字；下拉框也可查看当前小时不在场的代表。原有浅色布局、大地图、曝光数字和渐变评分保留。

`campaign_narratives.py` 使用当前广告的已检索资料、地点适用来源、原始合成人物画像和已保存数值评分生成文本。输出校验人物/群体 ID 完整唯一、实际画像字段引用、来源适用范围及各段完整性；模型不能覆盖姓名、画像或分数。好感、兴趣、预算可承受性与购买意愿分开，未知售价/收入/购买经历不作为事实。全部评论均为模型模拟，不能当成真实消费者评价或当地市场民调；地方资料提供情境，不意味着同一地区人群态度一致。

文字保存于 `backend/uploads/campaign_experiments/<id>/narratives/v1/`，不修改原 OASIS 运行、广告分数或曝光事件。每批人物保存检查点；重试可恢复，画像、证据、评分、模型或提示词变化会改变缓存指纹。新广告实验评分完成后自动生成文本；已有实验可在面板点击生成。阅读、切换人物、回放和下载不调用模型。仅调整车流时，可复用与输入指纹一致的已有文字。

接口（前缀 `/api/world/campaign-experiments/<id>/narratives`）：GET 查询状态；POST 开始/继续生成；GET `/scenes/<sid>` 读取完整文字；GET `/report.txt` 下载全部地点、群体、个人想法及来源的 UTF-8 文本。生成未完整完成时不发布部分文字，也不影响已完成的地图回放。相关测试见 `backend/tests/test_campaign_narratives.py`。

本次已通过配置的 DeepSeek API 完成现有 Nike 实验四地点的 **48 份群体分析、400 份个人文字（每人五部分）**。逐一核对姓名、所属群体、画像及评分与原记录一致，来源限定在适用地区。相关后端 **22 项**、前端回放 **7 项**和生产构建通过；真实浏览器验证群体/人物切换、点击地图打开对应个人、阅读不改变曝光数、手机无横向溢出及下载。产物：[全部文字](../output/campaign-narratives/audience-ad-comments.txt)、[群体和人物界面](../output/campaign-narratives/group-and-person.png)、[手机界面](../output/campaign-narratives/narratives-mobile.png)、[数据校验](../output/campaign-narratives/data-verification.json)、[浏览器校验](../output/campaign-narratives/ui-verification.json)。

### 长篇需求分析与投放决策版（v2）

文字升级为独立的 `narratives/v2/` 结果，旧版 `v1` 保留。每个代表人物生成七部分：身份与需求分析、预算权衡、连续的内心想法、较完整的可能评论、行动触发条件、投放启示及待核实信息；七部分合计至少 600 字，目标约 800–1100 字。每个群体增加需求优先级、创意与信息安排、场所/时段试投方案、验证计划，七部分合计至少 900 字，目标约 1200–1600 字。长度下限是完整性约束，不能替代内容质量或真实研究。

群体分析除两个不同兴趣的代表文本，还接收组内全部成员画像，以及代码从原场景行人事件汇总的逐时段加权经过机会。车辆和未知人物不进入此依据；经过机会可重复，不是实测人流或实际观看。界面提供时段依据表，供检查模型的试投建议。没有实测基线、真实价格、成本和库存时，不据此虚报最优预算、SOT、转化率或效果提升。

当前广告标题/文案明确作为用户或系统设定的模拟创意，产品资料中的官方事实另行引用；不能把产品新闻当作本广告的官方出处。文字要求区分画像假设、资料事实、模型推测与待验证建议。新建议关注短文案与信息层级、安全停留后的信息入口、对照试投、需保持一致的条件、观看/理解/查询/购买的指标区别及继续、调整或暂停的证据。

「供决策者使用」区域集中展示创意、场所时段与验证安排；个人文字补充「对投放决策的启示」和「依据、不确定性与待核实信息」。下载支持全部人物全文，以及 `GET .../narratives/report.txt?scope=groups` 的群体决策摘要；后一种只导出群体分析、时段依据和来源，不夹带 400 份个人长文。页面保持浅色黑字及地图人物联动。

v2 已实际完成四地点、400 位代表和 48 组分析。按七部分正文字符数核对，个人平均 **951**（范围 616–1381），群体平均 **1408**（范围 967–1921）；个人内心想法平均 **114**，旧版为 **23**。原有姓名、画像和数值评分逐一保持一致；逐小时群体依据已按原始行人事件独立复算。最终相关后端 **28 项**及前端生产构建通过，浏览器验证决策区、人物联动、模拟时段表、两种下载和手机布局。

产物：[群体决策摘要](../output/campaign-narratives-v2/audience-decision-brief.txt)、[全部长篇文本](../output/campaign-narratives-v2/audience-ad-comments.txt)、[决策分析界面](../output/campaign-narratives-v2/decision-plan.png)、[个人长篇分析](../output/campaign-narratives-v2/person-detailed.png)、[数据及长度校验](../output/campaign-narratives-v2/data-verification.json)、[浏览器校验](../output/campaign-narratives-v2/ui-verification.json)。同一实验 URL 重新打开即可读取 v2，阅读与下载不触发新的模型生成。

### 精简默认界面

四宫格默认保留地点选择、代表人数、模拟曝光机会、模型兴趣/好感、播放时间与速度。广告编辑、车流、资料入口集中到「广告设置」；同步、循环和场景库管理集中到「场景设置」。每格重复的地点标题、广告说明、轨迹按钮和评分明细收进「场景详情」，地图上的数字与渐变保留，地图版权署名持续显示。

「人群分析」先呈现关键需求，完整群体长文、投放建议、代表性评论及来源按需展开；点击地图人物先看模拟评论和可能行动，再通过「完整人物分析」阅读长文。「导出报告」中提供群体决策报告与完整人物报告。400 人及 48 组详细文本未重新生成或删除。单场景的地区/人群设置、时段排程、实验设置和行为记录也改为折叠入口。

实际浏览器验证：1800px 桌面默认按钮由 20 个减至 10 个，首张地图顶部由约 1040px 上移至 555px；四格在相同时刻的曝光数字一致。已验证广告草稿与应用状态区分、颜色指标、独立时钟、人物/屏幕点击、详细文本、导出、单场景设置及手机无横向溢出。生产构建通过。产物：[桌面](../output/simplified-ui/desktop.png)、[手机](../output/simplified-ui/mobile.png)、[简洁分析区](../output/simplified-ui/analysis.png)、[验收记录](../output/simplified-ui/verification.json)。

### 独立子窗口

四宫格卡片底部的「人群分析」「场景详情」改为两个并排按钮，分别打开独立弹窗；顶部「广告设置」也在弹窗中编辑。共用 `ModalWindow.vue`，通过原生 dialog 和 Teleport 呈现在页面上层，打开时不撑开卡片。窗口内部独立滚动，支持右上角关闭、Esc、点击背景以及 Tab 焦点循环；关闭恢复页面滚动与触发位置。手机窗口限制在视口内，长文仍可展开并导出。

点击地图人物/广告牌会打开相应分析/详情窗口；关闭后再次点击同一人物仍能打开。广告草稿关闭后保留，只有点击应用才会提交；任务进度与错误在弹窗内也可查看。原有数据与模型调用逻辑保留。

生产构建及实际浏览器验收通过：并排按钮、三个窗口、打开前后卡片尺寸、滚动与焦点恢复、Esc/背景/关闭按钮、人物与屏幕联动、完整报告导出、草稿保留和三种手机弹窗。曝光数与进入前一致，操作窗口未触发模型请求。产物：[桌面按钮](../output/modal-ui/desktop.png)、[人群分析](../output/modal-ui/audience.png)、[场景详情](../output/modal-ui/scene.png)、[广告设置](../output/modal-ui/advertising.png)、[手机广告窗口](../output/modal-ui/mobile-advertising.png)、[验收记录](../output/modal-ui/verification.json)。
