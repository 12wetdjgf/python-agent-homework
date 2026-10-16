"""python grade.py [Q1|Q2]：按行为评分，未完成也能给出反馈。"""
import sys
from lesson01 import ScriptedModel, execute_tool, run_agent


def check_add():
    assert execute_tool({"name": "add", "arguments": {"a": 2, "b": 3}}) == 5, "加法结果应为 5"


def check_negative():
    assert execute_tool({"name": "add", "arguments": {"a": -4, "b": 1.5}}) == -2.5, "应支持负数和小数"


def check_unknown():
    try:
        execute_tool({"name": "missing", "arguments": {}})
    except ValueError as error:
        assert "missing" in str(error), "错误消息应包含工具名"
        return
    raise AssertionError("未知工具应抛出 ValueError")


def check_direct():
    model = ScriptedModel([{"role": "assistant", "content": "你好"}])
    answer, messages = run_agent(model, "hi")
    assert answer == "你好", "无工具调用时应返回文本"
    assert messages == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "你好"}], "消息应保留用户输入和模型回复"
    assert len(model.seen) == 1, "最终文本之后应停止"


def check_roundtrip():
    call = {"role": "assistant", "tool_call": {"name": "add", "arguments": {"a": 7, "b": 8}}}
    final = {"role": "assistant", "content": "15"}
    model = ScriptedModel([call, final])
    answer, messages = run_agent(model, "7+8")
    tool = {"role": "tool", "name": "add", "content": "15"}
    assert answer == "15", "应返回最终回复"
    assert messages == [{"role": "user", "content": "7+8"}, call, tool, final], "应保留完整调用轨迹"
    assert model.seen[1] == messages[:3], "第二轮模型必须收到工具结果"


def check_multiple():
    model = ScriptedModel([
        {"role": "assistant", "tool_call": {"name": "add", "arguments": {"a": 1, "b": 2}}},
        {"role": "assistant", "tool_call": {"name": "add", "arguments": {"a": 3, "b": 4}}},
        {"role": "assistant", "content": "7"},
    ])
    answer, messages = run_agent(model, "两次计算")
    assert answer == "7" and len(model.seen) == 3, "应支持连续两轮工具调用"
    assert [m["content"] for m in messages if m["role"] == "tool"] == ["3", "7"], "两次工具结果都应保留"


def check_budget():
    call = {"role": "assistant", "tool_call": {"name": "add", "arguments": {"a": 1, "b": 1}}}
    model = ScriptedModel([call, call, call])
    try:
        run_agent(model, "一直调用", max_steps=2)
    except NotImplementedError:
        raise
    except RuntimeError:
        assert len(model.seen) == 2, "最多调用模型两次"
        return
    raise AssertionError("达到步数上限应抛出 RuntimeError")


def check_invalid_budget():
    for limit in (0, -1):
        model = ScriptedModel([])
        try:
            run_agent(model, "hi", max_steps=limit)
        except ValueError:
            assert not model.seen, "无效预算不应调用模型"
        else:
            raise AssertionError("非正步数应抛出 ValueError")


CASES = [
    ("Q1", 15, "基础工具调用", check_add),
    ("Q1", 10, "负数与小数", check_negative),
    ("Q1", 15, "未知工具反馈", check_unknown),
    ("Q2", 10, "直接回答与停止", check_direct),
    ("Q2", 20, "工具结果回传与消息顺序", check_roundtrip),
    ("Q2", 10, "连续工具调用", check_multiple),
    ("Q2", 10, "步数上限", check_budget),
    ("Q2", 10, "无效步数", check_invalid_budget),
]


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, "Q1", "Q2"):
        print("用法：python grade.py [Q1|Q2]")
        return 2
    earned = possible = 0
    for question, points, label, check in CASES:
        if selected and question != selected:
            continue
        possible += points
        try:
            check()
        except Exception as error:
            print(f"[待完成] {question} {label} 0/{points}：{type(error).__name__}: {error}")
        else:
            earned += points
            print(f"[通过] {question} {label} {points}/{points}")
    print(f"总分：{earned}/{possible}")
    return 0 if earned == possible else 1


if __name__ == "__main__":
    sys.exit(main())
