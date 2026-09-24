"""Build the evidence-only software-designer exam catalog.

This helper deliberately stores no third-party question text.  The discovered
pages do not grant a clear licence to redistribute the examination content.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests


ROOT = Path(__file__).parent
AS_OF = "2026-09-24"
HISTORY_INDEX = "https://www.cnitpm.com/zhenti/rs.html"

SPECIAL_SOURCES = {
    (2005, "H1", "applied"): "https://www.cnitpm.com/examst/535589/",
    (2015, "H1", "comprehensive"): "https://www.cnitpm.com/examst/545537/",
    (2015, "H1", "applied"): "https://www.cnitpm.com/examst/811020/",
    (2024, "H2", "comprehensive"): "https://www.cnitpm.com/pm1/165691mnwaztek44.html",
    (2024, "H2", "applied"): "https://www.cnitpm.com/pm1/1656926sw0ycginq.html",
    (2025, "H1", "comprehensive"): "https://m.cnitpm.com/exam/ExamST.aspx?sid=13354690&t1=4",
    (2025, "H1", "applied"): "https://www.cnitpm.com/Examst/13495484/",
    (2025, "H2", "comprehensive"): "https://www.cnitpm.com/examst/13660772/",
    (2025, "H2", "applied"): "https://adg.csdn.net/694cf32e5b9f5f31781aa07c.html",
    (2026, "H1", "comprehensive"): "https://m.cnitpm.com/exam/ExamST.aspx?sid=14505743&t1=4",
    (2026, "H1", "applied"): "https://www.educity.cn/rk/5513242.html",
}


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.href: str | None = None
        self.text = ""
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.text = ""

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.href is not None:
            self.anchors.append((self.text, self.href))
            self.href = None


def history_urls() -> dict[tuple[int, str, str], str]:
    """Extract direct paper links from the live historical index.

    The index orders each year as H2 comprehensive/applied, then H1
    comprehensive/applied.  2020 has only the two H2 entries.
    """
    response = requests.get(HISTORY_INDEX, timeout=30)
    response.raise_for_status()
    parser = _AnchorParser()
    # The page declares UTF-8 but is served with mojibake on some mirrors.
    # ASCII years and hrefs, which are all that this extractor uses, survive.
    parser.feed(response.content.decode("latin1", errors="replace"))
    by_year: dict[int, list[str]] = {}
    for text, href in parser.anchors:
        match = re.search(r"20(?:0[5-9]|1[0-9]|2[0-4])", text)
        if not match or not ("/examst/" in href.lower() or "/pm1/" in href.lower()):
            continue
        by_year.setdefault(int(match.group()), []).append(urljoin(HISTORY_INDEX, href).replace("http://", "https://"))
    result: dict[tuple[int, str, str], str] = {}
    order = (("H2", "comprehensive"), ("H2", "applied"), ("H1", "comprehensive"), ("H1", "applied"))
    for year in range(2005, 2025):
        expected = 2 if year == 2020 else 4
        links = by_year.get(year, [])
        if len(links) != expected:
            raise RuntimeError(f"historical index yielded {len(links)} links for {year}, expected {expected}")
        for key, url in zip(order, links):
            result[(year, *key)] = url
    return result


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_for(year: int, session: str, subject: str, paper_id: str, indexed_urls: dict[tuple[int, str, str], str]) -> dict[str, str]:
    url = SPECIAL_SOURCES.get((year, session, subject), indexed_urls.get((year, session, subject), HISTORY_INDEX))
    label = "综合知识" if subject == "comprehensive" else "应用技术"
    half = "上半年" if session == "H1" else "下半年"
    return {
        "id": f"EXAM-{year}-{session}-{subject.upper()}-S01",
        "title": f"{year}年{half}软件设计师{label}页面或索引",
        "url": url,
        "author": "信管网" if "cnitpm.com" in url else ("希赛网" if "educity.cn" in url else "第三方考生回忆页面"),
        "accessed_on": AS_OF,
        "locator": f"页面标题/索引项：{year}年{half}软件设计师{label}",
        "version": "web page accessed 2026-09-24",
        "kind": "exam_index",
        "reuse_policy": "link-only; page does not provide a clear licence for redistributing exam text; no question text copied",
        "query": f"{year}年 {half} 软件设计师 {label} 真题",
        "selection_reason": f"用于确认 {paper_id} 的页面存在性与来源定位；不据此宣称官方发布或完整原卷。",
    }


def main() -> None:
    indexed_urls = history_urls()
    entries: list[dict[str, object]] = []
    paper_count = 0
    for year in range(2005, 2027):
        for session in ("H1", "H2"):
            for subject in ("comprehensive", "applied"):
                paper_id = f"SD-{year}-{session}-{'COMP' if subject == 'comprehensive' else 'APPL'}-U"
                if year == 2020 and session == "H1":
                    entries.append({
                        "year": year,
                        "session": session,
                        "subject": subject,
                        "batch": "unknown",
                        "paper_id": paper_id,
                        "status": "missing",
                        "source_urls": ["https://www.miiteec.org.cn/news_details?code=1002"],
                        "note": "工信部教育与考试中心于2020-03-04公告推迟上半年考试；本轮未找到可核验试卷或最终取消公告，故不写 not_held。",
                    })
                    continue
                if year == 2026 and session == "H2":
                    entries.append({
                        "year": year,
                        "session": session,
                        "subject": subject,
                        "batch": "unknown",
                        "paper_id": paper_id,
                        "status": "not_held_yet",
                        "source_urls": ["https://hrss.sz.gov.cn/szksy/zxxx/content/post_12939472.html"],
                        "note": "官方考试通知列明2026-10-24至27日开考；截至2026-09-24尚未举行。",
                    })
                    continue

                source = source_for(year, session, subject, paper_id, indexed_urls)
                recent_recall = year >= 2025
                notes = (
                    "考生/学员回忆或考后整理页面；未核验为官方原卷，且页面未授予明确转载许可，故仅建索引。"
                    if recent_recall
                    else "第三方历史真题索引；未逐题核验完整性、答案与官方性，且无明确正文转载许可，故仅建索引。"
                )
                paper = {
                    "id": paper_id,
                    "title": f"{year}年{'上半年' if session == 'H1' else '下半年'}软件设计师{'综合知识' if subject == 'comprehensive' else '应用技术'}",
                    "year": year,
                    "session": session,
                    "subject": subject,
                    "batch": "1" if (year, session, subject) == (2025, "H1", "comprehensive") else "unknown",
                    "origin_kind": "recalled",
                    "completeness": "index_only",
                    "answer_status": "pending",
                    "question_ids": [],
                    "source_ids": [source["id"]],
                    "notes": notes,
                }
                out = ROOT / str(year) / session / paper_id
                dump(out / "paper.json", paper)
                dump(out / "sources.json", [source])
                coverage_status = "unverified" if (year, session, subject) in {
                    (2024, "H2", "applied"),
                    (2026, "H1", "applied"),
                } else "index_only"
                if coverage_status == "unverified":
                    notes += " 页面内容表现为考前占位、往年示例或未证实已更新，不能确认其为该场次实际试卷。"
                entries.append({
                    "year": year,
                    "session": session,
                    "subject": subject,
                    "batch": "1" if (year, session, subject) == (2025, "H1", "comprehensive") else "unknown",
                    "paper_id": paper_id,
                    "status": coverage_status,
                    "source_urls": [source["url"]],
                    "note": notes,
                })
                paper_count += 1

    coverage = {
        "as_of": AS_OF,
        "scope": "软件设计师，2005年至2026-09-24；综合知识与应用技术；仅收录可核验定位且遵守来源许可的内容",
        "entries": entries,
        "summary": {
            "coverage_entries": len(entries),
            "paper_records": paper_count,
            "question_records": 0,
            "index_only": paper_count - 2,
            "unverified": 2,
            "missing": 2,
            "not_held_yet": 2,
            "direct_paper_urls": paper_count,
            "statement": "专项部分完成，未声称集齐真题。历史索引和回忆页面均缺少明确正文再发布许可，因此本轮只保存元数据与直接链接证据。",
        },
    }
    dump(ROOT / "coverage.json", coverage)


if __name__ == "__main__":
    main()
