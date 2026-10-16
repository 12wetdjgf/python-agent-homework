"""第四课评分：临时测试文件只创建在课程目录内，不联网。"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import lesson04 as student


def expect_error(error_type, action, feedback):
    try:
        action()
    except error_type:
        return
    raise AssertionError(feedback)


def main():
    selected = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if selected not in (None, 'Q1', 'Q2'):
        print('用法：python -X utf8 grade04.py [Q1|Q2]')
        return 2
    course = Path(__file__).parent.resolve()
    with TemporaryDirectory(prefix='agent-read-tests-', dir=course) as temporary:
        fixture = Path(temporary).resolve()
        assert fixture.is_relative_to(course)
        root = fixture / 'allowed'
        root.mkdir()
        (root / 'sub').mkdir()
        (root / 'notes.txt').write_text('你好，agent！', encoding='utf-8')
        (root / 'exact.txt').write_bytes(b'1234')
        (root / 'large.txt').write_bytes(b'12345')
        (root / 'binary.bin').write_bytes(b'\xff\xfe')
        (fixture / 'outside.txt').write_text('outside fixture', encoding='utf-8')

        def normal_path():
            assert student.resolve_read_path(root, 'notes.txt') == (root / 'notes.txt').resolve()
            assert student.resolve_read_path(root, 'sub/../notes.txt') == (root / 'notes.txt').resolve(), '未越界的 .. 可以保留'

        def escape_path():
            # 两种攻击：越界；相邻目录名称以根目录名称开头。
            for name in ('../outside.txt', '../allowed_backup/notes.txt'):
                expect_error(ValueError, lambda: student.resolve_read_path(root, name), '越界路径必须拒绝')

        def absolute_path():
            expect_error(ValueError, lambda: student.resolve_read_path(root, str((root / 'notes.txt').resolve())), '绝对路径即便位于根目录内也应拒绝')

        def invalid_path():
            for name in ('', '   ', None, 3):
                expect_error(ValueError, lambda: student.resolve_read_path(root, name), '非字符串或空白路径必须拒绝')

        def text_read():
            assert student.read_text_file('notes.txt', root=root) == '你好，agent！', '保留完整 UTF-8 文本'

        def size_limit():
            assert student.read_text_file('exact.txt', root=root, max_bytes=4) == '1234'
            expect_error(ValueError, lambda: student.read_text_file('large.txt', root=root, max_bytes=4), '超出字节上限必须报错')

        def missing_or_directory():
            for name in ('missing.txt', 'sub'):
                expect_error(FileNotFoundError, lambda: student.read_text_file(name, root=root), '不存在的文件和目录不可作为文本文件读取')

        def invalid_read():
            expect_error(UnicodeDecodeError, lambda: student.read_text_file('binary.bin', root=root), '非 UTF-8 文件不能静默忽略')
            expect_error(ValueError, lambda: student.read_text_file('notes.txt', root=root, max_bytes=0), '非正字节预算必须报错')
            expect_error(ValueError, lambda: student.read_text_file('../outside.txt', root=root), '读取入口必须复用路径边界检查')

        cases = [
            ('Q1', 15, '正常路径与未越界的 ..', normal_path),
            ('Q1', 15, '越界与相似目录名', escape_path),
            ('Q1', 10, '绝对路径', absolute_path),
            ('Q1', 10, '无效路径', invalid_path),
            ('Q2', 15, 'UTF-8 文本读取', text_read),
            ('Q2', 15, '文件大小边界', size_limit),
            ('Q2', 10, '不存在的文件与目录', missing_or_directory),
            ('Q2', 10, '编码、预算和入口边界', invalid_read),
        ]
        earned = possible = 0
        for question, points, label, check in cases:
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
