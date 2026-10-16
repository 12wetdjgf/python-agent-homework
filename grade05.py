"""第五课第一部分行为评分；不联网、不读取接口配置。"""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import lesson05 as student
from lesson01 import ScriptedModel


class Model(ScriptedModel):
    def respond(self, messages, tools):
        assert tools[0]['name'] == 'read_text_file'
        return super().respond(messages)


def call(path='notes.txt', id='read_1', name='read_text_file'):
    return {'id': id, 'name': name, 'arguments_json': json.dumps({'path': path})}


def reply(*calls):
    return {'role': 'assistant', 'tool_calls': list(calls)}


def expect(error_type, action, feedback):
    try:
        action()
    except error_type:
        return
    raise AssertionError(feedback)


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q1', 'Q2'):
        print('用法：python -X utf8 grade05.py [Q1|Q2]')
        return 2
    course = Path(__file__).parent.resolve()
    with TemporaryDirectory(prefix='agent-errors-tests-', dir=course) as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(course)
        (root / 'notes.txt').write_text('第五课练习文本', encoding='utf-8')
        (root / 'binary.bin').write_bytes(b'\xff')

        def check_result(c, code=None):
            result = student.safe_read_call(c, root=root)
            assert result['role'] == 'tool' and result['tool_call_id'] == c['id'] and result['name'] == c['name']
            payload = json.loads(result['content'])
            if code:
                assert payload == {'ok': False, 'error': {'code': code, 'message': student.ERROR_MESSAGES[code]}}, '检查错误分类及固定反馈消息'
                assert str(root) not in result['content'], '不要泄露绝对路径'
            else:
                assert payload == {'ok': True, 'text': '第五课练习文本'}

        def success():
            check_result(call())

        def missing():
            check_result(call('missing.txt', id='missing'), 'not_found')

        def classification():
            c = call()
            c['arguments_json'] = '{broken'
            check_result(c, 'invalid_json')
            check_result(call('binary.bin'), 'invalid_encoding')
            check_result(call('../outside.txt'), 'invalid_request')

        def io_and_program_errors():
            original = student.execute_read_call
            try:
                for error, code in ((PermissionError('private path'), 'permission_denied'), (OSError('private path'), 'io_error')):
                    def failing(*args, **kwargs):
                        raise error
                    student.execute_read_call = failing
                    check_result(call(), code)
                def broken(*args, **kwargs):
                    raise KeyError('programming bug')
                student.execute_read_call = broken
                expect(KeyError, lambda: student.safe_read_call(call(), root=root), '程序错误不应伪装为工具反馈')
            finally:
                student.execute_read_call = original

        def recovery():
            model = Model([reply(call('missing.txt', id='bad')), reply(call(id='fixed')), {'role': 'assistant', 'content': '修正后读取成功'}])
            answer, history = student.run_resilient_agent(model, '读取文件', root=root)
            assert answer == '修正后读取成功' and len(model.seen) == 3
            results = [m for m in history if m['role'] == 'tool']
            assert [m['tool_call_id'] for m in results] == ['bad', 'fixed']
            assert json.loads(model.seen[1][-1]['content'])['ok'] is False, '第二次调用模型必须看到失败反馈'
            assert json.loads(model.seen[2][-1]['content'])['ok'] is True, '后续模型应看到成功结果'

        def tool_budget():
            original = student.safe_read_call
            attempts = []
            def counted(c, root=root):
                attempts.append(c['id'])
                return original(c, root=root)
            student.safe_read_call = counted
            try:
                model = Model([reply(call('missing.txt', id='a'), call(id='b'))])
                expect(RuntimeError, lambda: student.run_resilient_agent(model, 'x', root=root, max_tool_calls=1), '失败尝试也要计入预算')
                assert attempts == ['a'] and len(model.seen) == 1, '预算耗尽后不可执行第二个调用'
            finally:
                student.safe_read_call = original

        def step_budget():
            model = Model([reply(call()), {'role': 'assistant', 'content': '不应读取'}])
            expect(RuntimeError, lambda: student.run_resilient_agent(model, 'x', root=root, max_steps=1), '不能超过模型调用上限')
            assert len(model.seen) == 1

        def zero_and_invalid():
            model = Model([{'role': 'assistant', 'content': '直接回答'}])
            answer, history = student.run_resilient_agent(model, 'x', root=root, max_tool_calls=0)
            assert answer == '直接回答' and len(history) == 2
            for options in ({'max_steps': 0}, {'max_tool_calls': -1}):
                model = Model([])
                expect(ValueError, lambda: student.run_resilient_agent(model, 'x', root=root, **options), '无效预算必须拒绝')
                assert not model.seen

        cases = [('Q1', 10, '成功反馈与 ID', success), ('Q1', 10, '缺失文件反馈', missing),
                 ('Q1', 15, 'JSON、编码与路径错误分类', classification), ('Q1', 15, 'IO 分类与程序错误传播', io_and_program_errors),
                 ('Q2', 20, '失败后修正并继续', recovery), ('Q2', 15, '失败计次与同轮工具预算', tool_budget),
                 ('Q2', 5, '模型调用上限', step_budget), ('Q2', 10, '零工具预算和无效参数', zero_and_invalid)]
        score = total = 0
        for q, points, label, check in cases:
            if selected and q != selected:
                continue
            total += points
            try:
                check()
            except Exception as error:
                print(f'[待完成] {q} {label} 0/{points}：{type(error).__name__}: {error}')
            else:
                score += points
                print(f'[通过] {q} {label} {points}/{points}')
        print(f'总分：{score}/{total}')
        return 0 if score == total else 1


if __name__ == '__main__':
    sys.exit(main())
