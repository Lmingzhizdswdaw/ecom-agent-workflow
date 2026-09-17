# demo

本目录把链路 ③（广告计划搭建）的两层都跑起来——**规则层**算出该填什么，**动作层**真的填进去。

```
data/*.csv  ──►  build_plan_params.py  ──►  「4 条计划分别该写什么」
                                              │
                                              ▼
mock_form/index.html  ◄── CDP ──  fill_form.py  ──►  逐步截图 + 运行结果
```

---

## 规则层：`build_plan_params.py`

读 `data/products.csv` + `data/account_mapping.csv` + `data/rules.yaml`，
推导出每个商品 4 条广告计划的**最终字段值**（计划名、截断后的出价、店铺、落地页、素材目录、常量字段等）。

### 运行

```bash
pip install pyyaml

python demo/build_plan_params.py                                 # 全部商品
python demo/build_plan_params.py --only PDD-330011                # 单个商品
python demo/build_plan_params.py --seed 42 --ts 20260917-104500    # 固定随机ID与时间戳，输出可复现
python demo/build_plan_params.py --out demo/plans.csv             # 导出计划清单
```

### 输出示例

```
规则版本：rules.yaml   下发时间：20260917-104500   取整方式：floor
约束：4 条/品 = 2 条/户 × 2 户

── 德绒保暖护膝中老年秋冬加绒加厚款  [PDD-330011]
   缩写 护膝 │ 出价 12.7 → 12（截断） │ 店铺 demo-pdd-示例店铺
   落地页 https://lp.example.com/330011
   素材   素材库/护膝-德绒-PDD-330011/视频/
   ├─ [ACC-1001] 示例一组+示例操作人+护膝+PDD-330011+pdd+demo-pdd-示例店铺[20260917-104500][HBRPOI]
   ├─ [ACC-1001] ...（同户第 2 条）
   ├─ [ACC-1002] ...（第 2 个户）
   └─ [ACC-1002] ...

合计 4 条计划，覆盖 1 个商品。
```

### 脚本里体现的规则（可对照 `design/03-广告计划搭建.md`）

| 规则 | 代码位置 |
|---|---|
| 4 条/品 = 2 条/户 × 2 户 | `rules.yaml → accounts`，脚本据此双层循环 |
| 出价截断取整（12.7 → 12） | `price_to_int()` |
| 商品缩写 2–5 字 | `make_abbr()`（生产环境由模型生成，这里是确定性兜底） |
| 命名模板 + 随机ID 防重 | `rules.yaml → naming.template` + `make_rand_id()` |
| 素材目录以商品ID 归档 | 取自 `products.csv → 素材路径` |
| 常量字段（业务单元/品牌/跳转类型） | `rules.yaml → constants` |

关于随机ID：默认每次运行都随机；加 `--seed` 后输出完全可复现，便于对照检查。

---

## 动作层：`fill_form.py` + `mock_form/`

规则层算出字段值之后，下一步是**在界面里真的把它们填进去**。真实投放客户端不能用（涉及真实账号与业务数据），
因此本目录用 `mock_form/index.html` **1:1 复刻**了建计划的 6 步表单结构，再通过 CDP 驱动浏览器自动走完。

### 一键复现

```bash
bash demo/run_demo.sh
```

脚本会自动：起本地静态服务 → 以调试端口起无头浏览器 → 通过 CDP 执行 6 步 → 逐步截屏 → 合成展示图。

依赖：`python` + `websocket-client` + `pillow`；本机 Chrome 或 Edge 任一即可。

### 自动走完的 6 步

| 步 | 动作 | 规则来源 |
|---|---|---|
| ① | 引用规则模版 R-001 | 出价/预算/定向/转化目标取模版默认值，避免每次手填 |
| ② | 清空 → 搜索 2 个广告户 → 全选 | 先复位再批量（否则上一次的筛选残留） |
| ③ | 逐户设置：商品库 + 商品全名 + 出价 + 命名 | 4 条/品 ÷ 2 条/户 = 2 户；出价 12.7 → 12 截断 |
| ④ | 定向包 —— **不动** | 明确的不动作区，保持默认 |
| ⑤ | 跳转类型选落地页 → **先清空再写入**小程序路径 | 直接粘贴会与旧值拼接，跳转失效 |
| ⑥ | 按商品ID 检索素材文件夹 → 取「全部」 | 单次上限 15 条，超出直接丢弃 |

最后「生成广告计划」→「开始提交」（生产环境里提交属花钱动作，必须人工确认；此处为本地模拟）。

### 复刻进模拟表单的三个真实陷阱

| # | 陷阱 | 不处理的后果 | 规则如何应对 |
|---|---|---|---|
| 1 | 切换广告户时**商品库被静默重置** | 第 2 条计划商品为空，批量错一批 | 跨账户切换后强制重新校验关键字段（状态复位） |
| 2 | 输入框**旧值不覆盖，直接粘贴会拼接** | 落地页变成 `旧路径+新路径`，跳转直接失效 | 先清空再写入（先删后填） |
| 3 | 批量选择前**不清空**上一次筛选 | 上一个品的账户残留进来 | 批量操作前先复位（幂等性设计） |

陷阱 2 在演示中是**刻意先失败一次**的：`shots/06-未先清空-校验失败.png` 保留了拼接后被校验拦下的现场，
`shots/07-先清空再写入-校验通过.png` 才是正确做法。这两张截图一起看，说明的是护栏存在的意义。

### 产物

```
shots/01-规则模版-选中.png              shots/06-未先清空-校验失败.png   ← 失败现场
shots/02-媒体账号-全选.png              shots/07-先清空再写入-校验通过.png
shots/03-第1个广告户-已填.png            shots/08-素材-按商品ID检索并取全部.png
shots/04-切换第2户-商品库被重置.png       shots/09-已生成计划草稿.png
shots/05-第2个广告户-重新填写.png         shots/10-已提交.png
shots/steps-overview.png                # 一页总览（10 格缩略图）
demo.gif                                # README 首图
```

### 手工运行（拆开跑）

```bash
# 1) 起本地服务
python -m http.server 8899 --bind 127.0.0.1 --directory demo/mock_form

# 2) 以调试端口起浏览器（另开一个终端）
msedge.exe --headless=new --remote-debugging-port=9344 --remote-allow-origins=* \
           --user-data-dir=<临时目录> --no-first-run --disable-gpu --no-proxy-server

# 3) 自动填表并截屏
python demo/fill_form.py --port 9344 --url http://127.0.0.1:8899/index.html --shots demo/shots

# 4) 生成总览图与动图
python demo/make_assets.py --shots demo/shots --out demo
```

### 踩坑记录（环境相关，供复现参考）

- 访问 `127.0.0.1` 的调试端口前要绕开系统代理，否则会被反代吞掉返回 502：`export NO_PROXY=127.0.0.1,localhost`
- 无头浏览器用 `--headless=new`；`agent-browser` 自带的那份 Chromium 是残缺安装（启动即退），换系统 Edge/Chrome 即可
- 截屏前先调 `Emulation.setDeviceMetricsOverride` 固定视口，否则默认 800×600 布局会挤在一起
