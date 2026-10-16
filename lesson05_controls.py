"""第五课第二部分：协作式时限与创建文件前的用户授权。"""
from pathlib import Path
from time import monotonic
from lesson04 import SANDBOX, resolve_read_path


def time_left(deadline, clock=monotonic):
    """Q3（40分）：返回 deadline - clock() 的剩余秒数。

    结果 <= 0 时抛 TimeoutError，否则返回剩余秒数。
    deadline 与 clock 必须使用同一单调时钟，不使用日期时间计算耗时。
    clock 是可调用函数；评分器传入假时钟，无须实际等待。
    """
    # COURSE_TODO(Q3)
    res_clock = deadline - clock()
    if res_clock <= 0:
        raise TimeoutError("超时了")
    else:
        return res_clock


def timed_action(action, deadline, clock=monotonic):
    """提供协作式检查：开始前拒绝过期操作，结束后拒绝超时结果。

    无法强制打断 action；仅用于模型调用或读取，不用于写操作。
    第三课 HTTP 超时仍是单次 30 秒，因此可能越过此时限才返回。
    """
    time_left(deadline, clock)
    result = action()
    time_left(deadline, clock)
    return result


def create_text_file(relative_path, content, approve, root=SANDBOX):
    """Q4（60分）：审阅并授权后，在沙箱中创建新 UTF-8 文件。

    顺序：
    1. content 必须是字符串，UTF-8 编码大小 <= 4096，否则 ValueError。
    2. 用 resolve_read_path 检查路径边界；目标已存在则 FileExistsError。
       父目录不存在则 FileNotFoundError。本题不自动创建目录。
    3. 构造 review={'path': str(目标绝对路径), 'content': 原文本,
                    'bytes': UTF-8字节数}。
    4. 调用 approve(review) 一次；只有返回值 is True 才允许写入。
       其他值（包括 1、'yes'、False）抛 PermissionError。
    5. 用目标.open('x', encoding='utf-8', newline='') 创建并写入 content。
       'x' 能拒绝审阅后才出现的同名文件；不能使用 'w' 覆盖文件。
    6. 返回目标 Path。

    approve 是宿主提供的用户确认回调，不从模型工具参数中获取。
    不捕获异常、不要先写再确认，不修改已有文件。
    本题用于受信任本机练习，不是对抗恶意并发进程的完整沙箱。
    """
    # COURSE_TODO(Q4)
    if not isinstance(content, str):
        raise ValueError('content 必须是字符串')
    raw_bytes = content.encode('utf-8')
    if len(raw_bytes) > 4096:
        raise ValueError('文件内容超过 4096 字节上限')
    target = resolve_read_path(root, relative_path)
    if target.exists():
        raise FileExistsError('目标文件已存在，不可覆盖')
    if not target.parent.exists():
        raise FileNotFoundError('父目录不存在')
    review = {
        'path': str(target),
        'content': content,
        'bytes': len(raw_bytes),
    }
    decision = approve(review)
    if decision is not True:
        raise PermissionError('用户未授权创建文件')
    with target.open('x', encoding='utf-8', newline='') as handle:
        handle.write(content)
    return target
        


def console_approval(review):
    """真实用户确认由本机终端输入；这段代码不自动调用。"""
    print('准备创建：', review['path'])
    print('UTF-8 字节数：', review['bytes'])
    print('内容：\n' + review['content'])
    return input('允许创建这个文件吗？输入 YES 确认：').strip() == 'YES'
