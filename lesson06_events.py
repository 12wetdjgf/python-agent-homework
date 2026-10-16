"""第六课第二部分：操作事件日志。无网络，不记录消息正文或配置。"""
from pathlib import Path
from math import isfinite
import json


def validate_event(event):
    """老师提供结构约束；日志只接受指定元数据。"""
    if not isinstance(event, dict):
        raise ValueError('事件必须为字典')
    kind = event.get('type')
    fields = {'type', 'duration_ms'}
    if kind == 'tool_end':
        fields.update(('tool_name', 'call_id', 'ok'))
        if type(event.get('ok')) is not bool:
            raise ValueError('工具结果必须用布尔 ok 表示')
        if not all(isinstance(event.get(key), str) and event[key].strip() for key in ('tool_name', 'call_id')):
            raise ValueError('工具事件缺少名称或调用 ID')
    elif kind != 'model_end':
        raise ValueError('不支持的事件类型')
    if set(event) != fields:
        raise ValueError('事件字段不匹配；不要记录消息、配置或凭据')
    duration = event.get('duration_ms')
    if type(duration) not in (int, float) or not isfinite(duration) or duration < 0:
        raise ValueError('duration_ms 必须是有限的非负数')


def append_event(path, event):
    """Q4（50分）：将一个事件追加到 JSONL 文件。

    先 validate_event(event)，再将事件转成一行 JSON：
      json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n'
    使用 Path(path).open('a', encoding='utf-8', newline='') 追加。
    已有日志不可覆盖；每次追加一行，不写漂亮缩进的多行 JSON。
    返回目标 Path；不修改 event，不自动创建父目录。
    无效事件在打开文件前拒绝，不能留下新建空文件。
    path 由宿主指定，不通过模型参数选择。
    """
    # COURSE_TODO(Q4)
    validate_event(event)
    line = json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n'
    target = Path(path)
    with target.open('a', encoding='utf-8', newline='') as handle: 
        handle.write(line)
    return target
    


def summarize_events(events):
    """Q5（50分）：校验每个事件并汇总，返回字典：

      {'model_calls': 模型事件数, 'tool_calls': 工具事件数,
       'tool_errors': ok为False的工具事件数,
       'operation_ms': 所有事件duration_ms之和}

    模型事件 type=model_end，工具事件 type=tool_end。
    空事件列表返回四项均为0。不修改输入。
    operation_ms 是已记录操作耗时之和，不是整个会话墙钟时间，
    也不包含未记录的等待、用户思考或授权时间。
    事件计数不代表 token 使用量或费用。
    """

    model_calls = 0
    tool_calls = 0
    tool_errors = 0
    operation_ms = 0
    for event in events:
        validate_event(event)
        operation_ms += event['duration_ms']
        if event['type'] == 'model_end':
            model_calls += 1
        if event['type'] == 'tool_end':
            tool_calls += 1
            if not event['ok']:
                tool_errors += 1

    return {
    'model_calls': model_calls,
    'tool_calls': tool_calls,
    'tool_errors': tool_errors,
    'operation_ms': operation_ms,
}

