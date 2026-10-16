"""第五课第二部分评分：假时钟，无网络；只使用临时测试目录。"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import lesson05_controls as student


def expect(kind, action, message):
    try:
        action()
    except kind:
        return
    raise AssertionError(message)


def remaining():
    assert student.time_left(12, clock=lambda: 10) == 2
    for now in (12, 13):
        expect(TimeoutError, lambda: student.time_left(12, clock=lambda: now), '到期及过期都必须拒绝')


def no_start():
    calls = []
    expect(TimeoutError, lambda: student.timed_action(lambda: calls.append(1), 5, clock=lambda: 5), '到期不可开始操作')
    assert not calls, '检查应当发生在 action 之前'


def late_result():
    ticks = iter([1, 6])
    expect(TimeoutError, lambda: student.timed_action(lambda: 'late', 5, clock=lambda: next(ticks)), '结束后也要检查期限')
    assert student.timed_action(lambda: 'ok', 5, clock=lambda: 1) == 'ok'


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q3', 'Q4'):
        print('用法：python -X utf8 grade05_controls.py [Q3|Q4]')
        return 2
    course = Path(__file__).parent.resolve()
    with TemporaryDirectory(prefix='agent-controls-tests-', dir=course) as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(course)

        def approved():
            path = root / 'approved.txt'
            reviews = []
            def approve(review):
                assert not path.exists(), '确认前不可创建文件'
                reviews.append(dict(review))
                return True
            actual = student.create_text_file('approved.txt', '你好\n', approve, root=root)
            assert actual == path and path.read_bytes() == '你好\n'.encode('utf-8')
            assert reviews == [{'path': str(path), 'content': '你好\n', 'bytes': 7}], '审阅应包含准确目标、内容和字节数'

        def denied():
            for index, decision in enumerate((False, None, 1, 'yes')):
                name = f'denied-{index}.txt'
                expect(PermissionError, lambda: student.create_text_file(name, 'text', lambda review: decision, root=root), '只有布尔 True 表示授权')
                assert not (root / name).exists(), '拒绝后不能写入'

        def existing():
            path = root / 'original.txt'
            path.write_text('original', encoding='utf-8')
            asked = []
            expect(FileExistsError, lambda: student.create_text_file('original.txt', 'changed', lambda r: asked.append(r), root=root), '已有文件不可覆盖')
            assert path.read_text(encoding='utf-8') == 'original' and not asked

        def validation():
            asked = []
            for name, text, kind in (('../escape.txt', 'x', ValueError), ('oversize.txt', '中' * 1366, ValueError), ('not-text.txt', 12, ValueError), ('missing/new.txt', 'x', FileNotFoundError)):
                expect(kind, lambda: student.create_text_file(name, text, lambda r: asked.append(r), root=root), '无效请求应在确认前拒绝')
            assert not asked, '不能让用户确认无法执行的写入'

        def race():
            path = root / 'race.txt'
            def approve(review):
                path.write_text('created meanwhile', encoding='utf-8')
                return True
            expect(FileExistsError, lambda: student.create_text_file('race.txt', 'overwrite', approve, root=root), '审阅后出现的文件也不可覆盖')
            assert path.read_text(encoding='utf-8') == 'created meanwhile'

        cases = [('Q3', 20, '剩余时间与到期边界', remaining), ('Q3', 10, '过期时不启动操作', no_start), ('Q3', 10, '结束后的时限检查', late_result),
                 ('Q4', 20, '先审阅再创建', approved), ('Q4', 10, '明确授权与拒绝', denied), ('Q4', 10, '已有文件保护', existing),
                 ('Q4', 10, '参数、大小与路径边界', validation), ('Q4', 10, '审阅后文件出现', race)]
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
