"""课程最终入口：完成 lesson07.py 后运行。默认显示说明。"""
import argparse
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

from lesson03 import ChatCompletionsModel
from lesson05_controls import console_approval
from lesson06 import load_session, save_session
from lesson06_events import summarize_events
from lesson07 import Runtime, run_turn
from mcp_demo_client import DemoMCPClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('配置文件.env'))
    parser.add_argument('--resume', type=Path, help='宿主选择的历史快照路径')
    parser.add_argument('--mcp-demo', action='store_true', help='启动课程自带的本地只读计数服务')
    parser.add_argument('--allow-create', action='store_true', help='开放创建工具，每次仍需终端用户输入 YES')
    parser.add_argument('--interactive', action='store_true', help='连续对话；输入 exit 退出')
    parser.add_argument('--prompt', default='请调用 read_text_file 读取 notes.txt，简短说明内容。')
    args = parser.parse_args()
    if not args.live:
        print('先完成 lesson07.py，运行 python -X utf8 grade07.py。')
        print('联网：python -X utf8 agent_cli.py --live [--mcp-demo] [--interactive]')
        return
    history = load_session(args.resume) if args.resume else []
    model = ChatCompletionsModel.from_config_file(args.config)
    output = Path(__file__).with_name('runtime')
    output.mkdir(exist_ok=True)
    log = output / ('events-' + uuid4().hex + '.jsonl')
    with ExitStack() as stack:
        mcp = stack.enter_context(DemoMCPClient()) if args.mcp_demo else None
        runtime = Runtime(model, approve=console_approval if args.allow_create else None, mcp=mcp, event_path=log)
        prompt = args.prompt
        while True:
            if args.interactive:
                prompt = input('你（exit 退出）：').strip()
                if prompt.lower() == 'exit':
                    break
                if not prompt:
                    continue
            answer, full = run_turn(runtime, prompt, history)
            snapshot = output / ('session-' + uuid4().hex + '.json')
            save_session(snapshot, full)
            history = full
            print(answer)
            print('本轮统计：', summarize_events(runtime.events))
            print('完整快照：', snapshot)
            print('事件日志：', log)
            if not args.interactive:
                break


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError):
        print('运行中止：检查课程实现、预算、时限、会话文件或接口状态。已有快照不会覆盖。')
        raise SystemExit(1)
