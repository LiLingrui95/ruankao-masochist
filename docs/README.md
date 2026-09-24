# 软件设计师学习台：开发规范与执行入口

版本：3.0 · 2026-09-24 · 状态：八板块知识库已接入，真题正文收录仍有缺口。

当前入口是 [内容生产规范](content-guide/README.md)、[检索规则](content-guide/search-rules.md)、[编写模板](content-guide/templates.md) 和 [实施验收](../specs/003-knowledge-bank/verification.md)。已登记八板块、81 个考点；数量和考纲映射见 [生成报告](../content/generated/coverage.json)。旧专题与学习记录保留。

用户画像：学过 Python、C#，接触少量数据结构与算法，尚未系统学习计算机科学。目标：备考软考中级软件设计师，同时补齐理解考试内容所需的基础。

下表保留前期设计文档。与当前内容规模冲突的旧版数量及阶段目标，以 003 实施记录和内容索引为准。

| 文件 | 用途 |
| --- | --- |
| [开发规范](./development-spec.md) | 产品范围、SDD 工作流、业务规则、数据要求、验收标准 |
| [分阶段执行计划](./execution-plan.md) | 阶段依赖、具体任务、验收门槛、学习与开发如何配合 |
| [首阶段知识库与题库规范](./stage-0-content.md) | 8 个学习单元、48 题目标、内容生产规则、1 节完整课程与 6 题样例 |
| [自审与修订记录](./review-log.md) | 审查问题、修订结论、未验证事项 |

建议阅读顺序：先读执行计划，再读首阶段内容样例；开发人员或编码代理再完整阅读开发规范。

新增内容唯一维护源为 `content/modules/`、`content/exams/`、`content/curriculum.json` 和 `content/syllabus-map.json`。`scripts/build_content.py` 校验后生成索引，应用按需读取。SE-01 至 SE-03 仍由原 `content/pack.json` 与 `content/lessons/` 提供兼容入口；CSF 系列保留为选读归档。真题目前只有来源元数据，不能把 84 条目录记录计作 84 套已收录试卷。

SDD 在本项目中指 Specification-Driven Development。遵循先规格、后方案、再任务与实现的过程；可以接入 GitHub Spec Kit，但本轮没有安装或初始化该工具。
