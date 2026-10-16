"""第四课接线练习：复用文件工具和第三课模型适配器。默认不联网。"""
import argparse
import json
from lesson03 import ChatCompletionsModel
from lesson04 import SANDBOX, build_read_tool_schema, read_text_file


def execute_read_call(call, root=SANDBOX):
    """接线题：完成模型请求到 Python 文件工具的转换。

    call 使用第二课教学格式：id/name/arguments_json。
    1. name 必须是 read_text_file，否则抛 ValueError。
    2. json.loads 解析 arguments_json。
    3. 参数必须为字典且恰好含 path 一个字段，否则抛 ValueError。
       path 是否是非空字符串，交给第四课路径函数检查。
    4. 调用 read_text_file(args['path'], root=root)。
       工具参数叫 path，Python 函数参数叫 relative_path，这里负责连接。
    5. 返回 {'role': 'tool', 'name': 原工具名,
             'tool_call_id': 原调用id, 'content': 读取到的文本}。

    保留异常，先不转换为工具错误消息；异常恢复属于第五课。
    """
    # COURSE_TODO(INTEGRATION)
    if call.get('name') != 'read_text_file':
        raise ValueError(f"未知工具: {call.get('name')}")
    args = json.loads(call['arguments_json'])
    if not isinstance(args, dict):
        raise ValueError("工具参数必须为字典")
    if set(args.keys()) != {'path'}:
        raise ValueError("工具参数必须且仅包含 path 字段")
    content = read_text_file(args['path'], root=root)
    return {
        'role': 'tool',
        'name': call['name'],
        'tool_call_id': call['id'],
        'content': content
        }


def run_file_agent(model, user_text, root=SANDBOX, max_steps=5):
    if max_steps <= 0:
        raise ValueError('模型调用步数必须为正数')
    messages = [{'role': 'user', 'content': user_text}]
    tools = [build_read_tool_schema()]
    for _ in range(max_steps):
        reply = model.respond(messages, tools)
        messages.append(reply)
        calls = reply.get('tool_calls') or []
        if not calls:
            return reply['content'], messages
        for call in calls:
            messages.append(execute_read_call(call, root=root))
    raise RuntimeError('模型调用步数超上限')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--config', default='配置文件.env')
    args = parser.parse_args()
    if not args.live:
        print('先完成接线题，运行 python -X utf8 grade04_agent.py；--live 才联网。')
        return
    # 预检学生实现，失败时不读取密钥或发起请求。
    execute_read_call({'id': 'precheck', 'name': 'read_text_file',
                       'arguments_json': '{"path":"notes.txt"}'})
    model = ChatCompletionsModel.from_config_file(args.config)
    answer, history = run_file_agent(model, '请调用 read_text_file 读取 notes.txt，并据此告诉我当前在学习哪一课。')
    print(answer)
    results = [m for m in history if m['role'] == 'tool']
    print(f'模型请求 {model.calls} 次，文件工具执行 {len(results)} 次。')
    if not results:
        print('模型直接回答：尚未验证文件工具往返。')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f'{type(error).__name__}: {error}')
        raise SystemExit(1)
