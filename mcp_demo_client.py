"""教师提供的固定本机 MCP stdio 客户端，仅支持本课服务。

版本固定为 2025-06-18；无 HTTP、多路并发、资源或采样等能力。
"""
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
from threading import Thread
from time import monotonic


class DemoMCPClient:
    def __enter__(self):
        allowed = {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH'}
        environment = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        environment.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        self.process = subprocess.Popen(
            [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('mcp_demo_server.py'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', env=environment,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        self.queue = Queue()
        self.sequence = 0
        self.reader = Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            initialized = self.request('initialize', {'protocolVersion': '2025-06-18',
                'capabilities': {}, 'clientInfo': {'name': 'agent-lab', 'version': '1.0'}})
            if initialized.get('protocolVersion') != '2025-06-18' or 'tools' not in initialized.get('capabilities', {}):
                raise ValueError('本课 MCP 协议版本或能力不匹配')
            self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            self.tools = self.request('tools/list', {})['tools']
            return self
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                if len(line) > 1048576:
                    raise ValueError('MCP 响应过大')
                self.queue.put(json.loads(line))
        except (ValueError, OSError):
            self.queue.put({'transport_error': True})
        finally:
            self.queue.put(None)

    def _send(self, message):
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
        self.process.stdin.flush()

    def request(self, method, params, timeout=5):
        self.sequence += 1
        request_id = self.sequence
        self._send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
        end = monotonic() + timeout
        while True:
            remaining = end - monotonic()
            if remaining <= 0:
                raise TimeoutError('MCP 请求超时')
            try:
                response = self.queue.get(timeout=remaining)
            except Empty:
                raise TimeoutError('MCP 请求超时') from None
            if response is None or response.get('transport_error'):
                raise RuntimeError('MCP 服务连接已关闭或响应无效')
            if response.get('id') != request_id:
                continue  # 本课服务不发送服务端请求；忽略其他通知。
            if 'error' in response:
                raise RuntimeError('MCP 服务返回协议错误')
            return response['result']

    def call_tool(self, name, arguments):
        return self.request('tools/call', {'name': name, 'arguments': arguments})

    def schemas(self):
        return [{'name': 'mcp_' + tool['name'], 'description': tool.get('description', ''),
                 'parameters': tool['inputSchema']} for tool in self.tools]

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        self.reader.join(timeout=1)
        self.process.stdout.close()

    def __exit__(self, *args):
        self.close()


if __name__ == '__main__':
    with DemoMCPClient() as client:
        print('发现工具：', [tool['name'] for tool in client.tools])
        print('调用结果：', client.call_tool('count_words', {'text': 'hello tiny agent'}))
