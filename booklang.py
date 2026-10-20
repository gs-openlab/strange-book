#!/usr/bin/env python3
"""《奇怪的书》8 关键字语言的解释器。

关键字（照抄题面）：
    +  指针所指单元值 +1
    -  指针所指单元值 -1
    >  指针向右移动一格
    <  指针向左移动一格
    [  若指针所指单元值为 0，程序跳转到向后最近的 ] 位置（即跳过循环体）
    ]  若指针所指单元值非 0，程序跳转到向前最近的 [ 位置（即回到循环体开头）
    .  输出指针所指向单元的值作为 ASCII 值对应的字符
    ,  输入一个字符，将其 ASCII 值赋给指针指向的单元

单元：数量不限（用到哪格才算出哪格），初值 0，取值 0–255，超出即按 256 回绕。
指针：初始指向 0 号单元。

用法：
    python3 booklang.py programs/page1.book -i C -t      # 读入 'C'，逐条打印指令后的状态
    python3 booklang.py programs/page2.book -d           # 运行并导出末态
    python3 booklang.py programs/page3-sum.book -i AB    # 读入 'A'、'B'
    python3 booklang.py programs/page1.book -x 00 -d     # 输入 ASCII 0（十六进制给法）

括号的执行模型：
    skip（默认）——`[` 判定成立（单元为 0）时直接跳到配对 `]` 之后；`]` 判定成立（单元
        非 0）时直接跳到配对 `[` 之内（循环体第一条指令）。
    literal——严格照题面字面：跳到括号本身的位置，让那条括号指令再判一次。由于跳转时
        被跳到的括号条件必然为假，两种模型的行为完全相同，只是 literal 多走一步。

程序输出写 stdout（按字节写出，故码值 128–255 不会经 UTF-8 重编码）；
-t/-d 的跟踪与末态写 stderr，故 stdout 可直接管道给别的工具。
"""

from __future__ import annotations

import argparse
import sys

OPS = "+-<>[],."
WRAP = 256


class BookLangError(Exception):
    """程序本身的问题：括号不配对、指针越界、步数超限。"""


def strip_code(text: str) -> str:
    """滤掉空白与注释，只留下关键字。"""
    return "".join(ch for ch in text if ch in OPS)


def match_brackets(code: str) -> dict[int, int]:
    """给每个 [ 找到配对的 ]（反之亦然），返回 {下标: 配对下标}。"""
    stack: list[int] = []
    match: dict[int, int] = {}
    for i, ch in enumerate(code):
        if ch == "[":
            stack.append(i)
        elif ch == "]":
            if not stack:
                raise BookLangError(f"第 {i} 个字符处的 ] 没有配对的 [")
            j = stack.pop()
            match[i] = j
            match[j] = i
    if stack:
        raise BookLangError(f"第 {stack[-1]} 个字符处的 [ 没有配对的 ]")
    return match


def parse_hex_input(text: str) -> str:
    """把 "41 42" 这样的十六进制串解析成字符序列（每字节一字符）。"""
    digits = "".join(ch for ch in text if ch not in " \t\n,_")
    if digits[:2].lower() == "0x":
        digits = digits[2:]
    if not digits or len(digits) % 2 or any(c not in "0123456789abcdefABCDEF" for c in digits):
        raise BookLangError("--hex-input 需要偶数个十六进制数字，例如 41 42")
    return bytes.fromhex(digits).decode("latin-1")


