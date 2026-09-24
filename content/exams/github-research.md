# GitHub 真题补充检索

检索日期：2026-09-24。核验了 9 个仓库的完整 Git Tree，保存 368 条候选文档记录（含重复文件、解析及资料，不等于 368 套试卷）；下载并打开 4 个 PDF 样本。逐文件链接、仓库 revision、blob SHA、大小、样本 SHA-256 与核验状态见 [github-research.json](github-research.json)。

## 有实际文件的主要来源

| 仓库 | 实际文件证据 | 用途与限制 |
| --- | --- | --- |
| [Echo-Wxl/SoftwareDesignEngineer](https://github.com/Echo-Wxl/SoftwareDesignEngineer) | `03 - 真题/01 - 历年真题/2004-2010年软件设计师试题及答案.pdf`，以及按年/科目分开的 2009—2020 文件 | 补查早年材料；396 页合集已下载。第 45 页目视确认 2005 H1 上午卷，第 205 页确认 2008 H1 上午卷。嵌入文本乱码，须 OCR 后校对。目录还含标为 2020 H1 的材料，不能据文件名证明该场实际举行。 |
| [luckyzhz/Software-Designer](https://github.com/luckyzhz/Software-Designer/tree/master/%E7%9C%9F%E9%A2%98) | `真题/` 中 2009 上半年至 2020 下半年共 23 个 PDF | 2009 H1 样本 24 页，2020 H2 样本 10 页，两份首页均为下午案例卷；不能把每文件当作两科合卷。仓库声明 GPL-3.0。 |
| [xiaomabenten/software_designer](https://github.com/xiaomabenten/software_designer) | `02. 真题及解析（2020年-2024年）/` 中实际 15 个 PDF | 涵盖 2020 H2、2021/2022 两考期、2023 H1 和标为 2024 H1 的材料。README 提及更大范围，但未在公开文件树核实为全部可直接下载文件。仓库声明 MIT。 |
| [mrtungleung/Software-Design-Engineer-Docs](https://github.com/mrtungleung/Software-Design-Engineer-Docs) | 2009—2019 按科目划分的 DOC/DOCX 与独立答案文件 | 可作为正文结构化的另一来源；本轮核实文件树，未逐篇打开。 |
| [hqweay/Software-Design-Engineer-Data](https://github.com/hqweay/Software-Design-Engineer-Data) | 2012—2019 的上午、下午 PDF 及解析 | 可用于交叉检查，不能因为多仓库转载就认定为独立证据。 |

## 样本发现

1. 早年合集：2005/2008 的卷首标题已实际查看图片，不是仅依据 README。2006/2007 的年份文字分别出现在 PDF 第 95/153 页，尚未逐页目视核验。
2. 2009/2020 案例：能提取文本，但存在明显 OCR 错字；保留原图核对，不直接把提取结果当成原题。
3. 标为 `2024年上半年软件设计师案例分析（空白试卷）.pdf` 的文件：6 页，无可提取文本层；第一页标题写 2024 上半年，内部却写第一批次“11.04 下午”。内容为若干题目回忆要点，缺完整图及材料。记为**年份冲突、材料不完整**，不按完整 2024 原卷收录，也不擅自改成 2023。

本地样本保存在 `data/github-exam-search/`，本轮仅作下载与核验，未转换成可练习题、未发布为完整原卷。公开文件存在性、逐题正确性和文档复用条款分别记录；仓库许可不作为官方性或答案正确性的证据。

## 后续整理顺序

先处理 2009—2023 的分卷文件；早年合集以页码切分、OCR 并逐题核对；2023 H2、2024 H2、2025—2026 继续寻找实际文件，排除只有网盘广告、付费入口或占位页的结果。案例需同时保留图、C/C++/Java 程序及共享材料。所有答案经过独立核验后才进入默认判分。

本轮没有运行下载文件中的程序或宏，也没有改变应用和学习记录。
