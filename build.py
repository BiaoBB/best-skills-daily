#!/usr/bin/env python3
"""
每天自动从 LinklyAI/best-skills 拉取最新榜单 CSV，
结合本地中文词典 zh_dict.json 生成单文件静态网页 index.html（零第三方依赖）。
"""
import csv
import io
import json
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_RAW = "https://raw.githubusercontent.com/LinklyAI/best-skills/main"
ROOT = Path(__file__).resolve().parent

CAT_ZH = {
    "design-media": "设计音视频",
    "dev-programming": "编程开发",
    "it-ops-security": "运维云安全",
    "content-creation": "内容社媒",
    "ai-agent": "Agent 底座",
    "knowledge-management": "知识检索",
    "education": "教育学习",
    "life-service": "生活服务",
    "data-analysis": "数据分析",
    "business-ops": "商业运营",
    "professional": "专业服务",
    "office-efficiency": "办公效率",
    "other": "其他",
}


def fetch_text(url: str, retries: int = 3, timeout: int = 20) -> str:
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "best-skills-daily-builder/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            last_err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"拉取失败 {url}: {last_err}")


def fetch_csv(rel_path: str) -> list[dict]:
    txt = fetch_text(f"{BASE_RAW}/{rel_path}")
    return list(csv.DictReader(io.StringIO(txt)))


def to_int(val: str):
    if not val:
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


def to_float(val: str):
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def fmt_wan(n) -> str:
    if n is None:
        return "—"
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return f"{n:,}"


