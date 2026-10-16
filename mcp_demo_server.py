"""固定本地教学 MCP 服务：2025-06-18，stdio，纯文本 count_words。

只实现本课需要的协议子集；不访问文件、网络或接口配置。
"""
import json
import sys

VERSION = '2025-06-18'
TOOL = {'name': 'count_words', 'description': '按空白分隔文本并返回片段数量，中文整句不分词。',
        'inputSchema': {'type': 'object', 'properties': {'text': {'type': 'string'}},
                        'required': ['text'], 'additionalProperties': False}}


def main():
    initialized = ready = False
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Invalid JSON'}}
            print(json.dumps(response), flush=True)
            continue
        method = request.get('method')
        if 'id' not in request:
            if method == 'notifications/initialized' and initialized:
                ready = True
            continue
        response = {'jsonrpc': '2.0', 'id': request['id']}
        params = request.get('params', {})
        if method == 'initialize':
            initialized = True
            response['result'] = {'protocolVersion': VERSION, 'capabilities': {'tools': {}},
                                  'serverInfo': {'name': 'agent-lab-demo', 'version': '1.0'}}
        elif method == 'ping':
            response['result'] = {}
        elif not ready:
            response['error'] = {'code': -32000, 'message': 'Initialize first'}
        elif method == 'tools/list':
            response['result'] = {'tools': [TOOL]}
        elif method == 'tools/call':
            if params.get('name') != 'count_words':
                response['error'] = {'code': -32602, 'message': 'Unknown tool'}
            else:
                args = params.get('arguments')
                valid = isinstance(args, dict) and set(args) == {'text'} and isinstance(args['text'], str)
                if not valid or len(args['text'].encode('utf-8')) > 4096:
                    result = {'content': [{'type': 'text', 'text': 'Expected text of at most 4096 UTF-8 bytes'}], 'isError': True}
                else:
                    result = {'content': [{'type': 'text', 'text': str(len(args['text'].split()))}], 'isError': False}
                response['result'] = result
        else:
            response['error'] = {'code': -32601, 'message': 'Method not found'}
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
