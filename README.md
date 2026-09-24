# 软考虐待狂 · 软件设计师学习台

前三单元内容试点：3 个单元、9 个小节、18 道原创基础题。

## 开始使用

打开 http://127.0.0.1:8765 。服务已启动时，无需重新运行脚本。

电脑重启后，双击 `start-study.cmd`，会启动服务并打开浏览器。也可以在本目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File D:\study\start-study.ps1
```

也可使用 Python 手动启动，再打开上述地址：

```powershell
E:\miniconda\python.exe D:\study\app.py
```

首次在其他环境使用时，先安装 requirements.txt 中的依赖。本机已具备这些依赖。Python 3.10 或以上。

## 已有内容与功能

- 程序与数据、顺序/条件/循环、数组/索引/遍历，每单元 3 小节。
- 每单元 4 道选择题、1 道简答、1 道代码题，完整参考解析与来源。
- 按时长安排有限任务；阅读位置、答题草稿、笔记自动保存。
- 选择题自动反馈；简答、代码题保留原答案并按要点自评。
- 标记不确定、错题再练、作答记录、首答统计、备份恢复。
- 页内保存试用反馈，回顾页导出反馈文本；不自动发送。

## 数据

学习记录保存在 `data/study.sqlite3`。回顾页可导出含课程与记录的备份 JSON。恢复时校验版本和记录结构，确认后替换，原记录备份在 `data/backups/`。

本版只在这台电脑使用。跨设备同步、自动间隔复习、完整周总结和考试模考在后续阶段；目前“错题再练”是基于最新结果的筛选。

代码题用于阅读、填空与解释，不运行用户输入。题目均为原创基础题，不是真题；自评结果不是考试成绩。

## 开发与验证

总体规划见 [docs/README.md](docs/README.md)，本 feature 的规格、方案与验证见 [specs/001-study-session](specs/001-study-session)。

```powershell
E:\miniconda\python.exe -m pytest tests -q --basetemp=data/pytest-check
node --check static/app.js
```

本地浏览器 QA 使用隔离数据库与端口，不会把测试记录混入用户学习数据。

`--basetemp` 指向专用测试临时目录，pytest 会清理该目录；不要改成课程或学习数据目录。已完成的检查见 [verification.md](specs/001-study-session/verification.md)。
