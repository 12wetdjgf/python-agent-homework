"""第六课行为评分；只在课程目录内创建临时快照，不联网。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import json
import sys
import lesson06 as student


HISTORY = [
    {'role': 'user', 'content': '你好'},
    {'role': 'assistant', 'content': '你好呀'},
    {'role': 'user', 'content': '读取笔记'},
    {'role': 'assistant', 'tool_calls': [{'id': 'read_1', 'name': 'read_text_file', 'arguments_json': '{"path":"notes.txt"}'}]},
    {'role': 'tool', 'name': 'read_text_file', 'tool_call_id': 'read_1', 'content': '测试笔记'},
    {'role': 'assistant', 'content': '笔记已读取'},
]


def expect(kind, action, feedback):
    try:
        action()
    except kind:
        return
    raise AssertionError(feedback)


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q1', 'Q2', 'Q3'):
        print('用法：python -X utf8 grade06.py [Q1|Q2|Q3]')
        return 2
    course = Path(__file__).parent.resolve()
    with TemporaryDirectory(prefix='agent-session-tests-', dir=course) as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(course)

        def save():
            path = root / 'snapshot.json'
            messages = deepcopy(HISTORY)
            assert student.save_session(path, messages) == path
            payload = json.loads(path.read_text(encoding='utf-8'))
            assert payload == {'version': 1, 'messages': HISTORY}, '保存完整消息及版本'
            assert '你好' in path.read_text(encoding='utf-8'), '使用 ensure_ascii=False'
            assert messages == HISTORY, '不要修改输入'

        def preserve():
            path = root / 'existing.json'
            path.write_text('original', encoding='utf-8')
            expect(FileExistsError, lambda: student.save_session(path, HISTORY), '不能覆盖已有快照')
            assert path.read_text(encoding='utf-8') == 'original'

        def invalid_save():
            path = root / 'invalid.json'
            expect(ValueError, lambda: student.save_session(path, HISTORY[:-1]), '不保存未完成会话')
            assert not path.exists(), '应在写文件前验证'

        def load():
            path = root / 'load.json'
            path.write_text(json.dumps({'version': 1, 'messages': HISTORY}, ensure_ascii=False), encoding='utf-8')
            assert student.load_session(path) == HISTORY
            assert student.load_session(root / 'missing.json') == [], '仅缺失文件可返回空会话'

        def corrupted():
            path = root / 'broken.json'
            path.write_text('{broken', encoding='utf-8')
            expect(json.JSONDecodeError, lambda: student.load_session(path), '损坏快照不可默默丢弃')
            for payload in ({'version': 2, 'messages': HISTORY}, {'version': True, 'messages': HISTORY}, {'version': 1, 'messages': HISTORY[:-1]}, {'version': 1, 'messages': HISTORY, 'config': {}}):
                path.write_text(json.dumps(payload), encoding='utf-8')
                expect(ValueError, lambda: student.load_session(path), '拒绝未知版本、结构与未完成会话')
            path.write_bytes(json.dumps({'version': 1, 'messages': HISTORY}).encode('utf-16'))
            expect(UnicodeDecodeError, lambda: student.load_session(path), '快照约定使用 UTF-8，不自动猜测其他编码')

        def size():
            path = root / 'huge.json'
            path.write_bytes(b' ' * (1048576 + 1))
            expect(ValueError, lambda: student.load_session(path), '检查文件大小后才解析')

        def grouped():
            history = deepcopy(HISTORY)
            assert student.recent_turns(history, 1) == HISTORY[2:], '按 user 起点选取，保留工具调用和结果'
            assert history == HISTORY

        def copy_and_small():
            history = deepcopy(HISTORY)
            selected_history = student.recent_turns(history, 9)
            assert selected_history == HISTORY
            selected_history[3]['tool_calls'][0]['name'] = 'changed'
            assert history == HISTORY, '嵌套调用不能共享引用'
            assert student.recent_turns([], 1) == []

        def invalid_turns():
            for count in (0, -1, True, 1.5, '1', None):
                expect(ValueError, lambda: student.recent_turns(HISTORY, count), '轮数必须为正整数，bool 不算')
            expect(ValueError, lambda: student.recent_turns(HISTORY[:-1], 1), '选取上下文前也要检查完整消息结构')

        cases = [('Q1', 15, '新快照、中文与完整消息', save), ('Q1', 10, '保留已有快照', preserve), ('Q1', 5, '保存前校验', invalid_save),
                 ('Q2', 15, '读取与缺失文件', load), ('Q2', 10, '损坏、版本与结构检查', corrupted), ('Q2', 5, '文件大小上限', size),
                 ('Q3', 20, '按轮保留工具往返', grouped), ('Q3', 10, '深拷贝、空历史与不足轮数', copy_and_small), ('Q3', 10, '无效轮数', invalid_turns)]
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
