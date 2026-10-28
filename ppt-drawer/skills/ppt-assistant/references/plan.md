# 页面方案 v1

方案是 JSON，包含 `version: 1`、`title`、`style`、`slides`；需要源稿时加 `template` 的实际 PPTX 路径。`style` 可以是目录中的风格 ID，或运行时支持的自定义对象。`sample_slide_ids` 指定三页代表页，省略时运行时采用前三页。

每页包含唯一 `id`、`title`、`layout`、`takeaway`、`source_ids`、`blocks`。使用实际导入材料的来源 ID；素材块也标明相应 `source_id`。科学表述与知识条目的来源一致。

支持的基础布局为 `cover`、`title-content`、`two-column`、`evidence-grid`、`chart-table`、`process`、`summary`。从风格目录选择内容意图，再按这些布局表达；额外支持项以当前运行时验证为准。

| 内容块 | 必要内容 |
| --- | --- |
| text | `text` 或 `items` |
| image | 实际 `path`、`caption`、`source_id` |
| chart | `chart_type` 为 bar/line、`categories`、`series`（name、values）、`source_id` |
| table | `headers`、`rows`、`source_id` |
| process | `steps`，每步有 title 与可选 text |

图表和表格使用原始数据；保持类别、序列维度和有限数值。图片以实际素材路径读取，按原比例安排。图中已有坐标和图例保持清晰。

## 源页映射

需要在源 PPTX 页面上制作时，可为每页提供 `template_slide`（从 1 开始）、`template_preserve_names`（明确保留的源对象名），以及需要原位替换文字的 `template_title_name`、`template_takeaway_name`、`template_page_number_name`。先检查源文件中的实际对象名，仅将需要的固定视觉元素列入保留名单，科学内容按当前项目安排。

渲染报告说明实际采用源页映射、混合模式或主题与母版导入，并列明对象保留范围。该范围需要在样稿中核对，不把导入主题等同于完整保留源页面。

提交方案后，工作流保存的当前 `plan.json` 为制作输入。更改方案、来源或样稿会使旧确认失效；通过当前状态和确认流程继续。
