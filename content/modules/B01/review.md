# B01 内容审查记录

审查日期：2026-09-24

## 范围与数量

- 冻结考点：10/10；正文：10 篇；原创练习：83 道，其中四选一 20 道、简答 63 道。
- 各考点题量：T01 9、T02 6、T03 8、T04 8、T05 8、T06 8、T07 8、T08 8、T09 8、T10 12。
- 本模块只声称覆盖 `content/curriculum.json` 冻结的 B01 考点；未声称逐条覆盖尚未取得全文的官方考试大纲细目。

## 来源检索与复用

实际搜索并打开 Intel 处理器手册、IEEE 754-2019 标准页面、OSTEP 作者站 PDF、Linux kernel block 文档，以及 IBM RAID、SAN/NAS 页面。`sources.json` 记录检索词、URL、访问日期和具体 locator。所有练习为原创，没有复制商业题库、回忆题或来源中的章末题；来源仅用于核对定义与模型。

## 正文与题目核验

- T01：用模 256、符号位判据复核补码、符号扩展和两类溢出。
- T02：用二进制展开与对阶复核规格化、舍入和特殊值条件。
- T03：逐项区分取指寄存器与有效地址，复核直接/间接访问层次。
- T04：用容量/块大小/相联度三式复核地址位；分别核验“miss 额外时间”和“miss 总时间”公式。
- T05：用拍数时间线、Amdahl 时间比例及串并联概率补集复核。
- T06：画 Gantt 顺序并以 turnaround、waiting、response 定义交叉复核。
- T07：以 `empty+full=N` 和临界区许可不变量复核 P/V 次序。
- T08：逐轮记录 Work、Need、Allocation 复核安全序列；区分 unsafe 与 deadlock。
- T09：地址除法复核 VPN/offset/PFN；FIFO 序列由 `verify.py` 模拟。
- T10：逐段绝对差复核磁头移动量；索引容量分步换算；RAID 容量按等容量磁盘模型计算，RAID 10 另检查失效分布；SAN/NAS 按 block/file 抽象核对。

## 已知边界

Intel 是具体体系结构资料，正文中的通用 CPU/Cache 模型只在题设参数下使用。IEEE 标准正文需付费，公开页面仅核对标准范围，具体 binary32 常识按公开格式独立核算。不同教材可能采用负值信号量记等待人数；本模块明确采用“无许可即阻塞”的抽象语义，不依赖内部负值表示。

## 自动检查

运行 `python content/modules/B01/verify.py`：检查 JSON 可解析、合同必填字段、题目 ID/数量、`unit_id` 运行时规则、四选一答案与逐项错因、简答题专属 rubric、正文必备章节，并独立验证补码、Cache、流水线、PV、死锁、分页、FIFO、磁盘与 RAID 计算。结果记录为 `B01 verification passed: 10 topics, 83 exercises (20 single-choice)`。
