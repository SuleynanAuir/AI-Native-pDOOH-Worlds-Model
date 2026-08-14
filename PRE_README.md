# AI-Native pDOOH Screen Planning

> 输入原始屏幕库存、屏幕照片、目标国家的社会学资料、可选消费者调研和总预算；从“什么人可能经过、是否容易看见”出发，输出屏幕筛选、重要性评估与预算分配方案。

## 1. 我们实际拥有的输入

平台不预设完整的 Campaign Brief、广告创意或个人级用户数据。当前输入只有以下五类。

### 1.1 Original Frame Excel（必选）

参考文件为 [`data/test.xlsx`](data/test.xlsx)。系统只依赖表头和字段语义，不依赖示例中的具体数值。

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

详细技术设计见 [README.md](README.md)。
