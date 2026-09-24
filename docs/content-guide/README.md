# 内容生产合同 v1

目标：软件设计师，C++ 主线、C 算法；中文讲解、English 字段。日期 2026-09-24。

## 唯一维护源与边界
每个板块代理只写 content/modules/Bxx/。真题代理只写 content/exams/。主任务维护公共索引、Schema、应用、测试。禁止覆盖旧 SE/CSF 内容、修改数据库或提交 Git。
content/curriculum.json 冻结首轮考点 ID；可在所属主题下扩充正文，不自行改变公共 ID。跨板块引用而非复制。每 3 个相邻考点属于一个教学单元，module.json 必须给出有意义的单元标题。

## 文件合同
module.json: {id,title,description,objectives:[string],units:[{id,title,topic_ids:[string]}],topic_ids:[string],search_rules:[string]}。
sources.json 是数组。每项 {id,title,url,author,accessed_on,locator,version,kind,reuse_policy,query,selection_reason}。ID 以 Bxx-S 开头。打开实际来源页面；不能将搜索摘要写成阅读记录。至少 2 个真实来源；技术资料优先 primary sources。记录本地独立推导不等于虚构官方解析。
topics/<id>.json: {id,module_id,unit_id,title,aliases:[string],objectives:[string],prerequisite_ids:[topic-id],syllabus_refs:[string],body_path,source_ids:[string],version,review_status,minutes,exercise_target,exercise_rationale,question_ids:[string]}。
body_path 相对于 content 根目录，如 modules/B01/topics/B01-T01.md。minutes 取 5—10。review_status 为 reviewed 或 pending；只有实际自审并核验才能 reviewed。syllabus_refs 使用明确的章节名称；未核对官方细分编号时不得编造编号。
正文必须有 ## 考查目标、## 必要概念、## 原理与条件、## 推导例题、## 易错点与反例、## 自查、## 关联练习、## 出处。每篇至少 1 个完整推导例子，足够理解考点，通常 700—1400 中文字。不要为了凑字数重复话术。
exercises/<id>.json: {id,title,module_id,topic_ids:[string],unit_id,section_index:0,type,prompt,answer,explanation,source_ids:[string],answer_source_ids:[string],origin_kind,review_status,answer_status,verification,version,difficulty,minutes}。
**运行时 unit_id 等于主考点 ID**，并非教学分组 ID。这使每个考点作为短学习任务沿用现有学习记录。题 ID: Bxx-Tnn-Qnn 或 Bxx-CASE-nn。type 为 single_choice / short_answer / code_fill。difficulty 为 basic / applied / comprehensive。origin_kind 为 original / adapted / licensed / past_exam / recalled。answer_status 为 verified / pending / disputed。verification 是非空字符串，准确说明手算、真值表、运行等证据。
single_choice: options 是 {A:文本,B:文本,C:文本,D:文本}，answer 为 A/B/C/D；option_explanations 每选项一条。
short_answer/code_fill: answer 为参考文本；rubric 为 [{id:"r1",text:"具体评分要点"},...]（至少 2 项）。code_fill 另带 code、language、reference_fill。不能把自评描述成考试分数。
案例使用 short_answer + case_material:string + subquestions:[{id,prompt,points}]，共享材料完整，图可用 assets 中 SVG 或 Markdown 表格。子问题不能含答案；参考答案仍在顶层 answer。可选 assets:[{path,alt}]，path 相对 content 根。
每题必须有完整独立解析，不用一个模板替代答案。引用既有 SE 题通过 question_ids 引用；不要复制旧题改 ID 凑数。

## 题量和审校
少变化考点 3—4；常规应用 5—8；复杂考点 8—12。exercise_target 按实际难度明确目标，question_ids 必须达到目标，题目主考点计数，变式应有不同推理或边界。算法、数据库、DFD、UML、C++ 模式各至少 3 组完整案例，案例可归属综合考点。
可复用有许可或用户提供的题目。版权不明的商业整题不能批量抄录；可记录定位后自行编题，不做只换数字的伪原创。第三方回忆题不能标成正式原卷。
数学或代码核验可写 verify.py 到本板块目录，运行证据写 review.md。代码无法编译时只能写手工/独立模型核验。审查单位、边界、唯一答案、引用真实可达，未知写 gap。
review.md 应记录每篇/题的核验方式、搜索结果、缺口和数量，不能声称覆盖了未经核验的完整官方大纲。

## 真题合同
coverage.json: {as_of,scope,entries:[{year,session,subject,batch,paper_id,status,source_urls:[string],note}],summary}。session H1/H2；subject comprehensive/applied；未知批次 unknown。未举行与未找到必须区分。
每试卷 content/exams/<year>/<session>/<paper-id>/paper.json: {id,title,year,session,subject,batch,origin_kind,completeness,answer_status,question_ids:[string],source_ids:[string],notes}，completeness complete/partial/index_only/missing。
同目录 sources.json 同来源格式，ID EXAM-*。questions 与练习合同兼容，可加入 original_number,points,paper_id，未对齐考点 topic_ids 可为空并注明。未核验/不完整条目只查阅，不进入自动判分。真题没有可收录正文时保留完整检索与缺口证据，不以自编题冒充，不默认下载版权不明的商业全卷。

## 发布
主任务运行 scripts/build_content.py 校验并生成 content/generated/library.json、coverage.json、search.json。agents 不修改生成文件。只有 reviewed 且 verified 题目进入默认练习。备份与旧记录兼容由主任务处理。

