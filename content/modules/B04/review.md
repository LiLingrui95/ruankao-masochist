# B04 审校记录

- 范围：`content/curriculum.json` 冻结的 B04-T01—B04-T10；未声称逐条核对未公开的官方细分大纲。
- 来源：2026-09-24 以检索词记录于 `sources.json`，实际打开 db-book 作者站 PDF、PostgreSQL 18 Constraints、SQL Tutorial、Transactions、Indexes/EXPLAIN 页面后采用。正文只作概念转述，61 题均标记 `original`。
- 正文：10 篇均按八个必需标题自审，含完整推导例、适用条件、反例和出处；SQL 方言明确为 PostgreSQL 18。
- 题量：T01 5、T02 5、T03 8、T04 8、T05 5、T06 5、T07 5、T08 5、T09 5、T10 10，共 61 题。均为 `short_answer`，逐题 rubric 指向本题结论与条件。
- 案例：3 组，均属 T10，分别为社区图书馆、门诊预约、仓储履约；共享材料、分问、分值和具体 rubric 完整。图书馆案例用 Markdown 表格展示对象、示例与基数。
- 独立核验：`verify.py` 运行闭包算法，核对候选键推导；使用二元无损判据并检查有损反例；用优先图核对有环/无环调度；以内存数据库实际执行 3 条可移植 PostgreSQL SQL 子集，核对外连接零计数、HAVING 与 NOT EXISTS。
- 已知边界：SQLite 仅用于验证上述 SQL 子集的结果集；PostgreSQL 特有的部分唯一索引、排斥约束只按 PostgreSQL 18 官方语义人工复核，未在本机 PostgreSQL 实例执行。

## 主任务补审
补充数据库访问、参数化及NoSQL建模正文，新增6道具体主观练习，共67题。新增来源实际打开；采用手工语义核验，未声称执行PostgreSQL或MongoDB部署。
