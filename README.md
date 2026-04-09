# katago-nekio

这是一个给 KataGo / Lizziezy 相关工具做协作维护的仓库。

目标很简单：
1. 新人能快速上手
2. 大家能看懂、能改、能提交
3. 修改后能稳定推送

欢迎大家修改，欢迎 PR。

## 先看这一段（30 秒）

你可以把这个仓库理解成两部分：
1. 可协作内容：代码、配置、文档
2. 本地运行资源：大型二进制文件（不放完整历史到 Git）

因为 GitHub 有大文件限制，这里重点维护“可读、可改、可协作”的部分。

## 当前目录（精简后）

- [llm_control](llm_control): LLM 控制中枢（FastAPI 后端 + 前端页面）
- [.gitignore](.gitignore): 忽略规则，防止误提交大文件和本地文件
- [README.md](README.md): 你现在看到的说明

## 三步上手

1. 克隆仓库
2. 进入 [llm_control](llm_control)
3. 按 [llm_control/README.md](llm_control/README.md) 运行

## 想改代码？从这里开始

1. 后端逻辑
- [llm_control/app.py](llm_control/app.py)

2. 前端页面
- [llm_control/frontend/index.html](llm_control/frontend/index.html)

3. 依赖与启动
- [llm_control/requirements.txt](llm_control/requirements.txt)
- [llm_control/Start-LLM-Control.bat](llm_control/Start-LLM-Control.bat)

## 贡献方式（欢迎大家修改）

最推荐的流程：
1. Fork 本仓库
2. 新建分支（例如 feat/xxx 或 fix/xxx）
3. 做一件小而清晰的改动
4. 提交并发起 PR

PR 描述建议写清楚：
1. 改了什么
2. 为什么改
3. 怎么验证

## 提交前请检查

1. 不要提交 >100MB 文件
2. 不要提交真实密钥（例如 .env）
3. 不要提交本地缓存、日志、临时文件
4. README 或注释是否能让别人看懂

## 常见问题

1. 为什么仓库里没有完整运行包？
答：为了保证可协作和可推送，超大运行资源不全部进 Git 历史。

2. 我可以只改文档吗？
答：非常欢迎，文档改进同样是高价值贡献。

3. 我不确定改法对不对？
答：可以先提 Issue 说明想法，再一起确认方向。

## 一句话结尾

这个仓库欢迎所有让“别人更容易看懂和修改”的改动。