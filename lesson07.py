"""第七课：统一运行时。三个接线 TODO；默认不联网、不写用户文件。"""
from copy import deepcopy
from math import isfinite
from pathlib import Path
from time import monotonic
import json

from lesson04 import SANDBOX, build_read_tool_schema
from lesson05 import safe_read_call, tool_message
from lesson05_controls import create_text_file, time_left, timed_action
from lesson06 import recent_turns, validate_messages
from lesson06_events import append_event


CREATE_SCHEMA = {'name': 'create_text_file', 'description': '经用户审阅确认后创建沙箱内的新 UTF-8 文本文件；不覆盖已有文件。',
    'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
                   'required': ['path', 'content'], 'additionalProperties': False}}


def failure(call, code, message):
    return tool_message(call, {'ok': False, 'error': {'code': code, 'message': message}})


def create_result(call, root, approve):
    """教师提供写入适配：授权回调由宿主注入，不能由模型替换。"""
    if approve is None:
        return failure(call, 'permission_denied', '宿主未启用创建文件工具。')
    try:
        args = json.loads(call['arguments_json'])
        if not isinstance(args, dict) or set(args) != {'path', 'content'}:
            raise ValueError('args')
        target = create_text_file(args['path'], args['content'], approve, root=root)
        return tool_message(call, {'ok': True, 'text': '已创建：' + str(target.relative_to(Path(root).resolve()))})
    except TimeoutError:  # 授权结束后若已超时，立即终止而不是伪装成普通 IO 错误。
        raise
    except FileExistsError:
        return failure(call, 'already_exists', '目标已存在，不能覆盖。')
    except PermissionError:
        return failure(call, 'permission_denied', '用户没有授权此次创建。')
    except (ValueError, OSError):
        return failure(call, 'invalid_request', '写入参数、路径、内容或文件系统状态不符合要求。')


def normalize_mcp_result(result):
    """Q3（20分）：MCP 文本结果 -> 课程统一载荷（不是完整 tool 消息）。

    如果 result.get('isError', False) 为真，返回：
      {'ok': False, 'error': {'code': 'mcp_tool_error', 'message': 'MCP 工具执行失败。'}}
    否则遍历 result['content']，每块必须 type='text'、text为字符串，
    非文本块或错误文本类型抛 ValueError（本课不支持图片等内容）。
    返回 {'ok': True, 'text': 各块text用换行连接}；空列表文本为 ''。
    不修改输入。MCP 协议请求的 id 与模型的工具调用 id 不是同一个概念。
    """
    # COURSE_TODO(Q3)

    if result.get('isError', False):
        return {
            'ok': False,
            'error': {'code': 'mcp_tool_error', 'message': 'MCP 工具执行失败。'}
        }

    content = result.get('content', [])
    if not isinstance(content, list):
        raise ValueError('MCP content 必须是列表')

    texts = []
    for item in content:
        if (not isinstance(item, dict)
                or item.get('type') != 'text'
                or not isinstance(item.get('text'), str)):
            raise ValueError('MCP 块必须是包含 text 字符串的文本块')
        texts.append(item['text'])

    return {'ok': True, 'text': '\n'.join(texts)}


def mcp_result(call, client):
    if client is None:
        return failure(call, 'unavailable', '未连接 MCP 服务。')
    try:
        if call['name'] not in {tool['name'] for tool in client.schemas()}:
            raise ValueError('unknown')
        args = json.loads(call['arguments_json'])
        if not isinstance(args, dict):
            raise ValueError('arguments')
        result = client.call_tool(call['name'][4:], args)
        return tool_message(call, normalize_mcp_result(result))
    except TimeoutError:
        raise
    except (ValueError, RuntimeError, OSError):
        return failure(call, 'mcp_request_error', 'MCP 请求或内容格式不符合本课要求。')


def execute_tool(call, root=SANDBOX, approve=None, mcp=None):
    """Q1（30分）：按名称分发，复用已有封装，不重新实现读写和协议。

    read_text_file -> safe_read_call(call, root=root)
    create_text_file -> create_result(call, root, approve)
    名称以 'mcp_' 开头 -> mcp_result(call, mcp)
    其他 -> failure(call, 'unknown_tool', '未知工具。')
    直接返回上述函数的结果；保持调用 ID，不能执行 eval 或任意函数。
    本课假设 call 包含有效字符串 id/name/arguments_json。
    """
    # COURSE_TODO(Q1)
    name = call['name']

    if name == 'read_text_file':
        return safe_read_call(call, root=root)

    elif name == 'create_text_file':
        return create_result(call, root, approve)

    elif name.startswith('mcp_'):
        return mcp_result(call, mcp)

    else:
        return failure(call, 'unknown_tool', '未知工具。')


