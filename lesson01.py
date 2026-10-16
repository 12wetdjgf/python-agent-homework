"""第一课：教学协议，不是某家模型 API 的原始消息格式。"""
from copy import deepcopy


def add(a, b):
    return a + b


TOOLS = {"add": add}


class ScriptedModel:
    """按事先写好的剧本返回消息，方便观察循环；它不是语言模型。"""

    def __init__(self, responses):
        self.responses = deepcopy(responses)
        self.seen = []

    def respond(self, messages):
        self.seen.append(deepcopy(messages))
        if not self.responses:
            raise RuntimeError("剧本用完了：检查 agent 是否正确停止")
        return self.responses.pop(0)


def execute_tool(call):

    """Q1（40分）：call 示例 {name: 'add', arguments: {a: 2, b: 3}}。

    找到 TOOLS 中的函数，把 arguments 字典作为关键字参数传给它。
    返回函数的结果。未知工具应抛出 ValueError，消息包含工具名。
    提示：字典索引、**kwargs。不要使用 eval。
    """
    # COURSE_TODO(Q1)
    tool_name = call.get("name")
    if tool_name not in TOOLS:
        raise ValueError(f"未知错误工具:{tool_name}")
    func = TOOLS[tool_name]
    arguments = call.get("arguments",{})
    return func(**arguments)


def run_agent(model, user_text, max_steps=5):
    """Q2（60分）：返回 (最终文本, 完整消息列表)。

    初始消息：{'role': 'user', 'content': user_text}。
    每轮：model.respond(messages)，将模型返回的消息加入列表。
    如果消息不含 tool_call，就返回 content 和 messages。
    否则执行 execute_tool(reply['tool_call'])，追加工具消息：
        {'role': 'tool', 'name': 工具名, 'content': str(工具结果)}
    再开始下一轮。max_steps 是模型调用次数的上限；耗尽时抛 RuntimeError。
    max_steps <= 0 时抛 ValueError；工具异常暂时直接向上传递。
    本课每轮只允许一个工具调用。
    """
    # COURSE_TODO(Q2)
    if max_steps <= 0:
        raise ValueError("max_steps要大于0")
    messages = [{"role":"user","content":user_text}]
    for _ in range(max_steps):
        reply = model.respond(messages)
        messages.append(reply)
        if "tool_call" not in reply:
            return reply.get("content"),messages
        tool_call = reply["tool_call"]
        result = execute_tool(tool_call)
        tool_message = {
            "role":"tool",
            "name": tool_call["name"],
            "content": str(result)
        }
        messages.append(tool_message)
    
    raise RuntimeError("步数超上限")

def main():
    model = ScriptedModel([
        {"role": "assistant", "tool_call": {"name": "add", "arguments": {"a": 2, "b": 3}}},
        {"role": "assistant", "content": "计算结果是 5"},
    ])
    answer, messages = run_agent(model, "帮我算 2 + 3")
    for message in messages:
        print(message)
    print("最终回答：", answer)


if __name__ == "__main__":
    main()
