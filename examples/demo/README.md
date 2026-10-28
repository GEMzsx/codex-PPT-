# 技术演示

本示例的时间数据和图片均为构造素材，只用于验证软件流程，不代表科研实验结果。

在源码目录对新建或空项目运行：

```powershell
python tools/demo_workflow.py --project ./output/demo --phase prepare
python tools/demo_workflow.py --project ./output/demo --phase sample
python tools/demo_workflow.py --project ./output/demo --phase gates --simulate-review
python tools/demo_workflow.py --project ./output/demo --phase full --simulate-review
python tools/demo_workflow.py --project ./output/demo --phase verify
```

模拟确认只适用于未修改的技术演示。实际任务的整稿需要用户确认当前大纲和样稿。完整渲染另需已授权的渲染依赖，见根目录 README。
