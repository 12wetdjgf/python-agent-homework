"""第三课：Chat Completions 适配器。TODO 可离线评分；--live 才联网。

依据：https://developers.openai.com/api/docs/guides/function-calling
只覆盖文本和 function tools；不支持 Responses、流式或多模态。

"""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lesson02 import build_tool_schema, run_agent


def read_config_file(path):
    """仅读取本机配置：支持 KEY=VALUE、key: value 和 key value。

    不执行配置内容，不展开变量，不改写文件或进程环境。
    """
    aliases = {
        'agent_base_url': 'base_url', 'openai_base_url': 'base_url', 'base_url': 'base_url',
        'agent_api_key': 'api_key', 'openai_api_key': 'api_key', 'api_key': 'api_key', 'apikey': 'api_key',
        'agent_model': 'model', 'openai_model': 'model', 'model': 'model',
    }
    values = {}
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        match = re.match(r'^([A-Za-z_][A-Za-z_0-9]*)(?:\s*\(OpenAI\))?(?:\s*[=:：]\s*|\s+)(.*)$', line, re.IGNORECASE)
        if not match or match.group(1).lower() not in aliases:
            raise ValueError(f'配置第 {number} 行格式或字段不支持')
        key = aliases[match.group(1).lower()]
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key in values:
            raise ValueError(f'配置第 {number} 行存在重复字段')
        values[key] = value
    missing = [key for key in ('base_url', 'api_key', 'model') if not values.get(key, '').strip()]
    if missing:
        raise ValueError('配置缺少或为空：' + ', '.join(missing))
    return values


def to_api_message(message):
    """Q1（45分）：将一个教学消息转换成 Chat Completions 消息。

    所有转换都返回新字典，不修改输入。
    user：保留 role 和 content。
    tool：保留 role、content、tool_call_id，去掉教学字段 name。
    assistant：保留 role，content 缺省时为 None。
      如果 tool_calls 非空，将每个扁平调用转换成：
      {'id': 原id, 'type': 'function',
       'function': {'name': 原name, 'arguments': 原arguments_json}}
      没有调用时不输出 tool_calls 字段。
    不支持的 role 抛 ValueError，错误包含 role 值。
    本课输入是格式正确的教学消息，不用做通用协议校验。
    """
    # COURSE_TODO(Q1)
    role = message.get('role')
    if role == 'user':
        return {
            'role': 'user',
            'content': message.get('content', ''),
        }
    elif role == 'tool':
        return {
            'role': 'tool',
            'tool_call_id': message['tool_call_id'],
            'content': message.get('content', ''),
        }
    elif role == 'assistant':
        result = {
            'role': 'assistant',
            'content': message.get('content', None),
        }
        calls = message.get('tool_calls')
        if calls:
            result['tool_calls'] = [
                {
                    'id': c['id'],
                    'type': 'function',
                    'function': {
                        'name': c['name'],
                        'arguments': c['arguments_json'],
                    },
                }
                for c in calls
            ]
        return result
    else:
        raise ValueError(f'不支持的 role: {role}')


def from_api_message(message):
    """Q2（40分）：将接口的 assistant 消息转换成教学消息。

    返回 {'role': 'assistant', 'content': 文本或空字符串}。
    遍历 message.get('tool_calls') or []，把每个 function 调用变成：
      {'id': 原id, 'name': function中的name,
       'arguments_json': function中的arguments}
    有调用才在返回字典中加入 tool_calls。
    arguments 在这里保持 JSON 字符串：解析和执行留给第二课！
    遇到非 function 类型抛 ValueError，错误包含该类型值。
    返回新字典，不修改输入；无须保留其他供应商元数据。
    """
    # COURSE_TODO(Q2)
    content = message.get('content')
    if content is None:
        content = ''
    result = {
        'role': 'assistant',
        'content': content,
    }
    raw_calls = message.get('tool_calls')
    if raw_calls:
        flat_calls = []
        for c in raw_calls:
            call_type = c.get('type')
            if call_type != 'function':
                raise ValueError(f'不支持的工具调用类型: {call_type}')
            flat_calls.append({
                'id': c['id'],
                'name': c['function']['name'],
                'arguments_json': c['function']['arguments'],
            })
            result['tool_calls'] = flat_calls
    return result
        


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 配置错误时直接反馈状态码，避免将认证头转发给其他地址。
        return None


