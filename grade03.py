"""第三课离线评分，不读取密钥、不联网。"""
from copy import deepcopy
import sys
import lesson03 as student
from lesson02 import run_agent


def check_user():
    original = {'role': 'user', 'content': '你好'}
    result = student.to_api_message(original)
    assert result == original and result is not original, '返回新的用户消息字典'


def check_tool():
    source = {'role': 'tool', 'name': 'add', 'tool_call_id': 'sum_9', 'content': '42'}
    result = student.to_api_message(source)
    assert result == {'role': 'tool', 'tool_call_id': 'sum_9', 'content': '42'}, '工具消息应保留 ID，去掉 name'
    assert source['name'] == 'add', '不要修改原消息'


def check_assistant():
    source = {'role': 'assistant', 'tool_calls': [
        {'id': 'one', 'name': 'add', 'arguments_json': '{"a":1,"b":2}'},
        {'id': 'two', 'name': 'add', 'arguments_json': '{"a":3,"b":4}'},
    ]}
    snapshot = deepcopy(source)
    result = student.to_api_message(source)
    assert result['role'] == 'assistant' and result['content'] is None
    calls = result['tool_calls']
    assert len(calls) == 2, '保留所有工具调用'
    for actual, expected in zip(calls, source['tool_calls']):
        assert actual == {'id': expected['id'], 'type': 'function', 'function': {'name': expected['name'], 'arguments': expected['arguments_json']}}, '检查嵌套 function 和 arguments 字段'
    assert source == snapshot, '不要修改原调用'


def check_plain():
    assert student.to_api_message({'role': 'assistant', 'content': '完成', 'tool_calls': []}) == {'role': 'assistant', 'content': '完成'}, '空调用应当省略'


def check_role():
    try:
        student.to_api_message({'role': 'unexpected', 'content': 'x'})
    except ValueError as error:
        assert 'unexpected' in str(error)
        return
    raise AssertionError('不支持的 role 应抛 ValueError')


def check_reply_text():
    assert student.from_api_message({'role': 'assistant', 'content': '完成', 'tool_calls': None}) == {'role': 'assistant', 'content': '完成'}, 'None 调用应按空列表处理'
    assert student.from_api_message({'role': 'assistant', 'content': None})['content'] == '', 'None 文本归一为空字符串'


def check_reply_calls():
    source = {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'a', 'type': 'function', 'function': {'name': 'add', 'arguments': '{"a":5,"b":6}'}},
        {'id': 'b', 'type': 'function', 'function': {'name': 'add', 'arguments': '{"a":7,"b":8}'}},
    ]}
    snapshot = deepcopy(source)
    result = student.from_api_message(source)
    assert result == {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': 'a', 'name': 'add', 'arguments_json': '{"a":5,"b":6}'},
        {'id': 'b', 'name': 'add', 'arguments_json': '{"a":7,"b":8}'},
    ]}, '保留多个 ID，并保持参数为字符串'
    assert source == snapshot, '不要修改供应商回复'


def check_type():
    try:
        student.from_api_message({'role': 'assistant', 'tool_calls': [{'id': 'x', 'type': 'custom'}]})
    except ValueError as error:
        assert 'custom' in str(error)
        return
    raise AssertionError('本课不支持的工具类型应抛 ValueError')


def check_roundtrip():
    seen = []
    def fake_transport(payload):
        seen.append(deepcopy(payload))
        assert payload['model'] == 'fixture-model' and payload['stream'] is False
        assert payload['tools'][0]['type'] == 'function'
        assert payload['tools'][0]['function']['name'] == 'add'
        if len(seen) == 1:
            message = {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'sum', 'type': 'function', 'function': {'name': 'add', 'arguments': '{"a":17,"b":25}'}}
            ]}
        else:
            history = payload['messages']
            assert history[-2]['tool_calls'][0]['id'] == 'sum', '第二次请求应保留先前调用'
            assert history[-1] == {'role': 'tool', 'tool_call_id': 'sum', 'content': '42'}, '第二次请求必须回传真实工具结果'
            message = {'role': 'assistant', 'content': history[-1]['content']}
        return {'choices': [{'message': message, 'finish_reason': 'stop'}]}
    model = student.ChatCompletionsModel('https://example.invalid/v1', 'offline-placeholder', 'fixture-model', transport=fake_transport)
    answer, history = run_agent(model, '17+25')
    assert answer == '42' and len(seen) == 2 and len(history) == 4, '检查适配器与已有循环往返'


CASES = [
    ('Q1', 5, '用户消息', check_user),
    ('Q1', 10, '工具结果与 ID', check_tool),
    ('Q1', 20, '多个嵌套工具调用', check_assistant),
    ('Q1', 5, '文本回复', check_plain),
    ('Q1', 5, '未知角色反馈', check_role),
    ('Q2', 10, '文本与空调用', check_reply_text),
    ('Q2', 20, '回复转换与参数字符串', check_reply_calls),
    ('Q2', 10, '未知工具类型', check_type),
    ('ALL', 15, '模拟接口完整往返', check_roundtrip),
]


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q1', 'Q2'):
        print('用法：python -X utf8 grade03.py [Q1|Q2]')
        return 2
    earned = possible = 0
    for question, points, label, check in CASES:
        if selected and selected != question:
            continue
        possible += points
        try:
            check()
        except Exception as error:
            print(f'[待完成] {question} {label} 0/{points}：{type(error).__name__}: {error}')
        else:
            earned += points
            print(f'[通过] {question} {label} {points}/{points}')
    print(f'总分：{earned}/{possible}')
    return 0 if earned == possible else 1


if __name__ == '__main__':
    sys.exit(main())
