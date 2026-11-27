<div align="center">
  <img src="assets/Copy%20of%20VTM%20email%20header.png" alt="VIOOH Trading Manager +Intelligence" width="260">

# AI-Native pDOOH World-Model

**A workspace for full-day audience simulation, screen-level investment analysis, and media proposals in programmatic digital out-of-home advertising**

Minghao LI · [t330034027@mail.bnbu.edu.cn](mailto:t330034027@mail.bnbu.edu.cn)

[Business Workflow](#2-four-stage-business-workflow) · [Calculation Methods](#4-core-metrics-and-mathematical-models) · [Deployment](#6-installation-configuration-and-operation) · [APIs and Acceptance](#7-apis-deliverables-and-acceptance)

</div>

This document describes the current implementation in eight chapters for media planners, advertising operations teams, data analysts, and technical delivery teams. It is grounded in the repository code and saved application reports. The content is organized as an approximately seven-to-eight-page technical overview; Markdown has no fixed pagination, and the printed length depends on image sizes, equation rendering, and page settings.

## 1. Product Scope and Business Applications

### 1.1 The Business Problem

Programmatic digital out-of-home (pDOOH) buying requires screen inventories, locations, media prices, creative assets, and budgets to be evaluated together. Ranking inventory by CPM or reported impressions alone does not explain whether people at a particular location have an opportunity to see a screen, or how different investment priorities change the allocation.

This project organizes that work into an operational workflow: import inventory, prepare campaign inputs, simulate a full day for each screen, consolidate simulation evidence, calculate investment plans, and produce screen-level proposals and Excel workbooks. The primary deliverable is a **traceable media-planning recommendation**. Each screen retains an explicit identifier, location, observation window, campaign duration, share of time (SOT), investment amount, cumulative impressions, and calculation basis.

| Role | Operational task | System output | Next business action |
| --- | --- | --- | --- |
| Media planning | Compare inventory and investment priorities within a budget | Four allocation strategies, maps, and exposure-efficiency charts | Agree on objectives and alternative inventory with the advertiser |
| Advertising operations | Verify locations, creative, dates, and spending | Screen-level allocations, average daily amounts, SOT, and Excel exports | Confirm available shares and prices with the DSP or media owner |
| Data analysis | Examine simulation evidence and performance assumptions | Hourly playback, attitude-score coverage, and financial scenarios | Design field validation or controlled campaign tests |
| Technical delivery | Connect inventory, model, and map services | Project APIs, task progress, and execution records | Deploy services, monitor jobs, and retain audit evidence |

Typical applications include screen selection for regional brand campaigns, portfolio comparison under a fixed budget, creative-to-location suitability analysis, and candidate screening before a limited trial. The system currently **does not connect directly to a DSP to bid or place orders**. It does not replace campaign order management, proof-of-play, billing and settlement, or measured attribution platforms.

### 1.2 Implemented Capabilities

- **Inventory import and validation:** Read Excel worksheets; check identifiers, coordinates, sale eligibility, impressions, prices, and currencies; preserve original records and exclusion reasons.
- **Scene construction and full-day simulation:** Place screens within local neighborhoods, generate representative audiences and journeys, account for pedestrian and in-vehicle viewing opportunities, and record 24 hourly results.
- **Creative analysis:** Use campaign inputs and representative profiles to generate model-based favorability and interest scores, with inspectable sources and coverage.
- **Inventory-wide task management:** Display processed-screen counts and completion status. Two scenes loop during processing, and reporting becomes available after all screens finish.
- **Investment planning and proposals:** Allocate funds under different objectives and show campaign-period cumulative impressions, average daily amounts, SOT, financial scenarios, and differences between plans.

![Actual two-scene full-day playback](project-page/dist/assets/simulation-scenes.webp)

*Application capture: two locations share a playback clock while retaining separate scene and statistical evidence. The pedestrians and traffic shown are simulated scenarios.*

## 2. Four-Stage Business Workflow

### 2.1 Data and Settings

Open `/planning` and upload an `.xlsx` workbook containing `FilteredFrames`. The interface also accepts the worksheet name `filtered_frames`. Use the repository's `data/test.xlsx` to verify the deployment and data flow before importing operational inventory.

Enter the total budget, budget currency, start date, and campaign duration. Add geographic filters, exchange rates, the DSP fee rate, CPM markup, and per-screen constraints as required. Planning duration and the inventory impression measurement period are separate parameters: the former specifies campaign length; the latter defines how many days the source `IMPRESSIONS` value covers. If no explicit campaign duration is supplied, the interface defaults to a 30-day budget-estimation period.

### 2.2 Campaign Setup

Save the campaign details and creative assets, then verify regional context, traffic estimates, and any manually entered vehicle-flow parameters. Advertising copy, images, and contextual documents are model inputs. A small number of people visible in a photograph must not be extrapolated directly into neighborhood footfall.

Confirm the creative, target geography, and traffic assumptions before starting a batch. Changes to inventory, campaign details, creative assets, traffic parameters, or supporting documents can invalidate the match between an existing batch and the current inputs, requiring new evidence.

### 2.3 Audience Simulation

For every screen in the batch, the system prepares location information, population, routes, and advertising analysis, then records the full-day results. Screens are processed through parallel background tasks. The interface's `x / N screens processed` indicator measures completed screen processing, not playback progress.

The two-scene player supports inspection of hourly evolution at different locations. Moving the playback clock to `23:59` changes only the viewing position; it does not mark the entire inventory as complete. Report readiness requires a matching, complete record for each screen, including a recognized execution engine, completed status, a 24-hour schedule, and snapshots for rounds 1–24. Historical batches, preview scenes, and incomplete runs cannot substitute for the current batch.

### 2.4 Reports and Investment Recommendations

After all screens complete, generate the consolidated report and review investment, cumulative impressions, scores, and evidence sources. The investment map supports regional inspection and screen-level drilldown. The distribution view combines investment and impression distributions with the screen-level scatterplot. Investment details, inventory scorecards, and plan details are paginated at five screens per page.

Plan comparison provides an integrated recommendation, exposure-efficiency priority, audience-interest priority, and regional-dispersion priority. Selecting a strategy updates its allocations, cumulative impressions, and visualizations together. Export the selected strategy to Excel. Before procurement, operations staff should confirm actual pricing, minimum purchasable shares, scheduling, and remaining inventory.

## 3. Input Contracts, Data Sources, and Traceability

### 3.1 Inventory Fields

| Field | Business meaning and processing requirements |
| --- | --- |
| `VIOOH_ID` | Unique screen identifier; aliases such as `SCREENID` are supported. All rows sharing a duplicate identifier are temporarily excluded from allocation rather than accepting the first row. |
| `GEOM` | Geographic point, commonly represented as `POINT(longitude latitude)`, used for location resolution and consistency checks. |
| `LATITUDE`, `LONGITUDE` | WGS84 coordinates, which must be valid and match the intended location. Location resolution and planning-data validation perform their own checks. |
| `ADDRESS_*`, `CLOSEST_POI` | Address, city, country, and nearby point of interest, used for search, display, and regional context. |
| `VENUE_TAXONOMY_VALUE` | Venue category, such as transport, retail, or street environments. |
| `IMPRESSIONS` | Inventory-supplied impression volume. Its measurement period must be specified; it is not assumed to be a daily count. |
| `FLOORCPM`, `MEDIAOWNERCURRENCY` | Media CPM and its original currency, converted using the supplied exchange rates before proposal calculation. |
| `VIOOHSELECTOPTIN` | Confirmation of sale eligibility. Unconfirmed inventory remains in the records with an exclusion reason. |
| `FRAMEIMAGEPATH` | Reference to on-site imagery. Analysis also depends on image accessibility and the selected vision model's capabilities. |

Original rows, normalized fields, and calculated results are retained separately. Source fields such as `SCORE_P` remain available for reference and must not be interpreted as this system's final composite score. Missing values are not zeros: unknown attitudes may use a neutral prior when calculating importance, while the underlying attitude fields and their provenance remain explicitly unknown.

### 3.2 Three Levels of Measurement

| Level | Typical data | Appropriate use |
| --- | --- | --- |
| Input evidence | Inventory, coordinates, site photographs, regional documents, and traffic parameters | Define the candidate inventory and simulation conditions |
| Simulation observations | Recorded hours, weighted viewing opportunities, favorability, and interest | Compare locations, creative responses, and screens within the batch |
| Commercial estimates | Campaign duration, SOT, cumulative impressions, investment, and ROI scenarios | Develop budget plans, proposals, and trial-validation plans |

These levels must not be collapsed into a single performance score. For example, simulating a screen for 24 hours and producing a 30-day budget recommendation does not mean that 30 independent days were simulated. The daily result is extended linearly over the specified campaign period and SOT.

### 3.3 Batch Consistency and Persistence

A project signature is generated from inputs including inventory, campaign details, creative assets, traffic parameters, documents, and the full-day schedule. The reporting endpoint revalidates the current batch on the server and binds the result to `campaign_id`, `simulation_batch_id`, and an evidence fingerprint. This prevents clients from combining unrelated campaign results. If coordinates and simulation evidence do not match, that evidence cannot continue to be attributed to the same screen.

Runtime data is stored under `backend/uploads/`: `planning/` contains projects and coverage tasks, `campaign_experiments/` contains advertising experiments, and `scene_library/` contains playback scenes. Large per-screen inputs are archived separately to keep progress state lightweight. Partial-progress polling avoids repeatedly parsing every completed scene; final readiness checks and report generation still perform full validation.

## 4. Core Metrics and Mathematical Models

The notation below follows the current implementation. Let $s$ denote a screen, $a$ a synthetic representative, $t$ an hour, $D$ the planning duration in days, $\alpha_s$ the screen's SOT, and $B$ the total budget.

### 4.1 Policy-Driven Attention Decisions

Fast mode first generates policy parameters for each representative, then executes full-day evolution locally. Parameters include the base notice probability $p_a$, interest probability, preferred dwell time, fatigue coefficient $f_a$, and peer-influence coefficient $\beta_a$.

When a representative has line of sight to the screen and available viewing time $\tau_{a,t}>0$:

$$
p_{a,t}=\operatorname{clip}_{[0,1]}\left(
\frac{p_a\min(1,\tau_{a,t}/5)}{1+f_a n_{a,t}}
+\beta_a q_{a,t}\right).
$$

Here, $n_{a,t}$ is the number of previous encounters that attracted attention, and $q_{a,t}$ is the proportion of other representatives attending to the same screen in the preceding round. Without line of sight or available time, the decision is a pass-by. Representatives without a scheduled journey or whose routes do not encounter the screen are recorded as absent or unexposed, respectively. Dwell time is bounded by the available viewing window, and responses distinguish brief glances, watching, and interest.

Random draws are determined by the seed, representative identifier, and round. Fixed policies, scenes, and seeds support reproducibility of local trajectories; regenerating policies through the model can still change the outcome. `policy_simulation_v1` is an explicitly recorded method version, not independent language-model inference for every person in every hour.

### 4.2 Campaign-Period Cumulative Impressions

Let $O_s$ be the weighted opportunity total recorded for a screen over $H_s$ simulated hours. Event weights represent population or in-vehicle opportunity volumes, rather than the number of icons visible in the interface:

$$
O_s=\sum_{e\in\mathcal E_s}w_e,\qquad
\widehat I_s=O_s\frac{24}{H_s}D\alpha_s.
$$

$\widehat I_s$ is the cumulative opportunity count across the entire planning period at the recommended SOT. The table's `recommended_exposures` field already includes duration and SOT scaling; the frontend must not multiply it by $D$ again. The original observation total and observation hours are displayed separately.

In the underlying inventory-planning path, an inventory volume $I_s^{\mathrm{inv}}$ measured over $P$ days is scaled as $I_s^{\mathrm{inv}}D\alpha_s/P$. The current four-stage final-report workflow requires direct simulation from the active batch and does not automatically fill missing screens with inventory estimates or predictions. Summing across screens produces total opportunities, not deduplicated reach.

### 4.3 CPM, Investment, and Average Daily Amount

Let $c_s^0$ be the media CPM in its original currency, $m$ the markup rate, $r_s$ and $r_B$ the exchange rates expressed as USD per unit of the media and budget currencies, and $\delta$ the DSP fee rate:

$$
c_s=c_s^0(1+m)\frac{r_s}{r_B},\qquad
c_s^{\mathrm{all}}=c_s(1+\delta).
$$

$$
M_s=\frac{\widehat I_s}{1000}c_s,\qquad
F_s=M_s\delta,\qquad
A_s\approx M_s+F_s,\qquad
\overline A_s=\frac{A_s}{D}.
$$

$M_s$ is the media budget, $F_s$ the DSP fee, and $A_s$ the recommended investment. Amounts are processed in cents, and exports can retain a rounding reserve. The average daily amount $\overline A_s$ divides total investment at the recommended SOT by the number of days; it is **not a separately guaranteed daily rental rate from the media owner**. Additional execution costs are accounted for separately in the overall budget rather than included in the average daily media amount.

For example, with daily opportunities $O_s=200{,}000$, $H_s=24$, $D=30$, and SOT of $0.2\%$, cumulative impressions are $12{,}000$. At a converted CPM of USD 10 and a DSP fee of 10%, the media budget is USD 120, the DSP fee is USD 12, total investment is USD 132, and the average daily amount is USD 4.40. This illustrates the calculation and is not an actual supplier quote.

### 4.4 Importance and Budget Allocation

Composite importance combines seven dimensions: exposure, favorability, interest, visibility, location, market fit, and cost:

$$
S_s=\sum_{k=1}^{7}\omega_k z_{s,k},\qquad
\sum_k\omega_k=1,\quad z_{s,k}\in[0,100].
$$

The default raw weights are 20, 15, 20, 15, 15, 10, and 5, respectively, and are normalized before use. Unknown dimensions use 50 as a ranking prior; the resulting sensitivity bounds are not statistical confidence intervals. The exposure dimension in the final report is normalized against the maximum screen opportunity count in the current batch.

The complete report uses a trial-seed allocation followed by constrained weighted redistribution. Under the effectiveness objective, $u_s=S_s/100$, and the relative allocation weight is:

$$
v_s=\frac{\max\{\varepsilon,u_s/\max(0.01,c_s^{\mathrm{all}})\}}
{1+\lambda(n_{g(s)}-1)},\qquad \varepsilon=10^{-6}.
$$

$n_{g(s)}$ is the number of candidates in the screen's allocation grid cell, and $\lambda$ penalizes regional concentration. Allocation cells use approximately $0.01$-degree latitude and longitude intervals. They differ from the approximately 400-meter display groups on the report map and do not measure actual audience overlap.

Let $C_s^{\mathrm{full}}$ be the full-period cost at full SOT, $\rho$ the per-screen budget-share limit, and $E_s$ the additional execution cost. Allocations must satisfy:

$$
0\le A_s\le\min\{\alpha_{\max}C_s^{\mathrm{full}},\max(0,\rho B-E_s)\},\qquad
\sum_s A_s+\sum_{s:A_s>0}E_s\le B.
$$

The algorithm first assigns a small seed amount to candidates with capacity for at least 0.01 currency units. It then distributes the remaining funds according to $v_s$ among screens that have not reached their limits and meet the importance threshold. The profit objective also checks baseline-return conditions. Allocation stops when capacity is exhausted or no eligible candidates remain; spending the entire budget is not forced. Finally, $\alpha_s=A_s/C_s^{\mathrm{full}}$. This is a reproducible allocation heuristic, not a guarantee of global optimality. Continuous SOT fractions still require confirmation against the media owner's minimum purchasable shares.

### 4.5 Exposure Efficiency and Financial Scenarios

Plan-level exposure efficiency uses weighted CPM, not the arithmetic mean of individual screen CPMs:

$$
\operatorname{CPM}_{\mathrm{plan}}=
1000\frac{\sum_s A_s}{\sum_s\widehat I_s}.
$$

Financial estimates require separate assumptions for orders per thousand impressions $r_s$, the incremental attribution factor $\gamma$, average order value $V$, gross margin $\mu$, and total cost $C$:

$$
\Delta Q=\sum_s\frac{\widehat I_s}{1000}r_s\gamma,\quad
\Delta R=V\Delta Q,\quad
\operatorname{ROI}=\frac{\mu\Delta R-C}{C},\quad
\operatorname{ROAS}=\frac{\Delta R}{C}.
$$

When financial inputs are missing, the complete report can insert explicitly labeled demonstration assumptions: average order value 100, gross margin 0.45, incremental attribution factor 0.25, and low/base/high orders per thousand impressions of 0.05, 0.1, and 0.2. These values support scenario calculations; they are not industry benchmarks or validated conversion rates.

When screen-specific treatment and control observations are supplied, incremental orders per thousand impressions can be calculated as:

$$
r_s^\Delta=1000\left(\frac{Q_s^T}{I_s^T}-\frac{Q_s^C}{I_s^C}\right).
$$

Because this already represents an incremental difference, the code sets the attribution factor to 1 to avoid applying it twice. Low and high estimates use an approximate Poisson sensitivity calculation with a stabilizing term. Group comparability, consistent exposure definitions, and sample independence still require business validation.

## 5. Investment Strategies, Visualizations, and an Application Example

### 5.1 Four Investment Priorities

| Strategy | Current allocation characteristics | Business question |
| --- | --- | --- |
| Integrated investment recommendation | Seven-dimensional importance with the current cost, regional, and per-screen constraints | What baseline plan is supported by the available evidence? |
| Exposure-efficiency priority | Exposure weight 70%, cost 30%, regional penalty 0 | Which screens should receive additional budget based on exposure and cost? |
| Audience-interest priority | Interest 65%, favorability 25%, market fit 10%, regional penalty 0.5 | How can more budget be directed toward contexts with stronger creative-response alignment? |
| Regional-dispersion priority | Location 50%, exposure 30%, visibility 20%, regional penalty 4 | How can budget concentration in densely represented candidate areas be reduced? |

All four strategies share the same simulation batch and commercial inputs. Changing the investment priority does not require another full-day run. Different weights do not guarantee improvement in every metric: per-screen capacity, fees, and thresholds may dominate, producing similar plans. Exposure-efficiency priority is not a promise of globally optimal cumulative impressions.

### 5.2 A Verifiable Report Snapshot

The following results come from the local application's saved 144-screen report and project-page dataset, using a USD 10,000 budget and a 30-day planning period. All 144 screens have direct simulation evidence; 139 receive positive allocations, 139 have direct attitude scores, and none have calibrated financial-return evidence. A fresh clone does not include the complete backend execution state for this example.

| Strategy | Media investment, including DSP (USD) | Campaign-period cumulative impressions | Weighted CPM (USD) | Funded screens |
| --- | ---: | ---: | ---: | ---: |
| Integrated investment recommendation | 10,000.00 | 1,029,742 | 9.71 | 139 |
| Exposure-efficiency priority | 10,000.00 | 1,014,841 | 9.85 | 139 |
| Audience-interest priority | 10,000.00 | 1,000,774 | 9.99 | 139 |
| Regional-dispersion priority | 10,000.00 | 1,030,606 | 9.70 | 139 |

Impressions are simulated opportunities scaled by the campaign period and SOT. Values are rounded only for presentation. The underlying figures are available in the [project-page results file](project-page/dist/assets/results.json).

![Investment distribution, cumulative impressions, and screen-level relationships](project-page/dist/assets/investment-distribution.webp)

Review totals, distributions, and individual screens together. The map shows the spatial distribution of investment; histograms show where investment and cumulative impressions are concentrated; the scatterplot compares exposure at similar spending levels. Lower CPM does not automatically imply stronger brand outcomes or purchase returns.

## 6. Installation, Configuration, and Operation

### 6.1 Technology and Directory Structure

The frontend uses Vue 3, Vite, and MapLibre; the backend uses Flask; fast simulation runs in a separate Python process. Model requests, map verification, and deterministic local calculations are organized separately. Legacy social-simulation and graph services are optional modules rather than the recommended four-stage workflow described here.

```text
backend/app/audience/       Data, maps, audiences, simulation, scoring, and allocation
backend/scripts/           Policy simulation and other worker entry points
backend/tests/             Planning, simulation, coverage, and consistency tests
frontend/src/views/        ScreenPlanning.vue: four-stage workflow entry point
frontend/src/components/   Playback, maps, reports, and distribution components
backend/uploads/           Local runtime data and results; excluded from Git
data/test.xlsx             Test inventory
project-page/              Standalone project page, screenshots, and result data
```

### 6.2 Install Dependencies

Use Python 3.11 or 3.12 and Node.js 22.12+, with a dedicated virtual environment. Repository dependency manifests and lockfiles define the installed versions.

```bash
git clone https://github.com/SuleynanAuir/AI-Native-pDOOH-Worlds-Model.git
cd AI-Native-pDOOH-Worlds-Model
cp .env.example .env
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-planning.txt
npm ci --prefix frontend
```

Configure the actual services in the project-root `.env` file. The following values are placeholders, not usable credentials:

```dotenv
LLM_API_KEY=<your-model-service-key>
LLM_BASE_URL=<compatible-api-base-url>
LLM_MODEL_NAME=<available-text-model>
MULTIMODAL_ENABLED=true
MULTIMODAL_VISION_API_KEY=<your-vision-service-key>
MULTIMODAL_VISION_BASE_URL=<vision-api-base-url>
MULTIMODAL_VISION_MODEL=<image-capable-model>
MULTIMODAL_VISION_API_STYLE=chat
LOCATION_PROVIDER=mapricot
MAPRICOT_API_KEY=<your-map-service-key>
LOCATION_LOOKUP_ENABLED=true
PDOOH_POLICY_SIMULATION=true
```

Set `PDOOH_POLICY_SIMULATION=true` explicitly; a fresh clone does not inherit a mode previously enabled on another machine. This mode uses the backend's current Python environment and does not require the OASIS worker. To run alternative paths, create `backend/.venv-oasis` using `backend/requirements-world.txt` and configure `OASIS_PYTHON` as required. Legacy graph services are disabled by default.

Behavioral policies, population preparation, and creative analysis require model services. Nearby-place queries and basemaps require the corresponding map capabilities. After changing a service endpoint, verify actual API responses rather than checking only that environment variables exist. Keep credentials on the server; do not expose them through `VITE_` variables.

### 6.3 Start Services and Check Health

Run the following commands in separate terminals:

```bash
# Terminal 1: backend, default port 5001
.venv/bin/python backend/run.py
```

```bash
# Terminal 2: frontend, initially attempts port 3000
npm --prefix frontend run dev
```

```bash
# Verify that the backend responds
curl http://127.0.0.1:5001/health
```

If the frontend port is occupied, Vite selects a subsequent port; use the address printed in the terminal. Open `http://127.0.0.1:<frontend-port>/planning`. The `/world` route provides the standalone simulation workspace. The development proxy forwards `/api` to `http://localhost:5001`; update the proxy if the backend port changes.

The project showcase can run independently of the simulation backend:

```bash
python3 -m http.server 4178 --bind 127.0.0.1 --directory project-page/dist
```

Screenshots and project-page example data do not constitute preinstalled backend jobs. New projects should begin with inventory import and complete their own simulation batches.

## 7. APIs, Deliverables, and Acceptance

### 7.1 Common APIs

Business endpoints use the `/api` prefix. Except for health checks and file downloads, typical responses contain `success` and `data`, or `error` on failure. The table describes endpoint purposes; consult the corresponding routes and frontend calls for request fields.

| Method and path | Purpose |
| --- | --- |
| `POST /api/planning/import` | Upload a workbook using multipart field `workbook`, optionally with `source_sheet` |
| `POST /api/planning/sample` | Create a test-inventory project |
| `GET /api/planning/<pid>` | Read the project, inventory, and currently valid report |
| `GET/POST /api/planning/<pid>/ad-setup` | Read or save campaign settings |
| `POST /api/planning/<pid>/creative` | Upload a creative asset |
| `GET/POST /api/planning/<pid>/coverage` | Inspect or start inventory-wide processing for the current batch |
| `POST /api/planning/<pid>/plan` | Validate completion of all screens and generate investment plans |
| `GET /api/planning/<pid>/export?strategy=investment` | Export the specified strategy to Excel |

Reporting requires complete coverage for the current batch. Submitting budget parameters alone cannot bypass missing full-day evidence. A historical campaign identifier supplied by the frontend must not be treated as the currently valid batch.

### 7.2 Excel Export and Procurement Handoff

The exported workbook includes the selected strategy's Proposal and associated audit information, together with integrated investment rankings, financial scenarios, and assumptions. A key distinction is that **Proposal corresponds to the selected comparison strategy, while Investment Ranking and Return Scenarios describe the integrated investment strategy**. Confirm the strategy before reconciling worksheets; do not combine different worksheets as if they all describe the same allocation.

Before handing the proposal to buying or operations teams, verify screen identifiers and locations, dates and duration, currencies and exchange rates, CPM and DSP fees, screen-level amounts, SOT, campaign-period cumulative impressions, additional execution costs, and reasons for non-allocation. Totals and exported formulas should be reproducible. Where displayed daily amounts are rounded, the full-period total is authoritative.

### 7.3 Recommended Acceptance Sequence

1. **Inventory:** Confirm the imported count and trace duplicate identifiers, invalid coordinates, sale-eligibility issues, and currency problems to their original rows.
2. **Simulation:** Confirm that every target screen belongs to the same valid batch and has all 24 rounds. Interrupted runs must not count as completed.
3. **Reporting:** Keep observation and campaign periods separate; verify that cumulative impressions are not multiplied by duration twice and that allocations respect budget and screen-capacity limits.
4. **Interaction:** Check overall progress, completion notification, two-scene playback, pagination, map selection, and switching between all four strategies.
5. **Delivery:** Verify that the selected strategy matches the Excel Proposal and that media spending, DSP fees, execution costs, and remaining budget reconcile.

```bash
npm --prefix frontend run build
PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/tests/test_investment.py \
  backend/tests/test_policy_simulation.py \
  backend/tests/test_coverage_parallel.py \
  backend/tests/test_simulation_workflow.py -q
```

These checks validate code behavior. They do not replace acceptance testing against live model services, map services, and the complete inventory workflow. External-service failures, rate limits, or configuration changes can affect end-to-end execution.

## 8. Performance, Operations, and Business Validation

### 8.1 Performance Design

Policy mode replaces per-person, per-hour model interactions with batched policy generation. For 100 representatives, batches of 25 and up to four generation threads typically produce four initial policy requests, followed by local 24-hour evolution. Validation failures can trigger retries. Population preparation, map queries, creative-attitude analysis, and result processing incur separate costs; four policy batches therefore do not mean that an entire screen requires only four external requests.

Inventory coverage currently runs at most three screen tasks concurrently and overlaps independent advertising analysis with simulation. Route caching reduces repeated pathfinding, lightweight progress records are written separately from full checkpoints, and vehicle playback uses weighted samples to control volume. Measure processing time from task initiation until final playback and reporting evidence are ready, rather than timing model requests alone. No fixed acceleration factor is guaranteed.

### 8.2 Troubleshooting

| Symptom | Check first | Recommended action |
| --- | --- | --- |
| The interface shows `Network Error` | Backend health, actual frontend port, proxy destination, and stale API addresses | Restore API connectivity before refreshing; do not repeatedly create projects to mask the problem. |
| The map shows coordinates but no streets | Map-service permissions, credentials, tile requests, and network access | Allow loading to complete or fix the configuration. A coordinate-only fallback does not establish successful basemap verification. |
| Overall progress stops increasing | Current screen errors, model rate limits, map failures, and worker state | Inspect task state and logs, address the cause, and retry through the interface while preserving completed records. |
| Playback reaches the end of the day but reporting remains disabled | Inventory-wide completion and batch-signature consistency | Use backend `ready` status as the authority; do not manually alter completion counts. |
| SOT is very small despite a nonzero allocation | Continuous shares and display precision | Reconcile using a higher-precision percentage and total investment, then confirm the actual minimum purchasable share. |
| Strategies produce similar results | Capacity limits, budget, thresholds, and cost distribution | Compare per-screen allocations as well as totals; do not manufacture differences between plans. |

### 8.3 From Planning to Live Campaigns

For initial business validation, select a manageable group of screens and verify on-site locations, actual pedestrian and vehicle traffic, screen orientation, and visibility. Then record trial delivery, spending, and exposure definitions. If the objective is conversion or incremental revenue, design controls with comparable timing and geography, specify order attribution, repeated exposure, and attribution windows, and feed calibration observations back using screen identifiers.

External deployment requires authentication, authorization, TLS, persistent backups, process management, API rate limits, and log-retention policies. The current local-file state and Flask workspace should not be exposed directly as a production multi-tenant platform. Map, image, and model requests must also comply with the relevant service terms and data-handling requirements. Raw uploads, credentials, logs, and local execution state are excluded from Git.

### 8.4 Implementation Entry Points and Licensing

- Data validation and traditional inventory planning: [planning.py](backend/app/audience/planning.py).
- Inventory-wide reporting, strategy variants, and financial scenarios: [investment.py](backend/app/audience/investment.py).
- Continuous-SOT budget allocation: [investment_allocation.py](backend/app/audience/investment_allocation.py).
- Individual behavioral policies and validation: [policy_simulation.py](backend/app/audience/policy_simulation.py).
- Batch signatures and full-day completion checks: [simulation_workflow.py](backend/app/audience/simulation_workflow.py).
- Four-stage interface: [ScreenPlanning.vue](frontend/src/views/ScreenPlanning.vue).

The root [LICENSE](LICENSE) currently specifies MIT. Some package metadata retains different historical license fields; reconcile these before formal distribution. The code license does not automatically grant redistribution rights for third-party models, maps, source media data, or brand assets.
