#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_form.py —— 通过 CDP 自动完成「批量搭建广告」6 步流程（动作层演示）

演示对象：demo/mock_form/index.html（本地复刻的假表单，全部假数据）
不连接任何真实投放平台，不涉及任何公司账号。

用法：
    1) 用调试端口启动 Chromium / Chrome：
       chrome.exe --headless=new --remote-debugging-port=9333 \
                  --remote-allow-origins=* --user-data-dir=<临时目录> about:blank
    2) python fill_form.py [--port 9333] [--url http://127.0.0.1:8899/index.html] [--shots demo/shots]

输出：按步骤截屏到 --shots 目录，并在控制台打印每步动作与最终运行状态。
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request

import websocket  # websocket-client


# ---------------------------------------------------------------- CDP 客户端
class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=40, suppress_origin=True)
        self._id = 0

    def send(self, method, params=None):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"{method} 失败: {msg['error']}")
                return msg.get("result", {})

    def ev(self, expr):
        """执行 JS 表达式并取回值"""
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True,
        })
        if "exceptionDetails" in r:
            raise RuntimeError("JS 异常: " + json.dumps(r["exceptionDetails"], ensure_ascii=False)[:300])
        return r.get("result", {}).get("value")

    def goto(self, url):
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send("Page.navigate", {"url": url})
        time.sleep(2.5)

    def set_viewport(self, width=1440, height=1000):
        self.send("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
        })

    def shot(self, path, full_page=True):
        params = {"format": "png"}
        if full_page:
            params["captureBeyondViewport"] = True
        r = self.send("Page.captureScreenshot", params)
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))
        print(f"    📷 {os.path.basename(path)}")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def pick_page(port):
    raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10).read()
    for t in json.loads(raw):
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("未找到 page 目标")


# ---------------------------------------------------------------- 演示数据
PRODUCT = {
    "name": "德绒保暖护膝中老年秋冬加绒加厚款",
    "id": "PDD-330011",
    "bid_raw": "12.7",       # 文件里的出价
    "bid_fill": "12",        # 规则：截断取整，不四舍五入
    "lp": "https://lp.example.com/330011",
    "abbr": "护膝",
    "accounts": ["ACC-1001", "ACC-1002"],   # 一个品 4 条 = 2 户 × 2 条上限
}
SHOP = "demo-pdd-示例店铺"
TS = "20260917-113000"
GROUP = "示例一组"
OPERATOR = "示例操作人"


