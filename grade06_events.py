"""第六课日志评分：临时日志，不读取配置、不联网。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import json
import sys
import lesson06_events as student


EVENTS = [
    {'type': 'model_end', 'duration_ms': 12.5},
    {'type': 'tool_end', 'tool_name': 'read_text_file', 'call_id': '读取_1', 'ok': False, 'duration_ms': 2},
    {'type': 'tool_end', 'tool_name': 'read_text_file', 'call_id': '读取_2', 'ok': True, 'duration_ms': 3},
    {'type': 'model_end', 'duration_ms': 10},
]


def expect_value_error(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('无效事件应抛 ValueError')


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q4', 'Q5'):
        print('用法：python -X utf8 grade06_events.py [Q4|Q5]')
        return 2
    course = Path(__file__).parent.resolve()
    with TemporaryDirectory(prefix='agent-log-tests-', dir=course) as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(course)

        def append():
            path = root / 'events.jsonl'
            before = deepcopy(EVENTS)
            for event in EVENTS:
                assert student.append_event(path, event) == path
            lines = path.read_text(encoding='utf-8').splitlines()
            assert len(lines) == 4 and [json.loads(line) for line in lines] == EVENTS, '每个事件一行，追加而非覆盖'
            assert '读取_1' in path.read_text(encoding='utf-8'), '保留 Unicode 文本'
            assert EVENTS == before

        def invalid_append():
            for index, event in enumerate(({'type': 'model_end', 'duration_ms': 1, 'api_key': 'fake-test-value'}, {'type': 'model_end', 'duration_ms': -1}, {'type': 'model_end', 'duration_ms': float('nan')})):
                path = root / f'invalid-{index}.jsonl'
                expect_value_error(lambda: student.append_event(path, event))
                assert not path.exists(), '先校验，再打开文件'

        def summary():
            before = deepcopy(EVENTS)
            assert student.summarize_events(EVENTS) == {'model_calls': 2, 'tool_calls': 2, 'tool_errors': 1, 'operation_ms': 27.5}, '失败工具也计入调用次数'
            assert EVENTS == before

        def empty():
            assert student.summarize_events([]) == {'model_calls': 0, 'tool_calls': 0, 'tool_errors': 0, 'operation_ms': 0}

        def invalid_summary():
            expect_value_error(lambda: student.summarize_events([{'type': 'unknown', 'duration_ms': 1}]))
            expect_value_error(lambda: student.summarize_events([{'type': 'tool_end', 'tool_name': 'read', 'call_id': 'x', 'ok': 'false', 'duration_ms': 1}]))

        cases = [('Q4', 30, '追加、单行 JSON 与输入保留', append), ('Q4', 20, '无效事件不创建日志', invalid_append),
                 ('Q5', 30, '次数、错误与耗时汇总', summary), ('Q5', 10, '空日志', empty), ('Q5', 10, '汇总前校验', invalid_summary)]
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
