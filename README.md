# PPT Drawer

面向 Codex 的项目汇报助手。它根据本次提供的论文、文档、数据和图片整理内容，选择或沿用演示模板，优先生成可编辑 PPTX。

## 能做什么

- 在目标项目内建立材料索引、知识和来源记录；联网补充的知识单独列明来源、用途和页面。
- 按领域分析、汇报策划、版式设计、制作、质量检查分工；交接记录使用宿主实际调度的 agent ID。
- 先提交完整大纲和三页代表性样稿，用户确认后生成整稿。材料、方案或样稿改变会使旧确认失效。
- 有原始数据时制作原生可编辑图表和表格；仅有图片时保留图片，并使用可编辑标题和图注。
- 在样稿、交付和失败阶段记录复盘，区分已应用、已验证与待验证的改进。

插件内包含六套通用视觉规则与 26 类内容布局。项目知识来自每次任务提供的材料；用户指定的模板优先，复杂模板需要逐页核对。

## 安装与调用

需要 Python 及 `requirements.txt` 中的依赖。项目首版在 Windows 和 PowerPoint 上验证；安装 Python 依赖后，可构建本地插件包：

```powershell
python -m pip install -r requirements.txt
python tools/validate_plugin.py --plugin ./ppt-drawer --require-runtime --json
python tools/package_plugin.py --plugin ./ppt-drawer --output ./dist
codex plugin marketplace add (Resolve-Path ./dist/local-marketplace).Path --json
codex plugin add ppt-drawer@ppt-drawer-local --json
```

在 Codex 中选择插件，然后调用：

> 使用 $ppt-assistant，读取我指定的项目材料和模板，先提供整稿大纲与三页样稿。

使用说明与项目记录位置见 [docs/usage.md](docs/usage.md)。技术演示见 [examples/demo/README.md](examples/demo/README.md)，数据和图片均为构造素材；公开版改进及待验证事项见 [docs/retrospective.md](docs/retrospective.md)。

## 渲染依赖与许可边界

本仓库开源的是助手自身的技能、工作流与适配代码。当前 PPTX 渲染适配器还需要 Node.js、`@oai/artifact-tool`、Presentations 技能的 finalizer 及其 Python 运行环境。**这些依赖不随仓库或插件包分发，也不受本仓库 MIT 许可证授权。**

开发环境中的 `@oai/artifact-tool` 是专有软件，其附带许可将使用限制于内部评估和测试，并限制再分发及生产、商业用途。各使用者应检查自己实际取得的依赖及授权；没有相应依赖时，材料、知识和方案工作流可以运行，但无法使用当前适配器渲染 PPTX。Codex 环境和依赖的可用性可能不同，具体配置见 [渲染适配器说明](ppt-drawer/runtime/js/README.md)。

## 验证

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

获得相应渲染依赖后，可用 `tools/check_project.ps1 -Python <python> -Node <node>` 运行 Python、渲染和包验证。示例数据用于技术验证，真实科研内容仍需结合项目材料检查。

## 许可证

本仓库自身代码和自制示例以 [MIT License](LICENSE) 发布。外部依赖和用户提供的材料适用各自的许可。
