# katago-nekio

这是一个给 KataGo / Lizziezy 相关工具做协作维护的仓库。
This repository is for collaborative maintenance of KataGo and Lizziezy related tools.

目标很简单：
1. 新人能快速上手
2. 大家能看懂、能改、能提交
3. 修改后能稳定推送

The goals are simple:
1. New users can get started quickly
2. Everyone can understand, modify, and contribute
3. Changes can be pushed reliably

欢迎大家修改，欢迎 PR。
Contributions are welcome, and pull requests are welcome.

## 先看这一段（30 秒）
## Read This First (30 Seconds)

你可以把这个仓库理解成两部分：
1. 可协作内容：代码、配置、文档
2. 本地运行资源：大型二进制文件（不放完整历史到 Git）

You can view this repository as two parts:
1. Collaborative content: code, config, and docs
2. Local runtime assets: large binaries (not fully kept in Git history)

因为 GitHub 有大文件限制，这里重点维护“可读、可改、可协作”的部分。
Because GitHub has large file limits, this repo focuses on readable and maintainable collaborative content.

## 当前目录（精简后）
## Current Structure (Slimmed)

- [llm_control](llm_control): LLM 控制中枢（FastAPI 后端 + 前端页面）
- [.gitignore](.gitignore): 忽略规则，防止误提交大文件和本地文件
- [README.md](README.md): 你现在看到的说明

- [llm_control](llm_control): LLM control hub (FastAPI backend and frontend page)
- [.gitignore](.gitignore): ignore rules to avoid committing large files and local files
- [README.md](README.md): this document

## 三步上手
## Quick Start in 3 Steps

1. 克隆仓库
2. 进入 [llm_control](llm_control)
3. 按 [llm_control/README.md](llm_control/README.md) 运行

1. Clone this repository
2. Enter [llm_control](llm_control)
3. Follow [llm_control/README.md](llm_control/README.md)

## 想改代码？从这里开始
## Want To Modify? Start Here

1. 后端逻辑
- [llm_control/app.py](llm_control/app.py)

2. 前端页面
- [llm_control/frontend/index.html](llm_control/frontend/index.html)

3. 依赖与启动
- [llm_control/requirements.txt](llm_control/requirements.txt)
- [llm_control/Start-LLM-Control.bat](llm_control/Start-LLM-Control.bat)

1. Backend logic
- [llm_control/app.py](llm_control/app.py)

2. Frontend page
- [llm_control/frontend/index.html](llm_control/frontend/index.html)

3. Dependencies and startup
- [llm_control/requirements.txt](llm_control/requirements.txt)
- [llm_control/Start-LLM-Control.bat](llm_control/Start-LLM-Control.bat)

## 贡献方式（欢迎大家修改）
## How To Contribute

最推荐的流程：
1. Fork 本仓库
2. 新建分支（例如 feat/xxx 或 fix/xxx）
3. 做一件小而清晰的改动
4. 提交并发起 PR

PR 描述建议写清楚：
1. 改了什么
2. 为什么改
3. 怎么验证

Recommended workflow:
1. Fork this repository
2. Create a branch (for example feat/xxx or fix/xxx)
3. Make one small and clear change
4. Commit and open a pull request

Please include in PR description:
1. What changed
2. Why it changed
3. How you validated it

## 提交前请检查
## Before You Commit

1. 不要提交 >100MB 文件
2. 不要提交真实密钥（例如 .env）
3. 不要提交本地缓存、日志、临时文件
4. README 或注释是否能让别人看懂

1. Do not commit files larger than 100MB
2. Do not commit real secrets (for example .env)
3. Do not commit local cache, logs, or temp files
4. Ensure README or comments are understandable

## 常见问题
## FAQ

1. 为什么仓库里没有完整运行包？
答：为了保证可协作和可推送，超大运行资源不全部进 Git 历史。

1. Why is there no full runtime package in this repository?
Answer: To keep collaboration and pushing stable, very large runtime assets are not fully stored in Git history.

2. 我可以只改文档吗？
答：非常欢迎，文档改进同样是高价值贡献。

2. Can I contribute docs only?
Answer: Yes, documentation improvements are highly valuable.

3. 我不确定改法对不对？
答：可以先提 Issue 说明想法，再一起确认方向。

3. I am not sure whether my change direction is correct.
Answer: Open an issue first and we can align on direction together.

## 一句话结尾
## One-Line Closing

这个仓库欢迎所有让“别人更容易看懂和修改”的改动。
This repository welcomes all changes that make it easier for others to understand and contribute.