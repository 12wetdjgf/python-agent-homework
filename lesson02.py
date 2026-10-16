"""第二课：工具说明书、JSON 参数、调用 ID。

这里的扁平 tool_calls 是自定义教学协议，不是供应商 API 原始格式。
本课离线运行；真实模型适配器会把供应商响应转换成此格式。
"""
import json
from copy import deepcopy
from lesson01 import execute_tool


def build_tool_schema():
    """Q1（40分）：返回 add 的工具说明书（字典）。

    顶层字段：name='add'、description=非空的加法说明、parameters。
    parameters 是 JSON Schema：
      type='object'
      properties：a、b 都是 {'type': 'number'}
      required：['a', 'b']（顺序不限）
      additionalProperties=False
    提示：返回嵌套字典即可；number 包含整数和小数。
    注意：说明书描述参数约定，本身不会替你执行 Python 参数校验。
    """
    # COURSE_TODO(Q1)
    return {
        'name': 'add',
        'description': '计算两个数值相加的和。',
    'parameters': {
            'type': 'object',
            'properties': {
                'a': {'type': 'number'},
                'b': {'type': 'number'},
            },
            'required': ['a', 'b'],
            'additionalProperties': False,
        }
    }


def make_tool_result(call):
    """Q2（60分）：解析参数，复用第一课工具分发，返回带 ID 的结果。

    call 示例：
      {'id': 'call_1', 'name': 'add', 'arguments_json': '{"a": 2, "b": 3}'}
    步骤：
      1. json.loads 将 arguments_json 字符串转成参数字典。
      2. 调用第一课 execute_tool，传入 name 和 arguments。
      3. 返回 {'role': 'tool', 'tool_call_id': 原调用ID,
               'name': 原工具名, 'content': str(执行结果)}。
    保留 ID 原值；不能每次都写成 call_1。
    坏 JSON 应自然抛出 json.JSONDecodeError；未知工具的 ValueError 向上传递。
    本课假定 id/name 存在，参数对象符合说明书；完整运行时校验留到后续。
    """
    # COURSE_TODO(Q2)
    args = json.loads(call['arguments_json'])
    result = execute_tool({
        'name': call['name'],
        'arguments': args
    })
    return {
        'role': 'tool',
        'tool_call_id': call['id'],
        'name': call['name'],
        'content': str(result)
    }

class ResultAwareModel:
    """确定性的测试替身：第一轮提出调用，第二轮从工具消息读取结果。

    它不理解自然语言。算式由构造函数提供，不从 user_text 提取。
    """

    def __init__(self, a=2, b=3):
        self.a, self.b = a, b
        self.seen = []

    def respond(self, messages, tools):
        self.seen.append(deepcopy(messages))
        if not any(tool.get('name') == 'add' for tool in tools):
            raise ValueError('模型没有收到 add 的工具说明书')
        if len(self.seen) == 1:
            return {'role': 'assistant', 'tool_calls': [
                {'id': 'sum_001', 'name': 'add',
                 'arguments_json': json.dumps({'a': self.a, 'b': self.b})}
            ]}
        results = [m for m in messages if m.get('role') == 'tool'
                   and m.get('tool_call_id') == 'sum_001']
        if len(results) != 1:
            raise ValueError('缺少匹配 sum_001 的工具结果')
        return {'role': 'assistant', 'content': '计算结果是 ' + results[0]['content']}


def run_agent(model, user_text, max_steps=5):
    """本课提供循环；关注与第一课不同的 tools 参数和多个调用。"""
    if max_steps <= 0:
        raise ValueError('max_steps 要大于 0')
    messages = [{'role': 'user', 'content': user_text}]
    tools = [build_tool_schema()]
    for _ in range(max_steps):
        reply = model.respond(messages, tools)
        messages.append(reply)
        calls = reply.get('tool_calls', [])
        if not calls:
            return reply['content'], messages
        # 同一轮有多个调用：每个结果都必须保留对应 ID。
        for call in calls:
            messages.append(make_tool_result(call))
    raise RuntimeError('模型调用步数超上限')


if __name__ == '__main__':
    answer, history = run_agent(ResultAwareModel(2, 3), '帮我算 2 + 3')
    for message in history:
        print(json.dumps(message, ensure_ascii=False))
    print(answer)
