"""Quick statistics and a lightweight (lexicon-based) sentiment score. No heavy dependencies."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List

from .models import Message

_WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)

STOPWORDS = set("""
the and for that this with you your are was were have has had not but from they their them will would there what
when which who how can all any out our about into more some just than then also its it's been being over only other
https http www com org net telegram channel join like very much here now one two new get got via amp
از به با که این را در برای تا آن یک هم و یا اما اگر هر می را ها های بر شد شده است هست بود کرد کند کنید
خواهد باید نیز چه چرا کرده روی بین پس دیگر همه ما شما آنها او من تو ای بعد قبل خود داریم دارد
""".split())

POSITIVE = set("""
good great excellent amazing awesome love best win winning profit gain gains bullish pump moon up rise rising
growth success successful happy strong buy launch launched new record breakout surge rally positive nice congrats
خوب عالی عالیه بهترین سود صعود صعودی رشد موفق موفقیت خوشحال قوی خرید پامپ رکورد افزایش مثبت تبریک فوق‌العاده
""".split())

NEGATIVE = set("""
bad worst terrible awful loss losses lose losing bearish dump crash down fall falling drop scam hack hacked risk
fear sell weak fail failed failure problem warning danger negative sad liquidated rekt fraud
بد بدترین ضرر نزول نزولی ریزش سقوط کلاهبرداری هک ریسک ترس فروش ضعیف شکست مشکل هشدار خطر منفی ناراحت دامپ
""".split())


def sentiment(text: str) -> float:
    """Score in [-1, 1] from a small bilingual (English / Persian) word list. Rough, but dependency-free."""
    words = [w.lower() for w in _WORD_RE.findall(text)]
    pos = sum(w in POSITIVE for w in words)
    neg = sum(w in NEGATIVE for w in words)
    return 0.0 if pos + neg == 0 else round((pos - neg) / (pos + neg), 3)


def top_words(messages: Iterable[Message], n: int = 20) -> List[tuple]:
    counter: Counter = Counter()
    for m in messages:
        counter.update(w.lower() for w in _WORD_RE.findall(re.sub(r"https?://\S+", "", m.text))
                       if w.lower() not in STOPWORDS)
    return counter.most_common(n)


def summarize(messages: Iterable[Message], top: int = 5) -> Dict[str, Any]:
    """Everything you usually want to know about a batch of messages, as a JSON-friendly dict."""
    msgs = list(messages)
    if not msgs:
        return {"count": 0}
    dated = [m for m in msgs if m.date]
    viewed = [m for m in msgs if m.views is not None]
    per_day: Counter = Counter(m.date.date().isoformat() for m in dated)
    per_hour: Counter = Counter(m.date.hour for m in dated)
    per_weekday: Counter = Counter(m.date.strftime("%A") for m in dated)
    media: Counter = Counter(t for m in msgs for t in m.media_types)
    hashtags: Counter = Counter(h.lower() for m in msgs for h in m.hashtags)
    mentions: Counter = Counter(x.lower() for m in msgs for x in m.mentions)
    reactions: Counter = Counter()
    for m in msgs:
        reactions.update(m.reactions)
    scores = [sentiment(m.text) for m in msgs if m.text]
    total_views = sum(m.views for m in viewed)
    days = max(len(per_day), 1)

    def brief(m: Message) -> Dict[str, Any]:
        return {"id": m.id, "url": m.url, "views": m.views, "date": m.date.isoformat() if m.date else None,
                "text": (m.text[:140] + "…") if len(m.text) > 140 else m.text}

    return {
        "count": len(msgs),
        "channels": sorted({m.channel for m in msgs}),
        "first_date": min(m.date for m in dated).isoformat() if dated else None,
        "last_date": max(m.date for m in dated).isoformat() if dated else None,
        "posts_per_day": round(len(dated) / days, 2),
        "total_views": total_views,
        "avg_views": round(total_views / len(viewed)) if viewed else None,
        "with_media": sum(1 for m in msgs if m.media),
        "forwarded": sum(1 for m in msgs if m.forwarded_from),
        "media_types": dict(media.most_common()),
        "top_posts": [brief(m) for m in sorted(viewed, key=lambda m: m.views or 0, reverse=True)[:top]],
        "top_hashtags": hashtags.most_common(top * 2),
        "top_mentions": mentions.most_common(top * 2),
        "top_words": top_words(msgs, top * 4),
        "reactions": dict(reactions.most_common(10)),
        "sentiment": {
            "average": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "positive": sum(s > 0 for s in scores),
            "neutral": sum(s == 0 for s in scores),
            "negative": sum(s < 0 for s in scores),
        },
        "posts_by_day": dict(sorted(per_day.items())),
        "posts_by_hour": {h: per_hour.get(h, 0) for h in range(24)},
        "posts_by_weekday": dict(per_weekday.most_common()),
    }


def format_summary(stats: Dict[str, Any]) -> str:
    """Human-readable text version of :func:`summarize`."""
    if not stats.get("count"):
        return "No messages."

    def bar(value: int, maximum: int, width: int = 30) -> str:
        return "█" * max(1 if value else 0, round(width * value / maximum)) if maximum else ""

    lines = [
        f"📊 {stats['count']} messages from {', '.join(stats['channels'])}",
        f"   {stats['first_date'] or '?'}  →  {stats['last_date'] or '?'}  ({stats['posts_per_day']} posts/day)",
        f"👁  total views {stats['total_views']:,} · average {stats['avg_views'] or 0:,}",
        f"📎 with media {stats['with_media']} {stats['media_types']} · forwarded {stats['forwarded']}",
        f"🙂 sentiment avg {stats['sentiment']['average']:+} "
        f"(+{stats['sentiment']['positive']} / ={stats['sentiment']['neutral']} / -{stats['sentiment']['negative']})",
        "",
        "🔥 Top posts:",
    ]
    for p in stats["top_posts"]:
        lines.append(f"   {p['views'] or 0:>9,}  {p['url']}  {p['text'][:60]!r}")
    if stats["top_hashtags"]:
        lines += ["", "#️⃣  " + "  ".join(f"#{h}({c})" for h, c in stats["top_hashtags"])]
    if stats["top_words"]:
        lines += ["🔤 " + "  ".join(f"{w}({c})" for w, c in stats["top_words"][:15])]
    hours = stats["posts_by_hour"]
    peak = max(hours.values()) if hours else 0
    if peak:
        lines += ["", "🕒 Posts by hour (UTC):"]
        lines += [f"   {h:02d} {bar(c, peak)} {c}" for h, c in hours.items() if c]
    return "\n".join(lines)
