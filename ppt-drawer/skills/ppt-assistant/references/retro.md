# 阶段复盘与优化

样稿提交等待审阅、整稿交付和失败结束时都留下记录。根据实际产物或失败证据，说明发现、原因、改进动作及验证状态；记录为空泛的“已检查”不能证明优化完成。

`retro --stage sample|full|failure --input <JSON>` 的输入：

```json
{
  "summary": "本阶段的具体结果",
  "findings": [
    {
      "observation": "实际观察到的问题或有效做法",
      "evidence": ["相关页面、报告或错误记录"],
      "action": "已做或建议的动作",
      "status": "proposed",
      "scope": "project"
    }
  ]
}
```

- `proposed` 表示建议；`applied` 需提供真实项目 `changed_paths`；`verified` 需 `validation` 证据。
- 科学知识、素材与项目经验保留项目归属。可复用的制作规则与确定性检查记录为 general 建议，经实际验证后再通过插件源代码更新。
- 需要沉淀项目规则时填写 `rule`；只有 verified、scope 为 project 且有 rule 的发现才由运行时写入项目改进记录。
- 修复后复查受影响页面；交付时分清已经验证、已应用待验证和建议事项。失败记录说明还能从何处继续。

样稿阶段先登记复盘再等待用户；整稿阶段按检查结果登记复盘并执行 finish。通用建议不直接修改安装缓存。
