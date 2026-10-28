# 本地工作流接口

从本文件所在目录向上三级得到插件根；入口为 `scripts/ppt_drawer.py`。用当前可用 Python 执行，Node 渲染器为 `runtime/js/render.mjs`。先查看入口与所用子命令的 `--help`，参数事实以安装包中的帮助为准。

所有任务用 `--project <目标项目>` 与 `--run <本次运行ID>` 定位项目 `.ppt-assistant/runs/<run>/`。读取时优先加 `--compact`，需要正文时再读取运行目录中的材料文件。

| 子命令 | 使用时机与补充参数 |
| --- | --- |
| init | 初始化本次运行；`--title`，可选 `--brief` JSON 文件 |
| ingest | 导入指定材料；`--input` 文件或目录，可重复 |
| knowledge | 登记知识 JSON；`--input` |
| supplement | 登记联网补充 JSON；`--input` |
| plan | 提交页面方案 JSON；`--input` |
| render | 制作；`--stage sample` 或 `--stage full`，可按环境设置 `--node`、`--renderer`、`--output` |
| approve | 记录用户当前确认；`--statement` 实际原文，可选 `--reviewer user` |
| status | 恢复前读取当前阶段、产物与确认状态 |
| handoff | 记录实际子 agent；`--role`、`--agent-id`、可重复 input/output 路径、status、summary |
| retro | 记录本阶段复盘；`--stage sample/full/failure`、`--input` |
| finish | 确认当前整稿与交付复盘完整后结束 |

`register-sample --directory` 与 `register-full --directory` 用于登记外部制作产物；仍需满足运行时报告和确认要求。普通制作通过 render 入口。

知识输入为条目数组，每条有 `id`、`kind`、`text`、`source_ids`。联网补充输入为数组，每条有 `id`、`knowledge`、`url`、`purpose`、`slide_ids`。具体类型与校验消息以当前帮助和运行时结果为准，先使用项目真实来源再登记。

删除或重命名页面 ID 前，先用 supplement 将受影响条目的 `slide_ids` 清空为 `[]`（尚未用于页面），再提交新 plan，最后补上新的页面对应。存在失效映射时，plan 原子拒绝且保留原方案与确认；制作前也复验映射。仅修改标题等内容而保留页面 ID 时，对应关系可以继续使用。

渲染产物应有 `deck.pptx`、预览与 `render-report.json`，报告带阶段、页面 ID、方案哈希、原生对象统计和问题。完整稿需通过 Python 工作流的当前确认检查；直接调用 Node 制作适配器不授权整稿阶段。

Python 依赖见[声明](../../../requirements.txt)。Node 需要 `@oai/artifact-tool`；使用调用环境已提供的包路径，或显式提供 `PPT_DRAWER_NODE_MODULES` / `NODE_PATH`。图表完成处理使用已安装 Presentations skill 的 finalizer，并通过 Python 创建图表的可编辑工作簿；可用 `PPT_DRAWER_PRESENTATIONS_SKILL`、`PPT_DRAWER_PYTHON` 指定实际位置和执行程序。缺失时报告依赖缺口，按当前宿主权限处理执行。

依赖保留在环境中，不复制进插件。当前实现优先验证 Windows 和 PowerPoint，最终是否在 PowerPoint 中打开过以实际检查为准。
