# 使用 PPT 助手

首版面向当前 Windows 与 PowerPoint 环境。插件标识为 `ppt-drawer`，技能名为 `ppt-assistant`，界面显示“PPT 助手”。项目材料与知识保存在调用所面向的项目中。

## 构建与本地安装

在源码根目录执行：

```powershell
python tools/validate_plugin.py --plugin ./ppt-drawer --require-runtime --json
python tools/package_plugin.py --plugin ./ppt-drawer --output ./dist
```

成功后有一个 standalone ZIP，以及 `dist/local-marketplace/` 下独立的来源目录。ZIP 只包含插件；本地 marketplace 用于 Codex 安装，二者用途不同。打包器会验证内部引用、双 manifest、运行时入口和分发内容。

用户要求安装时再执行以下命令，它们会更新本机的 marketplace 配置与插件缓存：

```powershell
$marketplaceRoot = (Resolve-Path ./dist/local-marketplace).Path
codex plugin marketplace add $marketplaceRoot --json
codex plugin add ppt-drawer@ppt-drawer-local --json
codex plugin list --marketplace ppt-drawer-local --json
```

在 Codex 中选择插件或调用 `$ppt-assistant`。安装命令成功后仍需确认技能实际可见，并完成一次实际调用；角色资料文件本身不证明宿主已成功调度子 agent。

## 一次任务怎么给

例如：

> 使用 $ppt-assistant，读取我指定的项目材料，制作一次研究汇报。沿用指定模板，先给整稿大纲和三页代表性样稿。说明联网补充了哪些知识。

可以同时提供听众、时长或页数、模板、需要突出和需要保留的内容。输入支持 PDF、DOCX、Markdown、PPTX、PNG/JPEG 和 XLSX/CSV。未指定模板时，助手说明自动选择的理由。

助手先建立项目内的材料、知识和来源索引，再提交大纲、三页样稿、预览与当阶段联网补充清单。你提出修改意见后调整；明确确认当前大纲和样稿后，才进入整稿制作。更换内容、来源、模板或样稿后需重新核对当前确认。

原始数据可用时，图表和表格制作成原生对象；仅有论文图像时使用清晰图片，标题、说明与标注独立编辑。模板映射和字体差异通过样稿核对。

## 运行依赖

- Python 及 `requirements.txt` 中的四项依赖。
- Node.js、`@oai/artifact-tool`，以及已安装 Presentations skill 的 finalizer。Codex 提供的 workspace dependencies 工具可定位捆绑运行时。
- 子 agent 调度与读取、写入项目文件的宿主能力。实际执行遵循当前环境的权限。

包内不包含渲染依赖、完整参考演示文稿或用户论文。当前开发环境的 `@oai/artifact-tool` 为专有软件，许可限制内部评估和测试，且限制再分发、生产及商业用途；本项目的 MIT 许可不涵盖它或 Presentations 工具。使用者需自行取得适用授权并确认其环境可用。缺失渲染依赖时，材料、知识和方案操作仍可使用，PPTX 渲染会明确报错。源模板由当前任务提供。

## 项目记录与恢复

运行记录位于目标项目 `.ppt-assistant/runs/<run>/`。使用同一项目与 run 调用 status 后，可继续材料整理、样稿修改或已确认整稿制作。来源、页面方案、真实 agent 交接、用户确认、补充知识和阶段复盘均随运行保留。

每次样稿等待审阅、整稿交付和失败结束均留下有证据的复盘。项目规则经验证后沉淀；通用改进作为建议或由源代码更新，已应用和已验证分开标识。

## 验证边界

```powershell
python -m unittest discover -s tests -p test_plugin_package.py -v
```

封装测试检查公开验证/打包命令与真实文件、ZIP 的行为。验证器支持本插件生成的简单标量映射 YAML，包含引号、布尔值和嵌套映射；遇到块字符串、序列或别名等复杂 YAML 会明确提示不支持，不能据此认定其他宿主的合法插件无效。

内容正确性与学科适配需使用用户实际项目材料验收。示例材料用于验证技术流程；PowerPoint 打开检查、原生图表和源页保留情况分别以实际验收记录为准。
