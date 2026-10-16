"""python -X utf8 grade02.py [Q1|Q2]。第二课行为评分。"""
import json
import sys
import lesson02 as student


def schema_identity():
    schema = student.build_tool_schema()
    assert schema['name'] == 'add', '工具名必须与执行注册表一致'
    assert isinstance(schema['description'], str) and schema['description'].strip(), '需要非空工具说明'


def schema_arguments():
    params = student.build_tool_schema()['parameters']
    assert params['type'] == 'object', '参数整体应为对象'
    for key in ('a', 'b'):
        assert params['properties'][key]['type'] == 'number', f'{key} 应接受整数和小数'
    assert set(params['properties']) == {'a', 'b'}, '只定义 a 和 b'


def schema_constraints():
    schema = student.build_tool_schema()
    params = schema['parameters']
    assert sorted(params['required']) == ['a', 'b'], 'a、b 都必须提供'
    assert params['additionalProperties'] is False, '不接受说明书之外的参数'
    json.dumps(schema)  # 说明书必须可以传输为 JSON，不能包含 Python 函数。


def result_basic():
    call = {'id': 'call_7', 'name': 'add', 'arguments_json': '{"a": 2, "b": 3}'}
    result = student.make_tool_result(call)
    assert result == {'role': 'tool', 'tool_call_id': 'call_7', 'name': 'add', 'content': '5'}, '工具消息的内容、角色、名称或 ID 不正确'
    assert call == {'id': 'call_7', 'name': 'add', 'arguments_json': '{"a": 2, "b": 3}'}, '不要修改原调用'


def result_decimal():
    result = student.make_tool_result({'id': 'decimal', 'name': 'add', 'arguments_json': '{"a": -2, "b": 0.5}'})
    assert result['content'] == '-1.5', '必须解析并执行参数，不可把答案写死'


def invalid_json():
    try:
        student.make_tool_result({'id': 'bad', 'name': 'add', 'arguments_json': '{broken'})
    except json.JSONDecodeError:
        return
    raise AssertionError('坏 JSON 必须抛出 JSONDecodeError')


def unknown_tool():
    try:
        student.make_tool_result({'id': 'unknown', 'name': 'missing', 'arguments_json': '{}'})
    except ValueError as error:
        assert 'missing' in str(error), '反馈应包含未知工具名'
        return
    raise AssertionError('必须复用工具分发的未知工具反馈')


def correlation():
    calls = [
        {'id': 'first', 'name': 'add', 'arguments_json': '{"a": 1, "b": 2}'},
        {'id': 'second', 'name': 'add', 'arguments_json': '{"a": 10, "b": 20}'},
    ]
    results = [student.make_tool_result(call) for call in calls]
    assert [(r['tool_call_id'], r['content']) for r in results] == [('first', '3'), ('second', '30')], '同名工具的两次调用也要用不同 ID 匹配'


CASES = [
    ('Q1', 10, '工具名称与说明', schema_identity),
    ('Q1', 15, '参数结构与数值类型', schema_arguments),
    ('Q1', 15, '必填字段与 JSON 传输', schema_constraints),
    ('Q2', 20, '执行工具并构造结果', result_basic),
    ('Q2', 10, '负数与小数参数', result_decimal),
    ('Q2', 10, '坏 JSON 反馈', invalid_json),
    ('Q2', 10, '未知工具反馈', unknown_tool),
    ('Q2', 10, '多个调用的 ID 对应', correlation),
]


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q1', 'Q2'):
        print('用法：python -X utf8 grade02.py [Q1|Q2]')
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