class Machine:
    """一台执行 booklang 程序的机器。

    传入的源码会先过一遍 `strip_code`：空白与注释不进指令流。
    """

    def __init__(self, code: str, inputs: str = "", *,
                 max_steps: int = 1_000_000, trace: bool = False,
                 literal_brackets: bool = False) -> None:
        self.code = strip_code(code)
        self.match = match_brackets(self.code)
        self.inputs = inputs
        self.max_steps = max_steps
        self.trace = trace
        self.literal_brackets = literal_brackets
        self.ip = 0
        self.ptr = 0
        self.cells: dict[int, int] = {}
        self.out: list[str] = []
        self.in_pos = 0
        self.steps = 0
        self.trace_lines: list[str] = []

    # --- 单元读写：值域 0–255，超出即回绕 ---
    def get(self) -> int:
        return self.cells.get(self.ptr, 0)

    def set(self, value: int) -> None:
        self.cells[self.ptr] = value % WRAP

    def read_input(self) -> int:
        if self.in_pos >= len(self.inputs):
            return 0  # 输入耗尽：题面未定义，按「读到 0」处理
        code_point = ord(self.inputs[self.in_pos])
        self.in_pos += 1
        return code_point

    def run(self) -> str:
        code = self.code
        while self.ip < len(code):
            if self.steps >= self.max_steps:
                raise BookLangError(f"已执行 {self.steps} 步仍未结束，疑似死循环")
            op = code[self.ip]
            nxt = self.ip + 1
            if op == "+":
                self.set(self.get() + 1)
            elif op == "-":
                self.set(self.get() - 1)
            elif op == ">":
                self.ptr += 1
            elif op == "<":
                if self.ptr == 0:
                    raise BookLangError("指针被移出 0 号单元的左侧（题面未定义）")
                self.ptr -= 1
            elif op == "[":
                if self.get() == 0:
                    nxt = self.match[self.ip] if self.literal_brackets else self.match[self.ip] + 1
            elif op == "]":
                if self.get() != 0:
                    nxt = self.match[self.ip] if self.literal_brackets else self.match[self.ip] + 1
            elif op == ".":
                self.out.append(chr(self.get()))
            elif op == ",":
                self.set(self.read_input())
            self.steps += 1
            if self.trace:
                self.trace_lines.append(self.describe(self.ip, op))
            self.ip = nxt
        return "".join(self.out)

    def describe(self, ip: int, op: str) -> str:
        cell = self.get()
        nonzero = " ".join(f"{k}:{v}" for k, v in sorted(self.cells.items()) if v) or "（全零）"
        shown = str(cell)
        if op in ".,":
            shown += f" ('{chr(cell)}')" if 32 <= cell < 127 else f" (码 {cell})"
        return (f"步 {self.steps:>3}  ip={ip:<3} 指令 {op}  ptr={self.ptr:<2}"
                f"  当前单元 {shown:<10} 非零单元 {nonzero}")

    def dump(self) -> str:
        nonzero = [(k, v) for k, v in sorted(self.cells.items()) if v]
        codes = [ord(c) for c in self.out]
        return "\n".join([
            f"执行步数：{self.steps}",
            f"指针位置：{self.ptr}",
            "末态非零单元：" + ("; ".join(f"{k}={v}" for k, v in nonzero) if nonzero else "无（全部为 0）"),
            f"输出：{''.join(self.out)!a}  ASCII 码 {codes}",
        ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="booklang.py",
        description="《奇怪的书》8 关键字语言（+ - > < [ ] . ,）的解释器。",
        epilog="程序输出写 stdout（按字节写出）；-t/-d 的跟踪与末态写 stderr。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("program", help="程序文件；用 - 表示从 stdin 读取")
    parser.add_argument("-i", "--input", help="供 , 读入的字符序列（默认读 stdin）")
    parser.add_argument("-x", "--hex-input", metavar="HEX",
                        help="同上，但以十六进制给出（如 41 42），便于传入不可见字符")
    parser.add_argument("-t", "--trace", action="store_true", help="逐条打印被执行的指令及其后的状态")
    parser.add_argument("-d", "--dump", action="store_true", help="结束时打印步数、指针、非零单元与输出码")
    parser.add_argument("-s", "--max-steps", type=int, default=1_000_000, help="步数上限，超出即报错（默认 1000000）")
    parser.add_argument("-b", "--bracket-model", choices=("skip", "literal"), default="skip",
                        help="括号执行模型：skip=跳到括号之后（默认），literal=照题面字面跳到括号位置再判定")
    args = parser.parse_args(argv)

    if args.input is not None and args.hex_input is not None:
        parser.error("--input 与 --hex-input 只能给一个")

    if args.program == "-":
        source = sys.stdin.read()
        inputs = args.input if args.input is not None else ""
    else:
        with open(args.program, encoding="utf-8") as handle:
            source = handle.read()
        if args.hex_input is not None:
            inputs = parse_hex_input(args.hex_input)
        elif args.input is not None:
            inputs = args.input
        elif sys.stdin.isatty():
            inputs = ""  # 不去读终端，避免卡住；, 会立刻读到「结束」
        else:
            inputs = sys.stdin.read()

    machine = Machine(source, inputs, max_steps=args.max_steps,
                      trace=args.trace, literal_brackets=(args.bracket_model == "literal"))
    try:
        result = machine.run()
    except BookLangError as exc:
        sys.stderr.write(f"错误：{exc}\n")
        if args.dump:
            sys.stderr.write(machine.dump() + "\n")
        return 1

    sys.stdout.buffer.write(result.encode("latin-1"))
    sys.stdout.buffer.flush()
    if args.trace:
        sys.stderr.write("\n".join(machine.trace_lines) + "\n")
    if args.dump:
        sys.stderr.write(machine.dump() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
