"""第五课第一部分：工具错误反馈与执行预算。离线教学。"""
import json
from lesson04 import SANDBOX, build_read_tool_schema
from lesson04_agent import execute_read_call


ERROR_MESSAGES = {
    'invalid_json': '工具参数不是合法 JSON，请修正后重试。',
    'invalid_encoding': '该文件不是可读取的 UTF-8 文本。',
    'not_found': '文件不存在或不是普通文件，请检查相对路径。',
    'permission_denied': '没有读取该文件的权限。',
    'invalid_request': '工具名称、参数、路径或读取大小不符合要求。',
    'io_error': '读取文件失败。',
}


def tool_message(call, payload):
    """提供统一包装，不把异常文本或本机绝对路径发给模型。"""
    return {'role': 'tool', 'name': call['name'], 'tool_call_id': call['id'],
            'content': json.dumps(payload, ensure_ascii=False)}


def safe_read_call(call, root=SANDBOX):
    """Q1（50分）：执行工具，将预期错误变成工具结果。

    成功：调用 execute_read_call(call, root=root)，取结果的 content，
      返回 tool_message(call, {'ok': True, 'text': 文本})。
    预期错误：返回 tool_message(call, {'ok': False, 'error':
      {'code': 错误码, 'message': ERROR_MESSAGES[错误码]}})。
    分类：
      json.JSONDecodeError -> invalid_json
      UnicodeDecodeError -> invalid_encoding
      FileNotFoundError -> not_found
      PermissionError -> permission_denied
      ValueError -> invalid_request
      OSError -> io_error

    注意子类要先捕获：JSONDecodeError、UnicodeDecodeError 是 ValueError
    的子类；FileNotFoundError、PermissionError 是 OSError 的子类。
    不捕获 Exception；KeyError、TypeError 等程序错误继续向上抛出。
    本题假设调用对象具有合法 id/name 字段，不是通用接口校验器。
    不使用 str(error) 构造回复，避免泄露路径等实现细节。
    """
    # COURSE_TODO(Q1)
    try:
      res = execute_read_call(call, root=root)
      return tool_message(call, {'ok': True, 'text': res['content']})
    except json.JSONDecodeError:
        code = 'invalid_json'
    except UnicodeDecodeError:
        code = 'invalid_encoding'
    except ValueError:
        code = 'invalid_request'
    except FileNotFoundError:
        code = 'not_found'
    except PermissionError:
        code = 'permission_denied'
    except OSError:
        code = 'io_error'

    return tool_message(call, {'ok': False, 'error': {'code': code, 'message': ERROR_MESSAGES[code]}})


def run_resilient_agent(model, user_text, root=SANDBOX, max_steps=5, max_tool_calls=3):
    """Q2（50分）：基于第四课循环，增加独立的工具预算。

    max_steps 必须为正数，max_tool_calls 必须非负，否则抛 ValueError。
    建立 user 消息和 [build_read_tool_schema()]，每轮调用模型并记录回复。
    无调用则返回 (content, messages)。
    每个调用执行前检查已用工具次数；用完时抛 RuntimeError，
    不再执行该工具，也不再调用模型。
    没用完则将次数加一，调用 safe_read_call，并追加返回的工具消息。
    失败尝试同样消耗一次工具预算。预期失败不结束循环，模型可修正。
    同一轮多个调用逐个执行；预算用完前已执行的调用不回滚。
    模型调用次数耗尽且还没最终回复，抛 RuntimeError。

    max_tool_calls=0 仍允许模型直接回答。
    预算限制尝试次数，不是 token、费用或总运行时间预算。
    """
    # COURSE_TODO(Q2)
    step_used = 0
    if max_steps <= 0 or max_tool_calls < 0:
        raise ValueError("数值设置错误")
    messages = [{'role': 'user', 'content': user_text}]
    tools = [build_read_tool_schema()]
    for _ in range(max_steps):
      reply = model.respond(messages, tools)
      messages.append(reply)
      calls = reply.get('tool_calls') or []
      if not calls:
        return (reply['content'], messages)
      else:
         for call in calls:
          if step_used >= max_tool_calls: 
            raise RuntimeError('工具预算耗尽')
          step_used += 1
          msg = safe_read_call(call, root=root)
          messages.append(msg)
    raise RuntimeError     
