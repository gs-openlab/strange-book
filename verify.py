#!/usr/bin/env python3
"""自检 booklang.py：先用已知答案的经典程序校验语义，再跑三道题。

用法：python3 verify.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from booklang import BookLangError, Machine  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# 已知答案的经典 Brainfuck 片段，用来确认解释器在算术、循环、输入、单元移动、
# 256 回绕这些方面都没有偏差。
SELFTEST = [
    ("++++++++++[>++++++++++<-]>.", "", "d", "10x10=100='d'"),
    ("+++++[>+++++++++++<-]>.", "", "7", "5x11=55='7'"),
    (",[->+<]>.", "A", "A", "把输入搬到下一格再输出"),
    ("+" * 65 + ".", "", "A", "65 个 + = 'A'"),
    ("-" + ".", "", chr(255), "0-1 回绕成 255"),
    ("+" * 256 + ".", "", chr(0), "256 回绕成 0"),
    ("+++.>++.>+.", "", "\x03\x02\x01", "多单元各自累加"),
    ("[]+++++.", "", "\x05", "空循环体：条件为真时进不去"),
]


def run(code: str, inputs: str = "", literal: bool = False) -> str:
    return Machine(code, inputs, literal_brackets=literal).run()


def section(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def main() -> int:
    failed = 0

    section("一、解释器自检（经典程序，答案已知）")
    for code, inputs, want, note in SELFTEST:
        got = run(code, inputs)
        ok = got == want
        failed += 0 if ok else 1
        print(f"{'OK  ' if ok else 'FAIL'} {note}\n"
              f"     程序 {code!r} 输入 {inputs!r}\n"
              f"     得 {got!r}，期望 {want!r}")

    # 两种括号模型必须完全等价
    section("二、括号执行模型等价性（skip vs literal）")
    for name in ("page1", "page2"):
        code = open(os.path.join(HERE, "programs", f"{name}.book"), encoding="utf-8").read()
        for inputs in ("C", "\x00", "A"):
            a, b = run(code, inputs), run(code, inputs, literal=True)
            ok = a == b
            failed += 0 if ok else 1
            print(f"{'OK  ' if ok else 'FAIL'} {name}.book 输入 {inputs!r}："
                  f"skip -> {a!r}，literal -> {b!r}")

    section("三、第一页")
    code1 = open(os.path.join(HERE, "programs", "page1.book"), encoding="utf-8").read()
    for ch in ("C", "c", "A", "\x00", "1"):
        m = Machine(code1, ch)
        out = m.run()
        print(f"输入 {ch!r} (ASCII {ord(ch)}) -> {m.dump().splitlines()[-1]}")

    section("四、第二页")
    code2 = open(os.path.join(HERE, "programs", "page2.book"), encoding="utf-8").read()
    m = Machine(code2, "")
    out = m.run()
    print(m.dump())
    print(f"输出字符共 {len(out)} 个：" + " ".join(f"{c!r}" for c in out))
    print("十六进制：" + " ".join(f"{ord(c):02x}" for c in out))

    section("五、第三页（和为 65 与 90 的两种输入）")
    code3 = open(os.path.join(HERE, "programs", "page3-sum.book"), encoding="utf-8").read()
    for inp, want_code in (("AZ", 155), ("AB", 131), ("\x00A", 65)):
        m = Machine(code3, inp)
        out = m.run()
        got_code = ord(out) if out else None
        ok = got_code == want_code
        failed += 0 if ok else 1
        print(f"{'OK  ' if ok else 'FAIL'} 输入 {inp!r} -> 输出 {out!r} (ASCII {got_code})，"
              f"期望 ASCII {want_code} = {chr(want_code)!r}")

    section("六、第三页打印最大和 510 时的回绕")
    m = Machine(code3, chr(255) + chr(255))
    out = m.run()
    print(f"输入 '\\xff\\xff' -> 和 510，输出 ASCII {ord(out)} = {out!r}（510 mod 256 = 254）")

    # 题面注「假设所有 ASCII 码表中的字符皆可输入」=> 输入应覆盖 0–255 的全部取值。
    section("七、第三页穷举：256x256 组输入全部等于「和 mod 256」")
    bad = []
    total = 0
    for a in range(256):
        for b in range(256):
            total += 1
            m = Machine(code3, chr(a) + chr(b))
            out = m.run()
            if len(out) != 1 or ord(out) != (a + b) % 256:
                bad.append((a, b, out))
    print(f"共 {total} 组，不符 {len(bad)} 组" + (f"：{bad[:5]}" if bad else ""))
    failed += 0 if not bad else 1

    print(f"\n{'全部通过' if failed == 0 else f'{failed} 项不符'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