def has_zh(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def lookup_zh(row: dict, zh_dict: dict, is_clone: bool) -> str:
    by_src = zh_dict.get("by_source_skill", {})
    by_skill = zh_dict.get("by_skill_fallback", {})
    source = row.get("source", "")
    skill = row.get("skill", "")
    cat_name = CAT_ZH.get(row.get("cat", "other"), "其他")
    raw_zh = (row.get("raw_zh") or "").strip()

    if is_clone and f"superpowers:{skill}" in by_src:
        return by_src[f"superpowers:{skill}"]
    if f"{source}:{skill}" in by_src:
        return by_src[f"{source}:{skill}"]
    if has_zh(raw_zh):
        return raw_zh[:140]
    if skill in by_skill:
        return by_skill[skill]
    if raw_zh:
        return raw_zh[:140]
    return f"新上榜技能（{cat_name}），暂未收录进本地中文词典，所属仓库：{source or row.get('vendor') or '未知'}。"


def build_topics(t7: list[dict], rs20: list[dict], sb: list[dict]) -> list[dict]:
    clean = [r for r in t7 if not r["is_clone"]]

    # 1. 今日增速黑马（非马甲、周环比 > 0）
    growers = sorted([r for r in clean if r["growth"] is not None and r["growth"] > 0],
                     key=lambda x: x["growth"], reverse=True)
    # 同仓库最多取 2 个，避免被单一套件刷满
    picked_growers = []
    repo_cap = Counter()
    for r in growers:
        if repo_cap[r["source"]] >= 2:
            continue
        picked_growers.append(r)
        repo_cap[r["source"]] += 1
        if len(picked_growers) >= 6:
            break

    # 2. 全网综合高分常青树（同时在 best-100 中名次靠前）
    evergreens = sorted([r for r in clean if r["br"] is not None], key=lambda x: x["br"])
    picked_ever = []
    repo_cap = Counter()
    for r in evergreens:
        if repo_cap[r["source"]] >= 2:
            continue
        picked_ever.append(r)
        repo_cap[r["source"]] += 1
        if len(picked_ever) >= 6:
            break

    # 3. 设计审美与音视频热门
    media_top = sorted([r for r in clean if r["cat"] == "design-media"],
                       key=lambda x: (x["recent"] or 0, x["total"] or 0), reverse=True)
    picked_media = []
    repo_cap = Counter()
    for r in media_top:
        if repo_cap[r["source"]] >= 2:
            continue
        picked_media.append(r)
        repo_cap[r["source"]] += 1
        if len(picked_media) >= 6:
            break

    # 4. 编程开发与工程工作流
    dev_top = sorted([r for r in clean if r["cat"] == "dev-programming"],
                     key=lambda x: (x["recent"] or 0, x["total"] or 0), reverse=True)
    picked_dev = []
    repo_cap = Counter()
    for r in dev_top:
        if repo_cap[r["source"]] >= 2:
            continue
        picked_dev.append(r)
        repo_cap[r["source"]] += 1
        if len(picked_dev) >= 6:
            break

    # 5. 国内新星精选（同厂商最多 2 个，兼顾多样性）
    picked_rs = []
    vendor_cap = Counter()
    for r in rs20:
        v = r["vendor"] or r["skill"]
        if vendor_cap[v] >= 2:
            continue
        picked_rs.append(r)
        vendor_cap[v] += 1
        if len(picked_rs) >= 6:
            break

    # 6. 海外技术圈社媒热议 Top 6
    picked_sb = sb[:6]

    def fmt_t7_item(r: dict, mode: str) -> dict:
        if mode == "growth":
            metric = f"周环比 +{r['growth']}%"
            sub = f"本周 {fmt_wan(r['recent'])} / 趋势 #{r['rank']}"
            metric_up = True
        elif mode == "ever":
            metric = f"综合总榜 #{r['br']}"
            sub = f"评分 {r['wis']} / 累计 {fmt_wan(r['total'])}"
            metric_up = True
        else:
            metric = f"本周 {fmt_wan(r['recent'])}"
            sub = f"累计 {fmt_wan(r['total'])} / 趋势 #{r['rank']}"
            metric_up = (r["growth"] is not None and r["growth"] > 0)

        badge = ""
        badge_cls = "badge-top"
        if r["br"]:
            badge = f"综合榜 #{r['br']}"
        elif r["growth"] is not None and r["growth"] > 0:
            badge = f"+{r['growth']}%"
            badge_cls = "badge-up"

        return {
            "slug": r["skill"],
            "badge": badge,
            "badge_cls": badge_cls,
            "desc": r["zh"],
            "cat": r["cat"],
            "source": r["source"],
            "url": r["url"],
            "install": r["install"],
            "metric": metric,
            "metric_up": metric_up,
            "sub": sub,
        }

    topics = []
    if picked_growers:
        topics.append({
            "id": "topic-growers",
            "short_title": "今日增速黑马",
            "kicker": "自动筛选 · 周环比正增长",
            "title": "剥掉马甲后，本周涨得最猛的技能",
            "lead": "自动过滤同源克隆仓库，并限制同一仓库最多入选 2 席，只留下本周环比增长最快的代表性黑马。",
            "callout_title": "看榜提示",
            "callout_text": "周环比大涨通常意味着新功能出圈或社区刚发现的新玩法，适合第一时间尝鲜。",
            "highlight_first": True,
            "items": [fmt_t7_item(r, "growth") for r in picked_growers],
        })

    if picked_ever:
        topics.append({
            "id": "topic-evergreen",
            "short_title": "综合高分常青树",
            "kicker": "交叉比对 best-100 综合榜",
            "title": "既在热榜上、口碑又稳居全网前列的底座技能",
            "lead": "综合榜（wis）结合了安装量、增长动量、社媒声量、更新频率与官方信任度五个维度，是最不容易踩雷的装机清单。",
            "callout_title": "装机建议",
            "callout_text": "如果是刚搭本地 AI 环境，优先从这一组里挑自己用得上的装。",
            "highlight_first": True,
            "items": [fmt_t7_item(r, "ever") for r in picked_ever],
        })

    if picked_media:
        topics.append({
            "id": "topic-media",
            "short_title": "设计审美与音视频",
            "kicker": "设计·音视频热门方向",
            "title": "做视频、画原型与提升页面审美的热门工具",
            "lead": "按本周安装量自动挑选非马甲的设计与音视频技能（同一仓库最多展示 2 席，避免单包刷屏）。",
            "callout_title": "说明",
            "callout_text": "若某个新上榜英文技能暂未出现在词典里，可点击原页链接查看详情，或补充进 zh_dict.json。",
            "highlight_first": False,
            "items": [fmt_t7_item(r, "recent") for r in picked_media],
        })

    if picked_dev:
        topics.append({
            "id": "topic-dev",
            "short_title": "编程与工程工作流",
            "kicker": "编程开发热门方向",
            "title": "写代码、控质量与建站的高人气开发技能",
            "lead": "自动汇总本周最受欢迎的编程与软件工程协作技能，覆盖需求对齐、测试驱动开发、排错与自动建站。",
            "callout_title": "说明",
            "callout_text": "这类技能大多是纯 Prompt/工作流规范，装上即生效，几乎没有额外环境依赖。",
            "highlight_first": False,
            "items": [fmt_t7_item(r, "recent") for r in picked_dev],
        })

    if picked_rs:
        topics.append({
            "id": "topic-cn",
            "short_title": "国内新星务实神器",
            "kicker": "自动同步 rising-stars.csv",
            "title": "上线不满 30 天的新晋高人气工具（自带中文简介）",
            "lead": "主要来自国内腾讯 SkillHub 增量，画风偏办公、教学、专利与自媒体采集等直接解决具体问题的落地工具。",
            "callout_title": "安装说明",
            "callout_text": "SkillHub 国内独有技能暂无统一 CLI 直装命令，在平台内搜索对应英文名即可使用。",
            "highlight_first": True,
            "items": [
                {
                    "slug": r["skill"],
                    "badge": f"上线 {r['age']} 天" if r["age"] is not None else "新晋",
                    "badge_cls": "badge-up",
                    "desc": r["desc"],
                    "cat": r["cat"],
                    "source": r["vendor"] or r["platform"],
                    "url": r["url"],
                    "install": r["install"],
                    "metric": r["count_label"],
                    "metric_up": True,
                    "sub": f"新星榜 #{r['rank']}",
                }
                for r in picked_rs
            ],
        })

    if picked_sb:
        topics.append({
            "id": "topic-buzz",
            "short_title": "海外社媒热议",
            "kicker": "自动同步 social-buzz.csv",
            "title": "这周在 X、Hacker News 与 GitHub 被聊得最多的技能",
            "lead": "相比安装量，社媒声量更能反映海外开发者社区当下真正在讨论和推荐什么。",
            "callout_title": "指标说明",
            "callout_text": "声量分（0–1）综合了近 7 天 X、HN、Bluesky 和 GitHub 的相关性过滤提及次数。",
            "highlight_first": False,
            "items": [
                {
                    "slug": r["skill"],
                    "badge": f"声量 {r['buzz']:.3f}",
                    "badge_cls": "badge-top",
                    "desc": r["desc"],
                    "cat": r["cat"],
                    "source": r["vendor"] or r["platform"],
                    "url": r["url"],
                    "install": r["install"],
                    "metric": f"社媒热议 #{r['rank']}",
                    "metric_up": True,
                    "sub": f"HN {r['hn'] or 0} / Bsky {r['bsky'] or 0} / GH {r['gh'] or 0}",
                }
                for r in picked_sb
            ],
        })

    return topics


def main():
    zh_dict = json.loads((ROOT / "zh_dict.json").read_text(encoding="utf-8"))
    known_clones = set(zh_dict.get("clone_sources", []))

    readme = fetch_text(f"{BASE_RAW}/README.md")
    m_date = re.search(r"Last updated:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*", readme)
    data_date = m_date.group(1) if m_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    t7_raw = fetch_csv("data/latest/rankings/trending-7d.csv")
    b100_raw = fetch_csv("data/latest/rankings/best-100.csv")
    rs_raw = fetch_csv("data/latest/rankings/rising-stars.csv")
    sb_raw = fetch_csv("data/latest/rankings/social-buzz.csv")

    b_map = {}
    for r in b100_raw:
        b_map[r["skill_key"]] = {
            "br": to_int(r.get("rank")),
            "wis": to_float(r.get("wis")),
        }

    # 自动补充检测：若某仓库名含 /superpowers 且与已知马甲技能高度重合，也标为同源马甲
    clone_sources_seen = set()
    t7 = []
    for r in t7_raw:
        src = r.get("source_skillssh") or r.get("vendor") or ""
        is_clone = (src in known_clones) or src.endswith("/superpowers")
        if is_clone:
            clone_sources_seen.add(src)
        bm = b_map.get(r.get("skill_key", ""), {})
        item = {
            "rank": to_int(r.get("rank")) or 0,
            "skill": r.get("skill", ""),
            "vendor": r.get("vendor", ""),
            "source": src,
            "url": r.get("url", ""),
            "install": r.get("install", ""),
            "total": to_int(r.get("installs_skillssh")),
            "recent": to_int(r.get("weekly_recent")),
            "prev": to_int(r.get("weekly_prev")),
            "growth": to_float(r.get("growth_pct")),
            "cat": r.get("category") or "other",
            "br": bm.get("br"),
            "wis": bm.get("wis"),
            "is_clone": is_clone,
            "raw_zh": r.get("description_zh") or "",
        }
        item["zh"] = lookup_zh(item, zh_dict, is_clone)
        item.pop("raw_zh", None)
        t7.append(item)

    rs20 = []
    for r in rs_raw[:20]:
        sh = to_int(r.get("downloads_skillhub_cn"))
        ch = to_int(r.get("downloads_clawhub"))
        ss = to_int(r.get("installs_skillssh"))
        if sh is not None:
            count_label = f"SkillHub {fmt_wan(sh)}"
        elif ss is not None:
            count_label = f"skills.sh {fmt_wan(ss)}"
        elif ch is not None:
            count_label = f"ClawHub {fmt_wan(ch)}"
        else:
            count_label = "新晋上榜"

        raw_zh = (r.get("description_zh") or "").strip()
        raw_en = (r.get("description") or "").strip()
        if has_zh(raw_zh):
            desc = raw_zh[:130]
        else:
            src = r.get("source_skillssh") or r.get("vendor") or ""
            is_clone = (src in known_clones) or src.endswith("/superpowers")
            tmp = {
                "skill": r.get("skill", ""),
                "vendor": r.get("vendor", ""),
                "source": src,
                "cat": r.get("category") or "other",
                "raw_zh": "",
            }
            dict_desc = lookup_zh(tmp, zh_dict, is_clone)
            if not dict_desc.startswith("新上榜技能"):
                desc = dict_desc
            elif raw_zh:
                desc = raw_zh[:130]
            elif raw_en:
                desc = raw_en[:130]
            else:
                desc = "暂无平台简介。"
        rs20.append({
            "rank": to_int(r.get("rank")) or 0,
            "skill": r.get("skill", ""),
            "vendor": r.get("vendor", ""),
            "platform": r.get("platform", ""),
            "age": to_int(r.get("first_seen_days")),
            "cat": r.get("category") or "other",
            "count_label": count_label,
            "desc": desc,
            "url": r.get("url", ""),
            "install": r.get("install", ""),
        })

    sb = []
    for r in sb_raw[:20]:
        src = r.get("source_skillssh") or r.get("vendor") or ""
        is_clone = (src in known_clones) or src.endswith("/superpowers")
        raw_zh = (r.get("description_zh") or "").strip()
        raw_en = (r.get("description") or "").strip()
        tmp = {
            "skill": r.get("skill", ""),
            "vendor": r.get("vendor", ""),
            "source": src,
            "cat": r.get("category") or "other",
            "raw_zh": raw_zh,
        }
        desc = lookup_zh(tmp, zh_dict, is_clone)
        if desc.startswith("新上榜技能") and raw_en:
            desc = raw_en[:130]
        sb.append({
            "rank": to_int(r.get("rank")) or 0,
            "skill": r.get("skill", ""),
            "vendor": r.get("vendor", ""),
            "platform": r.get("platform", ""),
            "hn": to_int(r.get("hn_hits_7d")),
            "bsky": to_int(r.get("bsky_hits_7d")),
            "gh": to_int(r.get("gh_mentions_7d")),
            "buzz": to_float(r.get("buzz_score")) or 0.0,
            "cat": r.get("category") or "other",
            "desc": desc,
            "url": r.get("url", ""),
            "install": r.get("install", ""),
        })

    # 统计当日 100 席实景解剖
    clone_count = sum(1 for r in t7 if r["is_clone"])
    non_clone = [r for r in t7 if not r["is_clone"]]
    media_count = sum(1 for r in non_clone if r["cat"] == "design-media")
    dev_count = sum(1 for r in non_clone if r["cat"] == "dev-programming")
    cloud_count = sum(1 for r in non_clone if r["cat"] == "it-ops-security")
    other_count = len(t7) - clone_count - media_count - dev_count - cloud_count

    bjt = timezone(timedelta(hours=8))
    built_at_bjt = datetime.now(bjt).strftime("%Y-%m-%d %H:%M")

    payload = {
        "meta": {
            "data_date": data_date,
            "built_at_bjt": built_at_bjt,
        },
        "stats": {
            "total": len(t7),
            "clone_count": clone_count,
            "media_count": media_count,
            "dev_count": dev_count,
            "cloud_count": cloud_count,
            "other_count": other_count,
            "clone_sources_seen": sorted(clone_sources_seen),
        },
        "topics": build_topics(t7, rs20, sb),
        "t7": t7,
        "rs20": rs20,
        "sb": sb,
    }

    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    if "/*__DATA_PAYLOAD__*/" not in tpl:
        raise RuntimeError("template.html 中缺少 /*__DATA_PAYLOAD__*/ 占位符")

    out_html = tpl.replace("/*__DATA_PAYLOAD__*/", payload_json, 1)
    out_path = ROOT / "index.html"
    out_path.write_text(out_html, encoding="utf-8")
    print(f"构建完成: {out_path} ({len(out_html.encode('utf-8')):,} bytes) | 榜单日期: {data_date} | 马甲: {clone_count} 席")


if __name__ == "__main__":
    main()
