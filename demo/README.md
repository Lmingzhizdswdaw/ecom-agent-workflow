# demo

## build_plan_params.py

把链路 ③ 的**规则层**跑起来：读 `data/products.csv` + `data/account_mapping.csv` + `data/rules.yaml`，
推导出每个商品 4 条广告计划的**最终字段值**（计划名、截断后的出价、店铺、落地页、素材目录、常量字段等）。

生产环境里，这些字段值的下一步是**填进投放客户端的表单**（通过 CDP 自动填写）；
本脚本负责的是一半——「算出该填什么」，也就是把业务规则变成确定的字段值。

### 运行

```bash
pip install pyyaml

python demo/build_plan_params.py                              # 全部商品
python demo/build_plan_params.py --only PDD-330011             # 单个商品
python demo/build_plan_params.py --seed 42 --ts 20260917-104500  # 固定随机ID与时间戳，输出可复现
python demo/build_plan_params.py --out demo/plans.csv          # 导出计划清单
```

### 输出示例

```
规则版本：rules.yaml   下发时间：20260917-104500   取整方式：floor
约束：4 条/品 = 2 条/户 × 2 户

── 德绒保暖护膝中老年秋冬加绒加厚款  [PDD-330011]
   缩写 护膝 │ 出价 12.7 → 12（截断） │ 店铺 demo-pdd-示例店铺
   落地页 https://lp.example.com/330011
   素材   素材库/PDD-330011/
   ├─ [ACC-1001] 示例一组+示例操作人+护膝+PDD-330011+pdd+demo-pdd-示例店铺[20260917-104500][HBRPOI]
   ├─ [ACC-1001] ...（同户第 2 条）
   ├─ [ACC-1002] ...（第 2 个户）
   └─ [ACC-1002] ...
```

### 脚本里体现的规则（可对照 `design/03-广告计划搭建.md`）

| 规则 | 代码位置 |
|---|---|
| 4 条/品 = 2 条/户 × 2 户 | `rules.yaml → accounts`，脚本据此双层循环 |
| 出价截断取整（12.7 → 12） | `price_to_int()` |
| 商品缩写 2–5 字 | `make_abbr()`（生产环境由模型生成，这里是确定性兜底） |
| 命名模板 + 随机ID 防重 | `rules.yaml → naming.template` + `make_rand_id()` |
| 素材目录以商品ID 归档 | 输出字段 `素材目录` |
| 常量字段（业务单元/品牌/跳转类型） | `rules.yaml → constants` |

### 关于随机ID

默认每次运行都随机；加 `--seed` 后输出完全可复现，便于对照检查。

---

## 待补

- **`mock_form/`**：用假数据复刻投放客户端的 6 步表单结构（纯本地页面），
  配合 CDP 脚本演示"读字段 → 按规则填写 → 校验"的完整动作层，
  替代真实客户端（不接触任何账号与真实业务数据）。
