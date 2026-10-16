"""第四课接线评分，不联网、不读取本机接口配置。"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import lesson04_agent as student
from lesson03 import ChatCompletionsModel


def main():
    course = Path(__file__).parent.resolve()
    with TemporaryDirectory(prefix='agent-wire-tests-', dir=course) as directory:
        fixture = Path(directory).resolve()
        assert fixture.is_relative_to(course)
        root = fixture / 'sandbox'
        root.mkdir()
        content = '本次测试文件中的答案是 73。'
        (root / 'notes.txt').write_text(content, encoding='utf-8')
        (fixture / 'outside.txt').write_text('outside fixture', encoding='utf-8')

        def call(name='read_text_file', arguments=None, id='read_7'):
            return {'id': id, 'name': name, 'arguments_json': json.dumps(arguments if arguments is not None else {'path': 'notes.txt'})}

        def expect_value_error(action):
            try:
                action()
            except ValueError:
                return
            raise AssertionError('应拒绝该工具或参数')

        def read_result():
            original = call()
            before = deepcopy(original)
            assert student.execute_read_call(original, root=root) == {'role': 'tool', 'name': 'read_text_file', 'tool_call_id': 'read_7', 'content': content}, '检查参数映射、文件文本和调用 ID'
            assert original == before, '不要修改原调用'

        def unknown():
            expect_value_error(lambda: student.execute_read_call(call(name='add'), root=root))

        def bad_arguments():
            for args in ([], {'path': 'notes.txt', 'root': str(fixture)}, {}):
                expect_value_error(lambda: student.execute_read_call(call(arguments=args), root=root))

        def escape():
            expect_value_error(lambda: student.execute_read_call(call(arguments={'path': '../outside.txt'}), root=root))

        def roundtrip():
            requests = []
            def fake_transport(payload):
                requests.append(deepcopy(payload))
                assert payload['tools'][0]['function']['name'] == 'read_text_file'
                if len(requests) == 1:
                    message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'file_1', 'type': 'function', 'function': {'name': 'read_text_file', 'arguments': '{"path":"notes.txt"}'}}]}
                else:
                    last = payload['messages'][-1]
                    assert last == {'role': 'tool', 'tool_call_id': 'file_1', 'content': content}, '真实读取内容必须发回模拟接口'
                    message = {'role': 'assistant', 'content': last['content']}
                return {'choices': [{'message': message, 'finish_reason': 'stop'}]}
            model = ChatCompletionsModel('https://example.invalid/v1', 'offline', 'fixture', transport=fake_transport)
            answer, history = student.run_file_agent(model, '读取文件', root=root)
            assert answer == content and len(requests) == 2 and len(history) == 4

        cases = [(30, '文件读取与 ID 回传', read_result), (10, '未知工具', unknown),
                 (20, '限制模型可传入的参数', bad_arguments), (10, '路径边界仍然有效', escape),
                 (30, '模拟接口完整往返', roundtrip)]
        score = 0
        for points, label, check in cases:
            try:
                check()
            except Exception as error:
                print(f'[待完成] {label} 0/{points}：{type(error).__name__}: {error}')
            else:
                score += points
                print(f'[通过] {label} {points}/{points}')
        print(f'接线题总分：{score}/100')
        return 0 if score == 100 else 1


if __name__ == '__main__':
    raise SystemExit(main())
