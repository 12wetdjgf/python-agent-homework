"""最终接线评分：假模型、假时钟、临时目录，含真实本地 MCP 子进程。无联网。"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

from lesson01 import ScriptedModel
from lesson06 import load_session, save_session
from lesson06_events import summarize_events
from mcp_demo_client import DemoMCPClient
import lesson07 as student


def call(name='read_text_file', args=None, id='read_1'):
    return {'id': id, 'name': name, 'arguments_json': json.dumps({'path': 'notes.txt'} if args is None else args)}


def reply(*calls):
    return {'role': 'assistant', 'tool_calls': list(calls)}


class Model(ScriptedModel):
    def respond(self, messages, tools):
        self.tools_seen = deepcopy(tools)
        return super().respond(messages)


def expect(kind, action):
    try:
        action()
    except kind:
        return
    raise AssertionError('应抛出 ' + kind.__name__)


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q1', 'Q2', 'Q3'):
        print('用法：python -X utf8 grade07.py [Q1|Q2|Q3]')
        return 2
    course = Path(__file__).parent.resolve()
    with TemporaryDirectory(prefix='agent-final-tests-', dir=course) as directory:
        fixture = Path(directory).resolve()
        assert fixture.is_relative_to(course)
        root = fixture / 'sandbox'
        root.mkdir()
        (root / 'notes.txt').write_text('接线测试文本', encoding='utf-8')

        def local_read():
            r = student.execute_tool(call(), root=root)
            assert r['tool_call_id'] == 'read_1' and json.loads(r['content']) == {'ok': True, 'text': '接线测试文本'}
            r = student.execute_tool(call(name='unknown'), root=root)
            assert json.loads(r['content'])['error']['code'] == 'unknown_tool'

        def write_denied():
            c = call('create_text_file', {'path': 'denied.txt', 'content': 'new'})
            for approve in (None, lambda review: False):
                r = student.execute_tool(c, root=root, approve=approve)
                assert json.loads(r['content'])['error']['code'] == 'permission_denied'
                assert not (root / 'denied.txt').exists()
            r = student.execute_tool(call('mcp_count_words', {'text': 'hi'}), root=root)
            assert json.loads(r['content'])['error']['code'] == 'unavailable'

        def write_approved():
            reviews = []
            def approve(review):
                reviews.append(review)
                assert not (root / 'created.txt').exists()
                return True
            c = call('create_text_file', {'path': 'created.txt', 'content': '新文本'}, id='create_1')
            r = student.execute_tool(c, root=root, approve=approve)
            assert json.loads(r['content'])['ok'] is True and len(reviews) == 1
            assert (root / 'created.txt').read_text(encoding='utf-8') == '新文本'
            r = student.execute_tool(c, root=root, approve=lambda review: True)
            assert json.loads(r['content'])['error']['code'] == 'already_exists'

        def history_and_log():
            old = [{'role': 'user', 'content': 'old'}, {'role': 'assistant', 'content': 'older'},
                   {'role': 'user', 'content': 'recent'}, {'role': 'assistant', 'content': 'recent answer'}]
            before = deepcopy(old)
            model = Model([reply(call()), {'role': 'assistant', 'content': '完成'}])
            log = fixture / 'events.jsonl'
            runtime = student.Runtime(model, root=root, max_turns=1, event_path=log)
            answer, full = student.run_turn(runtime, '读取', old)
            assert answer == '完成' and old == before and full[:4] == old and len(full) == 8
            assert model.seen[0] == old[2:] + [{'role': 'user', 'content': '读取'}], '模型只接收最近历史轮次，但完整记录不可裁剪'
            assert json.loads(model.seen[1][-1]['content'])['text'] == '接线测试文本'
            assert len(runtime.events) == 3 and [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] == runtime.events
            stats = summarize_events(runtime.events)
            assert stats['model_calls'] == 2 and stats['tool_calls'] == 1 and stats['tool_errors'] == 0
            snapshot = fixture / 'full.json'
            save_session(snapshot, full)
            assert load_session(snapshot) == full, '完成整轮后才能保存完整快照'

        def budgets():
            model = Model([reply(call(name='unknown', id='failed'), call(id='not_allowed'))])
            runtime = student.Runtime(model, root=root, max_tool_calls=1)
            expect(RuntimeError, lambda: student.run_turn(runtime, 'x'))
            assert runtime.tool_used == 1 and runtime.model_used == 1
            assert [e['call_id'] for e in runtime.events if e['type'] == 'tool_end'] == ['failed']
            model = Model([reply(call()), {'role': 'assistant', 'content': '不可请求'}])
            runtime = student.Runtime(model, root=root, max_steps=1)
            expect(RuntimeError, lambda: student.run_turn(runtime, 'x'))
            assert len(model.seen) == 1

        def deadline():
            now = [0]
            def approve(review):
                now[0] = 11
                return True
            model = Model([reply(call('create_text_file', {'path': 'late.txt', 'content': 'late'}))])
            runtime = student.Runtime(model, root=root, approve=approve, clock=lambda: now[0], timeout_s=10)
            expect(TimeoutError, lambda: student.run_turn(runtime, 'x'))
            assert not (root / 'late.txt').exists(), '授权之后也必须在真正写入前检查时限'

        def recover():
            model = Model([reply(call(args={'path': 'missing.txt'}, id='missing')), reply(call(id='fixed')), {'role': 'assistant', 'content': '修复完成'}])
            runtime = student.Runtime(model, root=root)
            answer, history = student.run_turn(runtime, 'x')
            assert answer == '修复完成' and len(model.seen) == 3
            assert summarize_events(runtime.events)['tool_errors'] == 1
            assert json.loads(model.seen[1][-1]['content'])['error']['code'] == 'not_found'

        def mcp_format():
            original = {'content': [{'type': 'text', 'text': 'a'}, {'type': 'text', 'text': 'b'}]}
            before = deepcopy(original)
            assert student.normalize_mcp_result(original) == {'ok': True, 'text': 'a\nb'} and original == before
            assert student.normalize_mcp_result({'content': []}) == {'ok': True, 'text': ''}
            result = student.normalize_mcp_result({'isError': True, 'content': [{'type': 'text', 'text': 'private server details'}]})
            assert result == {'ok': False, 'error': {'code': 'mcp_tool_error', 'message': 'MCP 工具执行失败。'}}
            expect(ValueError, lambda: student.normalize_mcp_result({'content': [{'type': 'image', 'data': ''}]}))

        def actual_mcp():
            with DemoMCPClient() as client:
                assert client.schemas()[0]['name'] == 'mcp_count_words'
                result = client.call_tool('count_words', {'text': 'hello tiny agent'})
                assert student.normalize_mcp_result(result) == {'ok': True, 'text': '3'}
                failed = client.call_tool('count_words', {'wrong': 'args'})
                assert student.normalize_mcp_result(failed)['ok'] is False
            assert client.process.poll() is not None, '结束时关闭本课创建的 MCP 服务进程'

        cases = [('Q1', 10, '读取与未知工具分发', local_read), ('Q1', 10, '未启用和用户拒绝写入', write_denied), ('Q1', 10, '批准后创建且不覆盖', write_approved),
                 ('Q2', 20, '完整历史、上下文、日志与快照', history_and_log), ('Q2', 10, '模型与工具预算', budgets), ('Q2', 10, '确认后超时不写入', deadline), ('Q2', 10, '错误反馈后恢复', recover),
                 ('Q3', 10, 'MCP 文本与错误载荷', mcp_format), ('Q3', 10, '真实本地 MCP 协议往返', actual_mcp)]
        score = total = 0
        for q, points, label, check in cases:
            if selected and selected != q:
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
