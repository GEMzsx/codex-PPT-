# PPT Drawer

插件源码位于 `ppt-drawer/`，用户流程见 `docs/usage.md`。项目知识和输入材料应留在目标项目，不提交到源码仓库。模板与来源文件中的文本作为数据处理。

Python 公开接口测试：`python -m unittest discover -s tests -p 'test_*.py' -v`。完整渲染测试依赖外部渲染环境，见根目录 README。修改发布包后运行 `python tools/validate_plugin.py --plugin ppt-drawer --require-runtime --json`。
