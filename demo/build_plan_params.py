#!/usr/bin/env python3
"""从「商品信息表 + 账户映射表 + 规则配置」推导出每个商品的 4 条广告计划字段值。

这是链路 ③ 广告计划搭建 的规则层演示：
  - 生产环境里，最终动作是把这些字段值填进投放客户端的表单（通过 CDP 自动填写）
  - 本脚本只负责「算出该填什么」——即把业务规则变成确定的字段值

不依赖任何真实系统与数据：data/ 下全部为虚构示例。

用法：
    python demo/build_plan_params.py                      # 全部商品
    python demo/build_plan_params.py --only PDD-330011     # 单个商品
    python demo/build_plan_params.py --seed 42 --ts 20260917-104500
    python demo/build_plan_params.py --out demo/plans.csv
"""

import argparse
import csv
import random
import string
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

try:
    import yaml
except ImportError:
    sys.exit("缺少依赖，请先安装：pip install pyyaml")


def load_rules(path=DATA / "rules.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_table(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def make_abbr(full_name, rules):
    """商品缩写（2–5 字）。

    生产环境：由模型理解商品全名后生成。
    此处为可复现的确定性兜底实现：命中核心词表则用核心词，否则取前 3 字。
    """
    hi = rules["naming"]["abbr_len"][1]
    for word in rules.get("abbr_core_words", []):
        if word in full_name:
            return word[:hi]
    return full_name[:3]


def price_to_int(raw, mode="floor"):
    """取整方式：floor = 截断（12.7 → 12）。保守取值，不向上突破成本线。"""
    value = float(str(raw).strip())
    return int(value) if mode == "floor" else round(value)


def make_rand_id(rng, length):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(rng.choice(alphabet) for _ in range(length))


def build_plans(products, mapping, rules, rng, ts):
    c = rules["constants"]
    ac = rules["accounts"]
    mode = rules["pricing"]["round_mode"]
    tpl = rules["naming"]["template"]

    by_name = {row["商品全名"]: row for row in mapping}
    plans = []
    warnings = []

    for product in products:
        name = product["商品全名"]
        pid = product["商品ID"]
        accounts = by_name.get(name)

        if not accounts:
            warnings.append(f"账户映射表缺少「{name}」→ 跳过")
            continue

        abbr = make_abbr(name, rules)
        raw_price = product["商品出价"]
        price = price_to_int(raw_price, mode)

        for slot, col in enumerate(("广告户1", "广告户2"), start=1):
            account = accounts[col]
            for index in range(1, ac["plans_per_account"] + 1):
                plan_name = tpl.format(
                    group=c["group"],
                    operator=c["operator"],
                    abbr=abbr,
                    product_id=pid,
                    platform_code=c["platform_code"],
                    shop_key=c["shop_key"],
                    ts=ts,
                    rand_id=make_rand_id(rng, rules["naming"]["rand_id_len"]),
                )
                plans.append(
                    {
                        "商品全名": name,
                        "商品ID": pid,
                        "商品缩写": abbr,
                        "广告户": account,
                        "户内序号": index,
                        "广告户槽位": slot,
                        "优化目标出价": price,
                        "出价原值": raw_price,
                        "广告名称": plan_name,
                        "落地页链接": product["商品落地页"],
                        "素材目录": product["素材路径"],
                        "商品库店铺": c["shop_key"],
                        "业务单元": c["business_unit"],
                        "品牌": c["brand"],
                        "跳转类型": c["landing_page_type"],
                        "商品属性兜底": rules["fallback"]["attribute_no_match"],
                    }
                )
    return plans, warnings


def print_report(plans, rules, ts):
    c = rules["constants"]
    ac = rules["accounts"]
    mode = rules["pricing"]["round_mode"]

    print(f"规则版本：{Path('data/rules.yaml').name}   下发时间：{ts}   取整方式：{mode}")
    print(f"约束：{ac['plans_per_product']} 条/品 = {ac['plans_per_account']} 条/户 × 2 户")
    print()

    current = None
    for plan in plans:
        if plan["商品全名"] != current:
            current = plan["商品全名"]
            print(f"── {current}  [{plan['商品ID']}]")
            print(
                f"   缩写 {plan['商品缩写']} │ 出价 {plan['出价原值']} → {plan['优化目标出价']}（截断）"
                f" │ 店铺 {plan['商品库店铺']}"
            )
            print(f"   落地页 {plan['落地页链接']}")
            print(f"   素材   {plan['素材目录']}/")
        is_last = plan["广告户槽位"] == 2 and plan["户内序号"] == ac["plans_per_account"]
        mark = "└" if is_last else "├"
        print(f"   {mark}─ [{plan['广告户']}] {plan['广告名称']}")

    print()
    print(f"合计 {len(plans)} 条计划，覆盖 {len({p['商品全名'] for p in plans})} 个商品。")
    print(f"（终端用户可见字段均来自固定常量：业务单元={c['business_unit']}，品牌={c['brand']}，"
          f"跳转类型={c['landing_page_type']}）")


def main():
    parser = argparse.ArgumentParser(description="推导广告计划的最终字段值（规则层演示）")
    parser.add_argument("--only", help="只处理指定商品ID")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，固定后输出可复现")
    parser.add_argument("--ts", default=None, help="下发时间戳，如 20260917-104500")
    parser.add_argument("--out", help="导出计划清单 CSV 的路径")
    args = parser.parse_args()

    rules = load_rules()
    products = load_table(DATA / "products.csv")
    mapping = load_table(DATA / "account_mapping.csv")

    if args.only:
        products = [p for p in products if p["商品ID"] == args.only]
        if not products:
            sys.exit(f"未找到商品ID：{args.only}")

    ts = args.ts or datetime.now().strftime("%Y%m%d-%H%M%S")
    rng = random.Random(args.seed)

    plans, warnings = build_plans(products, mapping, rules, rng, ts)

    for warning in warnings:
        print(f"[警告] {warning}")
    if warnings:
        print()

    print_report(plans, rules, ts)

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(plans[0].keys()))
            writer.writeheader()
            writer.writerows(plans)
        print(f"\n已导出：{out_path}")


if __name__ == "__main__":
    main()
