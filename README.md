# katago-nekio

一个面向 KataGo + Lizziezy 使用场景的可维护仓库，目标是：
- 让新用户可以快速跑起来
- 让开发者可以低门槛修改
- 让贡献者知道改什么、怎么提 PR

欢迎大家直接提 Issue、提 PR、补文档、修脚本、改配置。

## 这个仓库是什么

本仓库主要保存可协作的内容：
- 配置文件（cfg、txt、json 等）
- 脚本和工具代码（bat、py、前端页面）
- 文档和说明

出于 GitHub 单文件大小限制，运行时大型二进制资源（例如部分 exe、dll、模型大文件）不全部放在 Git 历史中。
这意味着仓库更适合协作开发与配置管理，而不是完整分发包镜像。

## 目录速览

- [lizziezy_base](lizziezy_base): 主目录，包含配置、脚本、主题、说明文档
- [lizziezy_base/katago_configs](lizziezy_base/katago_configs): KataGo 常用配置
- [lizziezy_base/llm_control](lizziezy_base/llm_control): LLM 控制中枢（FastAPI + 前端）
- [lizziezy_base/readboard](lizziezy_base/readboard): 读盘相关配置与组件说明
- [lizziezy_base/trt](lizziezy_base/trt): TensorRT 相关示例配置
- [.gitignore](.gitignore): 仓库忽略规则（防止误提交大文件/本地文件）

## 快速开始

### 1. 获取仓库

克隆后进入项目目录。

### 2. 准备运行资源

如果你要完整运行 Lizziezy/KataGo，请把本地已有的运行资源放回对应目录（例如可执行文件、模型权重、相关动态库）。

建议优先确保以下目录资源完整：
- lizziezy_base/weights
- lizziezy_base/katago_tensorRT
- lizziezy_base/jre
- lizziezy_base/jcef-bundle

### 3. 可选：启动 LLM 控制中枢

查看 [lizziezy_base/llm_control/README.md](lizziezy_base/llm_control/README.md) 按说明配置并启动。

## 最常见可修改点

如果你第一次参与修改，建议从这些地方开始：

1. 引擎参数和分析策略
- [lizziezy_base/katago_configs/analysis.cfg](lizziezy_base/katago_configs/analysis.cfg)
- [lizziezy_base/katago_configs/default_gtp.cfg](lizziezy_base/katago_configs/default_gtp.cfg)

2. LLM 控制行为
- [lizziezy_base/llm_control/app.py](lizziezy_base/llm_control/app.py)
- [lizziezy_base/llm_control/frontend/index.html](lizziezy_base/llm_control/frontend/index.html)

3. 主题和界面风格
- [lizziezy_base/theme/theme.txt](lizziezy_base/theme/theme.txt)
- [lizziezy_base/theme/Custom/theme.txt](lizziezy_base/theme/Custom/theme.txt)

4. 使用与排障文档
- [lizziezy_base/说明文档](lizziezy_base/%E8%AF%B4%E6%98%8E%E6%96%87%E6%A1%A3)

## 贡献指南（欢迎大家修改）

欢迎任何形式的改进，尤其包括：
- 修复启动/路径/配置问题
- 提升默认参数合理性
- 改善文档可读性
- 补充中英文说明
- 优化 LLM 控制体验

建议贡献流程：

1. Fork 并新建分支（例如 feat/xxx、fix/xxx）
2. 提交小而清晰的改动（每次只解决一类问题）
3. 在提交说明中写明改动目的和影响范围
4. 发起 PR，描述复现步骤和验证方式

PR 描述建议包含：
- 修改动机
- 具体改了哪些文件
- 如何验证
- 是否影响现有用户配置

## 提交前检查

为避免再次出现无法推送的问题，请在提交前确认：

1. 没有误提交大文件（特别是 >100MB）
2. 没有提交本地私密文件（如 .env 实值）
3. 没有提交本地缓存或日志
4. 配置修改有对应说明

## 已知说明

- 本仓库优先保证协作可维护，不追求完整二进制分发。
- 若你需要一键可运行的完整包，建议在发布渠道提供单独压缩包或 Release 附件。

## 交流与反馈

如果你准备改动但不确定方向，直接开 Issue 说明你的目标即可。
如果你已经改好，直接开 PR，我们会尽快一起把它变得更稳定、好用、易维护。