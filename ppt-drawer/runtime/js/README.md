# 页面制作适配器

从页面方案 v1 制作 PPTX 与真实 PNG 预览。用户流程通过 Python 工作流调用本适配器，完整稿的审阅确认由该工作流验证。

```text
node render.mjs --plan plan.json --output new-output --stage sample
node render.mjs --plan plan.json --output another-output --stage full
```

输入可含 `template`，或用 `--template source.pptx` 指定模板。输出目录中的 `deck.pptx` 已存在时拒绝覆盖。`render-report.json` 提供输入方案哈希、页序、原生对象统计、预览列表与限制说明，阻塞问题放在 `errors` 并以非零状态退出。

## 运行时

这些依赖独立于本项目许可证。本仓库不分发它们；开发环境中的 `@oai/artifact-tool` 是专有软件，许可限于内部评估和测试，且限制再分发及生产、商业用途。请检查实际取得的依赖许可和使用权。

- 需要已安装的 `@oai/artifact-tool`，优先通常的 Node 模块解析，其次 `PPT_DRAWER_NODE_MODULES`、`NODE_PATH` 与捆绑 Node 相邻的 `node_modules`。
- 需要已安装 Presentations 技能的最终化检查工具；从 `CODEX_HOME` 或用户目录的 `.codex/plugins/cache` 发现，可通过 `PPT_DRAWER_PRESENTATIONS_SKILL` 指定。
- 最终化检查调用捆绑 Python；可用 `PPT_DRAWER_PYTHON` 指定。检查完整的 literal chart 数据并创建新的工作簿快照，使 PowerPoint 可编辑图表数据。运行环境须允许这些检查子进程。
- 输出目录的父目录作为本次制作 workspace，独立的 `.ppt-drawer-build-*` 目录保留草稿与检查收据。`render-report.json` 的 `validation_receipt` 指向收据；PNG 是渲染结果，不能单独证明 PowerPoint 应用行为。

## 源页对象映射

仅提供模板时保留导入后的尺寸、主题与母版，报告明确说明手工放置的源页页眉和标志没有自动复用。

需要保留真实源页对象时，为各页提供 `template_slide`（从 1 开始）、`template_preserve_names` 或 `template_preserve_ids`。另可指定 `template_title_name`、`template_takeaway_name`、`template_page_number_name`，原位替换相应文本。名称重复时使用对应的 `template_title_id`、`template_takeaway_id`、`template_page_number_id`；ID 是源对象在公开 facade 中的 `id`，不是 inspect 的 `sh/...` 索引。

制作者先通过 Artifact Tool inspect/resolve 核对源对象及位置，形成明确映射。复制指定源页后只保留明示对象，删除其他源科研正文；新正文仍按本次项目方案制作。报告逐页列出实际保留的对象及源页，并将这种模式记为 `mapped_source_slides`。它表示保留了选定的原生对象，不表示所有原稿内容或视觉属性均已完整复刻。

## 本次验证

公开 `runRenderer(options)` 与命令行共用实现，供 Node 内置测试运行器在 `--test-isolation=none` 下执行。测试观察 PPTX、工作簿、页数、来源正文清理和 PNG 等公开产物，不依赖私有函数。源文件、生成物及草稿分别保存。