def plan_name(rand_id):
    return f"{GROUP}+{OPERATOR}+{PRODUCT['abbr']}+{PRODUCT['id']}+pdd+{SHOP}[{TS}][{rand_id}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9333)
    ap.add_argument("--url", default="http://127.0.0.1:8899/index.html")
    ap.add_argument("--shots", default="shots")
    args = ap.parse_args()

    os.makedirs(args.shots, exist_ok=True)
    S = lambda n: os.path.join(args.shots, n)

    cdp = CDP(pick_page(args.port))
    print(f"✅ 已连接调试端口 {args.port}")

    cdp.set_viewport(1440, 1000)
    cdp.goto(args.url)
    cdp.set_viewport(1440, 1000)
    title = cdp.ev("document.title")
    print(f"✅ 已加载页面：{title}\n")

    print("【步骤 1】引用规则模版")
    cdp.ev("document.getElementById('btn-rule-template').click()")
    time.sleep(0.4)
    cdp.ev("document.querySelectorAll('#rule-list .rowitem')[0].click()")
    time.sleep(0.3)
    cdp.shot(S("01-规则模版-选中.png"))
    cdp.ev("document.getElementById('btn-rule-confirm').click()")
    time.sleep(0.4)
    print("    · 已引用模版 R-001（出价/预算/定向/转化目标取默认）")

    print("【步骤 2】选择媒体账号")
    cdp.ev("document.getElementById('btn-edit-accounts').click()")
    time.sleep(0.4)
    # 先清空再搜索 —— 不清空会残留上一次的选择
    cdp.ev("document.getElementById('btn-acc-clear').click()")
    time.sleep(0.2)
    cdp.ev(
        "(()=>{const i=document.getElementById('acc-search-input');"
        f"i.value='{PRODUCT['accounts'][0]} {PRODUCT['accounts'][1]}';"
        "document.getElementById('btn-acc-search').click();})()"
    )
    time.sleep(0.4)
    cdp.ev("document.getElementById('btn-acc-selectall').click()")
    time.sleep(0.3)
    cdp.shot(S("02-媒体账号-全选.png"))
    cdp.ev("document.getElementById('btn-acc-confirm').click()")
    time.sleep(0.4)
    print(f"    · 已选广告户 {PRODUCT['accounts']}（先清空→搜索→全选）")

    print("【步骤 3】广告基本信息（逐户设置）")
    cdp.ev("document.getElementById('btn-edit-basic').click()")
    time.sleep(0.5)

    def fill_basic(rand_id, shot_name):
        cdp.ev(f"document.getElementById('shop-select').value='{SHOP}'")
        cdp.ev(
            "(()=>{const i=document.getElementById('product-search-input');"
            f"i.value='{PRODUCT['name']}';"
            "document.getElementById('btn-product-search').click();})()"
        )
        time.sleep(0.4)
        cdp.ev("document.querySelectorAll('#product-list .rowitem')[0].click()")
        # 出价：12.7 → 12（截断，不四舍五入）
        cdp.ev(f"document.getElementById('bid-input').value='{PRODUCT['bid_fill']}'")
        cdp.ev(f"document.getElementById('plan-name-input').value='{plan_name(rand_id)}'")
        time.sleep(0.3)
        cdp.shot(S(shot_name))

    fill_basic("A7F3C1", "03-第1个广告户-已填.png")
    cdp.ev("document.getElementById('btn-basic-confirm').click()")
    time.sleep(0.6)
    # 关键：切到第二个户，商品库被静默重置 —— 这里必须重新选
    cdp.shot(S("04-切换第2户-商品库被重置.png"))
    print("    · 第 1 户已确定；切换后商品库被静默重置（截图留证）")

    fill_basic("B2E9D4", "05-第2个广告户-重新填写.png")
    cdp.ev("document.getElementById('btn-basic-confirm').click()")
    time.sleep(0.5)
    print("    · 第 2 户已确定（出价 12 = 12.7 截断）")

    print("【步骤 4】定向包 —— 按规则不动，保持默认")

    print("【步骤 5】创意基本信息 —— 小程序路径")
    cdp.ev("document.getElementById('btn-edit-creative').click()")
    time.sleep(0.4)
    cdp.ev("document.getElementById('jump-type-select').value='落地页'")
    # 故意先演示“直接追加”的错误做法：旧值 + 新值 拼接
    cdp.ev(
        "(()=>{const e=document.getElementById('path-editable');"
        f"e.textContent=e.textContent+'{PRODUCT['lp']}';}})()"
    )
    time.sleep(0.3)
    cdp.ev("document.getElementById('btn-creative-confirm').click()")
    time.sleep(0.4)
    cdp.shot(S("06-未先清空-校验失败.png"))
    print("    · 演示反面：直接粘贴 → 与旧值拼接 → 校验拦下（截图留证）")
    # 正确做法：先清空，再写入
    cdp.ev("document.getElementById('path-editable').textContent=''")
    time.sleep(0.2)
    cdp.ev(f"document.getElementById('path-editable').textContent='{PRODUCT['lp']}'")
    time.sleep(0.3)
    cdp.ev("document.getElementById('btn-creative-confirm').click()")
    time.sleep(0.4)
    cdp.shot(S("07-先清空再写入-校验通过.png"))
    print("    · 正确做法：先删后填 → 通过")

    print("【步骤 6】创意素材")
    cdp.ev("document.getElementById('btn-edit-material').click()")
    time.sleep(0.4)
    cdp.ev("document.getElementById('btn-add-material').click()")
    time.sleep(0.4)
    cdp.ev(
        "(()=>{const i=document.getElementById('folder-search');"
        f"i.value='{PRODUCT['id']}';"
        "document.getElementById('btn-folder-search').click();})()"
    )
    time.sleep(0.4)
    cdp.ev("document.getElementById('btn-material-all').click()")
    time.sleep(0.4)
    cdp.shot(S("08-素材-按商品ID检索并取全部.png"))
    cdp.ev("document.getElementById('btn-mat-confirm').click()")
    time.sleep(0.3)
    cdp.ev("document.getElementById('btn-material-confirm').click()")
    time.sleep(0.4)
    print("    · 按商品ID检索素材文件夹，取用上限 15 条（超出直接丢弃）")

    print("【生成】生成广告计划 → 提交")
    cdp.ev("document.getElementById('btn-generate').click()")
    time.sleep(0.5)
    cdp.shot(S("09-已生成计划草稿.png"))
    cdp.ev("document.getElementById('btn-submit').click()")
    time.sleep(0.5)
    cdp.shot(S("10-已提交.png"))
    print("    · 已生成并提交")

    state = json.loads(cdp.ev("JSON.stringify(window.__mock.dump())"))
    cdp.close()

    print("\n================ 运行结果 ================")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    ok = (state["rule"] and len(state["accounts"]) == 2 and state["shop"]
          and state["path"] == PRODUCT["lp"] and state["materials"]
          and state["generated"] and state["submitted"])
    print("\n结论：" + ("✅ 6 步全流程闭环通过" if ok else "❌ 存在未完成项"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
