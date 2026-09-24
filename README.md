# 软考虐待狂 · 软件设计师学习台

结构化知识库 v3：8 个板块、81 个考点，C++ 主线与 C 算法训练。原 SE 系列 24 题与 CSF 系列 18 题及其记录保留。内容数量以自动生成的 [覆盖报告](content/generated/coverage.json) 为准。

真题专项目前仅完成 2005—2026 年场次矩阵与 84 份逐卷来源记录，**真题正文 0 题、完整收录 0 卷**，不能作为已建成的历年刷题库。缺口及检索证据见 [真题审查报告](content/exams/review.md)。

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

- 计算机系统与操作系统、程序语言与编译、数据结构与算法、数据库、软件工程、面向对象/UML/C++、网络安全、数学与综合基础。
- 按板块、教学单元和考点组织正文；支持标题、别名和正文关键词搜索。
- 题目按板块、考点、题型、难度、来源组合筛选并分页；案例保留共享材料、配图与子问题。未核验题目不进入默认练习或掌握统计。
- 真题按年份、考期、科目与批次查阅来源、完整度、回忆版性质及缺口，明确区分索引和正文。
- 首页按“学新知识 / 错题再练 / 单元自测”安排任务，切换立即预览具体内容、题数和预计用时；自测可选择已学单元。
- 各模式的未完成任务与草稿独立保存；完成后回顾待巩固题目并进入对应讲解。阅读位置、答题草稿、笔记自动保存。
- 选择题自动反馈；简答、代码题保留原答案并按要点自评。绿色 ✔ 表示正确/自评通过，红色 ❌ 表示错误/自评待巩固，待自评用中性色。
- 标记不确定、错题再练、作答记录、首答统计、备份恢复。
- 页内保存试用反馈，回顾页导出反馈文本；不自动发送。

## 数据

学习记录保存在 `data/study.sqlite3`。回顾页可导出 v3 备份 JSON，包含内容版本、内容快照与学习记录；支持已知 v1/v2 备份和未修改的旧 v3 内容子集。恢复前完整校验并备份原记录到 `data/backups/`，损坏备份不会替换记录。

本版只在这台电脑使用。跨设备同步、自动间隔复习、完整周总结和考试模考在后续阶段；目前错题再练基于最新答错或不确定的结果，每组最多五题；单元自测也为最多五题的小组练习。

代码题用于阅读、填空与解释，不运行用户输入。新题为参照历年题型的原创练习，不是历年原题；自评结果不是考试成绩。

新增内容使用 B01—B08 独立编号。SE-* 和 CSF-* 的含义及历史记录不变，知识库页保留原有专题与基础归档入口。升级前 v2 备份路径仍为 `data/backups/before-curriculum-v2-*.json`。

## 开发与验证

内容维护先读 [统一规范](docs/content-guide/README.md)、[板块检索规则](docs/content-guide/search-rules.md) 与 [模板](docs/content-guide/templates.md)。本轮实施与验收见 [specs/003-knowledge-bank](specs/003-knowledge-bank)，先前试点记录仍保留在 specs/002-exam-alignment。

```powershell
E:\miniconda\python.exe scripts/build_content.py
E:\miniconda\python.exe -m pytest tests -q --basetemp=data/pytest-check
node --check static/app.js
```

修改 `content/modules/` 或 `content/exams/` 后先运行内容构建，再重启服务。只校验可加 `--check`。构建生成 `content/generated/` 与 JSON Schema；不要手改生成索引。每个板块的 `verify.py` 保留独立计算与语义检查。普通构建和学习使用不联网。

本地浏览器 QA 使用隔离数据库与端口，不会把测试记录混入用户学习数据。

`--basetemp` 指向专用测试临时目录，pytest 会清理该目录；不要改成课程或学习数据目录。已完成的检查及限制见 [verification.md](specs/003-knowledge-bank/verification.md)。
