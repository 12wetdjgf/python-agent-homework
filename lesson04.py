"""第四课：受限的文本读取工具。当前仅离线，不调用模型。"""
from pathlib import Path


SANDBOX = Path(__file__).parent / 'sandbox'


def resolve_read_path(root, relative_path):
    """Q1（50分）：将相对路径解析为 root 内的绝对 Path。

    1. relative_path 必须是非空字符串，否则抛 ValueError。
    2. 不允许绝对路径：用 Path(relative_path).is_absolute() 判断。
    3. 分别 resolve 根目录和拼接后的目标（处理 ..、符号链接）。
    4. 用 target.is_relative_to(root_path) 判断目标仍在根目录内。
       越界抛 ValueError。不要用字符串 startswith 判断包含关系！
    5. 返回解析后的目标 Path，不读文件、不改变文件。

    resolve 的结果并不保证文件存在；是否是文件留给 Q2。
    本课允许没有越界的子目录和 ..，例如 sub/../notes.txt。
    """
    # COURSE_TODO(Q1)
    if not isinstance(relative_path, str) or not relative_path.strip():
         raise ValueError("relative_path 必须是非空字符串")
    rel_path = Path(relative_path)
    if rel_path.is_absolute():
         raise ValueError({"不允许绝对路径"})
    root_path = Path(root).resolve()
    target = (root_path / rel_path).resolve()
    target = (root_path / rel_path).resolve()
    if not target.is_relative_to(root_path):
        raise ValueError("路径越界，逃出沙箱根目录啦！")
    return target


def read_text_file(relative_path, root=SANDBOX, max_bytes=65536):
    """Q2（50分）：调用 Q1，读取一个有限大小的 UTF-8 文本文件。

    max_bytes <= 0 时抛 ValueError。
    调用 resolve_read_path 得到目标；若不是文件，抛 FileNotFoundError。
    使用 with target.open('rb') as handle，最多读取 max_bytes + 1 个字节。
    超过 max_bytes 则抛 ValueError；否则 decode('utf-8') 返回字符串。
    UnicodeDecodeError 自然向上传递；不要使用 errors='ignore'。

    读多一个字节用于判断超限，同时避免把巨大文件全部读进内存。
    不使用 eval、不执行 shell、不写文件。
    """
    # COURSE_TODO(Q2)
    if max_bytes <= 0:
        raise ValueError({"数值设置错误"})
    target = resolve_read_path(root,relative_path)
    if not target.is_file():
        raise FileNotFoundError("读取非文本文件")
    else:
        with target.open('rb') as handle:
            data = handle.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("读取文本超上限")
        return data.decode('utf-8')



def build_read_tool_schema():
    return {
        'name': 'read_text_file',
        'description': '读取练习目录内的 UTF-8 文本文件，使用相对路径。',
        'parameters': {
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
            'additionalProperties': False,
        },
    }


if __name__ == '__main__':
    print(read_text_file('notes.txt'))
