# 检索、来源与发布规则

统一执行：登记考点 → 术语/别名 → 原理资料 → 考试样本 → 推导核验 → 练习变式 → 来源记录 → 审校。技术结论采用 primary sources；试卷来源不等同于答案权威性。

| 板块 | 检索模板 | 优先来源与核验对象 |
|---|---|---|
| B01 | `<concept> representation / cache / scheduling / semaphore`；`软件设计师 <考点> 计算 条件` | ISA/IEEE、OSTEP、系统官方资料；位宽、单位、命中代价、并发时序、死锁条件 |
| B02 | `C <term> WG14`；`compiler <phase> university notes` | WG14、GCC、LLVM、高校编译课程；语言标准、未定义行为、作用域、推导是否合法 |
| B03 | `<algorithm> correctness complexity lecture`；`软件设计师 算法 <题型>` | 教材作者、高校算法课程；前提、不变量、反例、渐近界、边界输入 |
| B04 | `<relational concept> database textbook`；`SQL <feature> documentation` | 数据库教材作者、数据库官方文档；依赖闭包、无损分解、SQL方言、NULL与事务 |
| B05 | `<engineering concept> SWEBOK`；`<testing technique> ISTQB` | IEEE、ISTQB、公开高校资料；过程适用性、DFD平衡、覆盖蕴含、估算假设 |
| B06 | `UML <diagram> OMG`；`C++ <feature> standard`；`<pattern> roles` | OMG、WG21、语言实现文档；UML多重度、生命周期、虚析构、模式角色与业务条件 |
| B07 | `<protocol> RFC`；`<security concept> NIST` | IETF RFC、NIST及标准机构；地址边界、协议版本、安全性质和威胁模型 |
| B08 | `<mathematics> university`；`<law title> gov.cn`；`<standard> ISO` | 高校、政府原文、标准组织；数学前提、法规施行日期、历史/现行版本、英文语境 |
| EXAM | `<year> 软件设计师 <综合知识/应用技术> <上半年/下半年> 真题` | 考试机构、出版社及逐卷历史索引；实际科目、批次、题序、图片、是否占位或回忆版 |

## 记录与停止条件

1. `sources.json` 记录实际执行的查询与打开的 URL；从目录遍历得到的链接写“索引遍历”，不能冒称逐年搜索。
2. 来源 `locator` 定位到章节、条款、页码或题号；首次链接查验不能保证永久可用，保留访问日期。
3. 转载源共享同一个上游时不能算独立交叉证据。正文来自哪份资料、答案由谁推导分别记录。
4. 未获得可用正文、缺图或答案争议时，写明缺口和恢复条件，继续完成其他考点；不以生成题代替历年真题。
5. 题目共享材料只放已知条件，不提前给待求结果。评分要点必须具体，禁止截断答案当 rubric。
6. 校验程序证明数据结构与指定算例；内容作者仍需检查概念、边界和错误选项。自审不是官方审定。

## 检索接口

- `GET /api/catalog`：板块、教学单元、考点元数据与覆盖状态。
- `GET /api/topics?q=&module=&page=1&page_size=20`：名称、别名和正文的多词匹配；不返回完整正文。
- `GET /api/topic/{id}`：考点正文与来源引用。
- `GET /api/questions?module=&topic=&type=&difficulty=&origin=&q=&page=1&page_size=20`：题目摘要。`status=all` 可查待核验条目，但不能提交判分。
- `GET /api/papers?year=&session=&subject=&batch=&page=1&page_size=20`：试卷索引与检索覆盖；`GET /api/paper/{id}` 保留原题序。

题目列表和题干接口采用字段白名单；答案、核验说明及 rubric 只在提交或主动查看后显示。既有单选自动判分、主观自评逻辑继续使用。