class Runtime:
    """教师提供基础设施，学生通过 run_turn 将它们接线。

    时限为协作式检查；HTTP/MCP 在其各自超时后才能返回。
    授权之后、写入之前再次检查；不在写入完成后冒称操作被取消。
    """
    def __init__(self, model, root=SANDBOX, approve=None, mcp=None, event_path=None,
                 max_steps=5, max_tool_calls=3, max_turns=3, timeout_s=90, clock=monotonic):
        if (type(max_steps) is not int or max_steps <= 0
                or type(max_tool_calls) is not int or max_tool_calls < 0
                or type(max_turns) is not int or max_turns <= 0):
            raise ValueError('调用与历史轮数预算无效')
        if type(timeout_s) not in (int, float) or not isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError('时限必须是有限正数')
        self.model, self.root, self.approve, self.mcp = model, root, approve, mcp
        self.event_path, self.clock = event_path, clock
        self.max_steps, self.max_tool_calls, self.max_turns = max_steps, max_tool_calls, max_turns
        self.timeout_s = timeout_s

    @property
    def tools(self):
        result = [build_read_tool_schema()]
        if self.approve is not None:
            result.append(deepcopy(CREATE_SCHEMA))
        if self.mcp is not None:
            result.extend(self.mcp.schemas())
        return result

    def begin(self):
        self.deadline = self.clock() + self.timeout_s
        self.model_used = self.tool_used = 0
        self.events = []

    def emit(self, event):
        if self.event_path is not None:
            append_event(self.event_path, event)
        self.events.append(event)

    def respond(self, messages):
        time_left(self.deadline, self.clock)
        if self.model_used >= self.max_steps:
            raise RuntimeError('模型调用预算耗尽')
        self.model_used += 1
        start = self.clock()
        try:
            return timed_action(lambda: self.model.respond(deepcopy(messages), self.tools), self.deadline, self.clock)
        finally:
            self.emit({'type': 'model_end', 'duration_ms': max(0, (self.clock() - start) * 1000)})

    def execute(self, call):
        time_left(self.deadline, self.clock)
        if self.tool_used >= self.max_tool_calls:
            raise RuntimeError('工具调用预算耗尽')
        self.tool_used += 1
        ok = False
        start = self.clock()
        def approval(review):
            decision = self.approve(review)
            time_left(self.deadline, self.clock)  # 用户确认耗时也影响后续写入许可。
            return decision
        def action():
            return execute_tool(call, self.root, approval if self.approve is not None else None, self.mcp)
        try:
            result = action() if call['name'] == 'create_text_file' else timed_action(action, self.deadline, self.clock)
            ok = json.loads(result['content'])['ok'] is True
            return result
        finally:
            self.emit({'type': 'tool_end', 'duration_ms': max(0, (self.clock() - start) * 1000),
                       'tool_name': call['name'], 'call_id': call['id'], 'ok': ok})


def run_turn(runtime, user_text, history=None):
    """Q2（50分）：一轮对话，复用 Runtime，不再自己实现预算与时限。

    1. history 为 None 时使用 []；否则校验 history。
    2. full = deepcopy(历史)，context = recent_turns(历史, runtime.max_turns)。
       这是选取最近若干个【历史轮次】，再加当前轮；full 不裁剪。
    3. 新 user 消息分别追加到 full 和 context，调用 runtime.begin()。
    4. 循环 runtime.respond(context)，回复追加到两个列表。
       如果没有 tool_calls（含空列表），校验 full，返回 (回复content, full)。
       否则逐个 runtime.execute(call)，工具结果追加到两个列表，继续循环。
    不捕获预算/时限/程序异常，不修改传入 history。
    Runtime 自己限制模型和工具次数，while True 在这里有明确外部上限。
    仅完成整轮才由 CLI 保存快照；错误中断保留元数据日志，不保存半轮历史。
    """
    if history is None:
        valid_history = []
    else:
        validate_messages(history)
        valid_history = history

    full = deepcopy(valid_history)

    context = recent_turns(valid_history, runtime.max_turns)

    user_msg = {'role': 'user', 'content': user_text}
    full.append(deepcopy(user_msg))
    context.append(deepcopy(user_msg))

    runtime.begin()

    while True:
        reply = runtime.respond(context)
        full.append(reply)
        context.append(deepcopy(reply))

        calls = reply.get('tool_calls') or []

        if not calls:
            validate_messages(full)
            return reply.get('content', ''), full

        for call in calls:
            tool_msg = runtime.execute(call)
            full.append(tool_msg)
            context.append(deepcopy(tool_msg))
