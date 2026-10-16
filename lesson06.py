"""第六课：本机会话快照与按用户轮次选择上下文。无网络。"""
from copy import deepcopy
from pathlib import Path
import json


def validate_messages(messages):
    """老师提供基础结构校验；不是完整供应商协议校验器。

    本课只接受已完成的教学会话，不保存等待工具结果的半轮记录。
    """
    if not isinstance(messages, list):
        raise ValueError('messages 必须是列表')
    pending = set()
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError('每条消息必须是字典')
        role = message.get('role')
        if role not in ('user', 'assistant', 'tool'):
            raise ValueError('不支持的消息角色')
        if index == 0 and role != 'user':
            raise ValueError('非空会话必须从 user 开始')
        if role != 'tool' and pending:
            raise ValueError('工具调用尚未收到全部结果')
        if not isinstance(message.get('content', ''), str):
            raise ValueError('文本必须是字符串')
        allowed = {'role', 'content'}
        if role == 'assistant':
            allowed.add('tool_calls')
            calls = message.get('tool_calls') or []
            if not isinstance(calls, list):
                raise ValueError('工具调用必须是列表')
            for call in calls:
                if (not isinstance(call, dict) or set(call) != {'id', 'name', 'arguments_json'}
                        or not all(isinstance(call[key], str) and call[key] for key in call)):
                    raise ValueError('工具调用字段无效')
                if call['id'] in pending:
                    raise ValueError('同轮工具调用 ID 重复')
                pending.add(call['id'])
        elif role == 'tool':
            allowed.update(('name', 'tool_call_id'))
            if message.get('tool_call_id') not in pending:
                raise ValueError('工具结果没有对应调用')
            if not isinstance(message.get('name'), str):
                raise ValueError('工具结果缺少名称')
            pending.remove(message['tool_call_id'])
        if set(message) - allowed:
            raise ValueError('会话含不支持字段；不要将接口配置混入会话')
    if pending or (messages and messages[-1]['role'] != 'assistant'):
        raise ValueError('本课只保存有最终回复的完整会话')


def save_session(path, messages):
    """Q1（30分）：将完整会话保存为一个新 JSON 快照文件。

    先 validate_messages(messages)，再构造
      {'version': 1, 'messages': messages}。
    用 Path(path).open('x', encoding='utf-8') 和 json.dump 保存。
    ensure_ascii=False，indent=2；返回目标 Path。
    已有文件由 x 模式抛 FileExistsError，不覆盖；不创建父目录。
    输入消息不可修改。path 来自宿主程序，不由模型工具参数控制。
    """
    # COURSE_TODO(Q1)
    validate_messages(messages)
    payload = {'version': 1, 'messages': messages}
    target = Path(path)
    with target.open('x', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return target

def load_session(path):
    """Q2（30分）：读取快照，返回 messages。

    只在文件不存在时返回 []，其他异常不得吞掉。
    用二进制方式最多读 1048576 + 1 个字节；超过 1 MiB 抛 ValueError。
    UTF-8 解码，再 json.loads。
    顶层必须为字典，恰好含 version/messages；version 必须是整数 1
    （bool 不算整数版本：可用 type(version) is int）。否则 ValueError。
    调用 validate_messages，校验成功才返回 messages。
    坏 JSON、编码错误自然向上传播，不能伪装成空会话。
    """
    # COURSE_TODO(Q2)
    target = Path(path)
    try:
        with target.open('rb') as handle:
            raw = handle.read(1048576 + 1)
    except FileNotFoundError:
        return []
    if len(raw) > 1048576:
        raise ValueError('文件超过 1 MiB 上限')
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict) or set(data.keys()) != {'version', 'messages'}:
        raise ValueError('格式不合规')
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError('版本必须是数字 1')

    messages = data['messages']
    validate_messages(messages)
    return messages


def recent_turns(messages, max_turns):
    """Q3（40分）：返回最近 max_turns 个用户轮次，保留完整消息组。

    max_turns 必须是正整数（不接受 bool），否则 ValueError。
    先 validate_messages。每条 user 是新一轮的起点。
    找出 user 消息的索引，选择倒数第 max_turns 个起点到列表末尾。
    不足 max_turns 轮则保留全部，空列表返回 []。
    返回 deepcopy 后的列表，不修改原会话，也不能共享嵌套工具字典。
    一轮包含该 user 之后的模型调用、工具结果和最终回答。

    这是按轮数选择，不是 token 预算、摘要压缩或长期语义记忆。
    """
    # COURSE_TODO(Q3)
    if type(max_turns) is not int or max_turns <= 0:
        raise ValueError('数值max_turns设置错误')
    validate_messages(messages)
    user_indices = [i for i, m in enumerate(messages) if m.get('role') == 'user']
    if len(user_indices) <= max_turns:
        start_idx = 0
    else:
        start_idx = user_indices[-max_turns]
    return deepcopy(messages[start_idx:])
