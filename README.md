# Python Agent Homework

从零实现工具调用 Agent 的七课作业完成记录。只使用 Python 标准库，包含真实模型适配、本机 MCP、文件工具、会话存储、授权和测试。

**状态：七课核心作业完成，10 个评分入口均通过 100/100。** 详细证据与验收边界见 [COMPLETION.md](COMPLETION.md)。

## 快速验证

Python 3.10+，无需安装第三方依赖：

```sh
python -X utf8 run_checks.py
python -X utf8 mcp_demo_client.py
```

评分不联网、不读取真实接口配置。MCP 演示只启动仓库自带的本机计数子进程，结束后关闭。

## 七课结构

| 课程 | 代码 | 内容 |
| --- | --- | --- |
| 1 | lesson01.py | Agent 循环与工具分发 |
| 2 | lesson02.py | 工具描述、JSON 参数与调用 ID |
| 3 | lesson03.py | OpenAI 兼容 Chat Completions 适配器 |
| 4 | lesson04.py / lesson04_agent.py | 受限文件读取与接线 |
| 5 | lesson05.py / lesson05_controls.py | 错误恢复、预算、时限与授权 |
| 6 | lesson06.py / lesson06_events.py | 会话快照、上下文与 JSONL 日志 |
| 7 | lesson07.py / agent_cli.py | 统一运行时、完整 CLI 与 MCP |

每课的 grade*.py 保留行为评分；代码中的 COURSE_TODO 注释标记原练习位置，已有实现。教程说明文档保留了分阶段的教学要求；当前完成状态以本页及 COMPLETION.md 为准。

## 使用自己的模型接口

复制 `.env.example` 为本机的 `配置文件.env`，填写 Base URL、密钥和支持工具调用的模型名。Base URL 包含服务要求的基础路径，程序在其后追加 `/chat/completions`。兼容性取决于供应商的实际协议支持。

```sh
python -X utf8 lesson03.py --config "配置文件.env" --check-config
python -X utf8 agent_cli.py --live
python -X utf8 agent_cli.py --live --mcp-demo --prompt "请调用 mcp_count_words 统计 hello tiny agent 的片段数。"
python -X utf8 agent_cli.py --live --mcp-demo --interactive
```

配置文件只留本机，不提交。真实请求使用自己的模型服务，费用由该服务决定。

## 会话恢复与文件权限

完整快照和元数据日志在本机 `runtime/`，不会提交。恢复时用实际快照文件名替换占位名称：

```sh
python -X utf8 agent_cli.py --live --resume "runtime/session-实际文件名.json" --interactive
```

默认只提供读取工具。`--allow-create` 开放创建工具后，每次仍需终端用户审阅目标和内容并输入 `YES`；使用新建模式，不覆盖已有文件。模型不能自行授权。协作式时限会在用户确认后、写入前重新检查，不承诺强制中断正在执行的请求。

## 来源与范围

这是学习者与 AI 编程老师协作完成的教学项目。核心流程参考 hummcode 的职责划分；接口格式依据官方文档；MCP 演示是固定协议版本的最小本机实现。参考仓库本身未打包到本仓库，详见 [代码来源.md](代码来源.md)。

本项目不声称提供生产级沙箱、完整 MCP SDK、自动摘要压缩或精确 token 计费。GitHub Actions 配置可重复运行离线评分，实时结果以仓库 Actions 页面为准。
