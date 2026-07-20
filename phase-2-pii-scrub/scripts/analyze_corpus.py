#!/usr/bin/env python3
"""Analyze Phase 2 scrubbed corpus for Phase 3 strategy planning."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

THEME_KEYWORDS = {
    "kyc_onboarding": r"\b(kyc|pan|aadhaar|aadhar|verification|onboard|signup|sign up|register|account open)\b",
    "payments_upi": r"\b(upi|payment|pay|transaction|transfer|failed|fail|stuck|pending|refund)\b",
    "withdrawal": r"\b(withdraw|withdrawal|payout|cash out|redeem)\b",
    "login_app_crash": r"\b(login|log in|crash|crashing|freeze|hang|not open|not working|bug|glitch|error|technical)\b",
    "customer_support": r"\b(support|customer care|call|response|reply|ticket|help|service)\b",
    "trading_options": r"\b(option|f&o|fno|trade|trading|order|position|margin|intraday|stock|mutual fund|sip|ipo)\b",
    "statements_tax": r"\b(statement|tax|capital gain|pnl|p&l|report|ledger|portfolio)\b",
    "charges_fees": r"\b(charge|fee|brokerage|deduct|commission|hidden)\b",
}

STOP = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is",
    "it", "this", "that", "with", "my", "i", "me", "app", "groww", "very", "good", "bad",
    "not", "no", "all", "be", "has", "have", "was", "were", "are", "you", "your", "from",
    "can", "cant", "will", "just", "also", "so", "get", "use", "using", "but", "its",
}


def review_text(review: dict) -> str:
    return f"{review.get('title', '')} {review['text']}".strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text.lower()))


def count_theme(review_list: list[dict], pattern: str) -> int:
    rx = re.compile(pattern, re.I)
    return sum(1 for r in review_list if rx.search(review_text(r)))


def main() -> None:
    path = Path(__file__).resolve().parent.parent / "data" / "output" / "scrubbed_reviews.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    reviews = data["reviews"]

    ratings = Counter(r["rating"] for r in reviews)
    sources = Counter(r["source"] for r in reviews)
    word_counts = [word_count(review_text(r)) for r in reviews]
    text_lens = [len(r["text"]) for r in reviews]
    dates = [r["date"] for r in reviews]

    low = [r for r in reviews if r["rating"] <= 2]
    high = [r for r in reviews if r["rating"] >= 4]

    print("=== CORPUS OVERVIEW ===")
    print(f"Total reviews: {len(reviews)}")
    print(f"Sources: {dict(sources)}")
    print(f"Rating distribution: {dict(sorted(ratings.items()))}")
    print(f"Avg rating: {sum(r['rating'] for r in reviews) / len(reviews):.2f}")
    print(f"Low (1-2): {len(low)} ({100 * len(low) / len(reviews):.1f}%)")
    print(f"High (4-5): {len(high)} ({100 * len(high) / len(reviews):.1f}%)")
    print(f"Date range: {min(dates)} to {max(dates)}")
    print(f"Word count: min={min(word_counts)} max={max(word_counts)} avg={sum(word_counts) / len(word_counts):.1f}")
    print(f"Text chars: min={min(text_lens)} max={max(text_lens)} avg={sum(text_lens) / len(text_lens):.0f}")

    print("\n=== THEME KEYWORD HITS (all reviews) ===")
    theme_all = {}
    for name, pat in THEME_KEYWORDS.items():
        c = count_theme(reviews, pat)
        theme_all[name] = c
        print(f"  {name}: {c} ({100 * c / len(reviews):.1f}%)")

    print(f"\n=== LOW-RATED (1-2 stars): {len(low)} reviews ===")
    theme_low = {}
    for name, pat in THEME_KEYWORDS.items():
        c = count_theme(low, pat)
        theme_low[name] = c
        print(f"  {name}: {c} ({100 * c / len(low):.1f}%)")

    words = Counter()
    for r in low:
        for w in re.findall(r"\b[a-z]{3,}\b", review_text(r).lower()):
            if w not in STOP:
                words[w] += 1
    print("\nTop 25 words in 1-2 star reviews:")
    for w, c in words.most_common(25):
        print(f"  {w}: {c}")

    monthly: dict[str, int] = defaultdict(int)
    for r in reviews:
        monthly[r["date"][:7]] += 1
    print("\n=== MONTHLY VOLUME (recent 8) ===")
    for m in sorted(monthly.keys())[-8:]:
        print(f"  {m}: {monthly[m]}")

    avg_w = sum(word_counts) / len(word_counts)
    print("\n=== LLM INPUT SIZING (Groq) ===")
    print(f"Avg words/review: {avg_w:.1f}")
    print(f"Naive (3 themes x 20 reps): ~{3 * 20 * avg_w:.0f} words")
    print(f"Recommended (3 themes x 10 reps): ~{3 * 10 * avg_w:.0f} words")
    print(f"Full corpus tokens estimate (~1.3 tok/word): ~{len(reviews) * avg_w * 1.3:.0f} tokens (too large for single LLM call)")

    print("\n=== RECOMMENDED PHASE 3 STRATEGY ===")
    top_themes = sorted(theme_low.items(), key=lambda x: x[1], reverse=True)[:5]
    print("Top pain themes by low-rated keyword hits:")
    for name, c in top_themes:
        print(f"  - {name.replace('_', ' ')}: {c} hits")


if __name__ == "__main__":
    main()