class ChatCompletionsModel:
    """提供与第二课相同的 respond(messages, tools)，只替换模型对象。"""

    def __init__(self, base_url, api_key, model, transport=None):
        base_url = base_url.strip().rstrip('/')
        parts = urlsplit(base_url)
        if (parts.scheme not in ('https', 'http') or not parts.hostname
                or parts.username or parts.password or parts.query or parts.fragment):
            raise ValueError('Base URL 必须是无认证信息、查询参数和片段的 http(s) 地址')
        if not api_key.strip() or not model.strip():
            raise ValueError('密钥和模型名不可为空')
        self.endpoint = base_url + '/chat/completions'
        self.api_key = api_key
        self.model = model.strip()
        self.transport = transport or self._post_json
        self.calls = 0

    @classmethod
    def from_config_file(cls, path):
        values = read_config_file(path)
        return cls(values['base_url'], values['api_key'], values['model'])

    @classmethod
    def from_environment(cls):
        fields = ('AGENT_BASE_URL', 'AGENT_API_KEY', 'AGENT_MODEL')
        missing = [field for field in fields if not os.environ.get(field, '').strip()]
        if missing:
            raise ValueError('缺少环境变量：' + ', '.join(missing))
        return cls(*(os.environ[field] for field in fields))

    def _post_json(self, payload):
        request = Request(
            self.endpoint, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + self.api_key}, method='POST',
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                data = response.read(2 * 1024 * 1024 + 1)
        except HTTPError as error:
            # 不输出请求头、密钥或可能包含私有信息的服务响应全文。
            raise RuntimeError(f'接口返回 HTTP {error.code}；检查地址、认证、模型或工具支持') from None
        except (URLError, TimeoutError):
            raise RuntimeError('接口连接失败或超时；检查网络和地址') from None
        if len(data) > 2 * 1024 * 1024:
            raise RuntimeError('接口响应超过本课 2 MiB 上限')
        try:
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError('接口未返回合法 JSON') from None

    def respond(self, messages, tools):
        payload = {
            'model': self.model,
            'messages': [to_api_message(message) for message in messages],
            'tools': [{'type': 'function', 'function': tool} for tool in tools],
            'stream': False,
        }
        self.calls += 1
        response = self.transport(payload)
        if not isinstance(response, dict) or not response.get('choices'):
            raise RuntimeError('接口缺少 choices；确认使用 Chat Completions 协议')
        choice = response['choices'][0]
        if choice.get('finish_reason') in ('length', 'content_filter'):
            raise RuntimeError('模型回复被截断或过滤，不能作为完整结果')
        reply = from_api_message(choice['message'])
        if not reply.get('tool_calls') and not reply.get('content'):
            raise RuntimeError('接口没有返回可用文本或工具调用')
        return reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='读取本机环境变量并真实请求接口')
    parser.add_argument('--config', type=Path, help='从本机配置文件读取地址、密钥和模型，优先于环境变量')
    parser.add_argument('--check-config', action='store_true', help='仅检查配置，不联网、不输出配置值')
    parser.add_argument('--prompt', default='请调用 add 工具计算 17 加 25，再告诉我工具的结果。')
    args = parser.parse_args()
    if args.check_config:
        if args.live:
            raise ValueError('--check-config 和 --live 不能同时使用')
        if args.config:
            ChatCompletionsModel.from_config_file(args.config)
        else:
            ChatCompletionsModel.from_environment()
        print('配置读取和基础校验通过；未联网，尚未验证认证、模型或工具支持。')
        return
    if not args.live:
        print('先运行 python -X utf8 grade03.py；--live 会向配置的服务发出请求。')
        return
    # 在读取密钥和发送请求之前确认两个练习已实现。
    to_api_message({'role': 'user', 'content': '预检'})
    from_api_message({'role': 'assistant', 'content': '预检'})
    model = (ChatCompletionsModel.from_config_file(args.config) if args.config
             else ChatCompletionsModel.from_environment())
    answer, messages = run_agent(model, args.prompt, max_steps=5)
    print(answer)
    results = [message for message in messages if message['role'] == 'tool']
    print(f'模型请求 {model.calls} 次；实际工具执行 {len(results)} 次。')
    for result in results:
        print(f"工具 {result['name']} / ID {result['tool_call_id']} / 结果 {result['content']}")
    if not results:
        print('本次模型直接回答：尚未完成真实工具往返验收。')


if __name__ == '__main__':
    try:
        main()
    except OSError:
        print('无法读取配置文件；请检查文件位置、权限和编码。')
        raise SystemExit(1)
    except (ValueError, RuntimeError) as error:
        print(f'{type(error).__name__}: {error}')
        raise SystemExit(1)
