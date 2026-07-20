"""Fetch public Groww reviews from App Store and Google Play."""

from __future__ import annotations

import csv
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from groww_pulse.phases.phase_1_ingestion.id_utils import normalize_text

logger = logging.getLogger("groww_pulse.ingest")

GROWW_PLAY_PACKAGE = "com.nextbillion.groww"
GROWW_APP_STORE_ID = 1404871703

# Play Store: paginate across storefronts to reach high targets (e.g. 20k).
PLAY_FETCH_COUNTRIES = [
    "in", "us", "gb", "ae", "sg", "au", "ca", "de", "fr", "nl",
    "sa", "qa", "kw", "om", "bh", "my", "id", "ph", "nz", "ie",
    "it", "es", "jp", "kr", "br", "hk", "tw", "th", "vn", "za",
    "mx", "tr", "pl", "se", "no", "dk", "fi", "ch", "at", "be",
]

# App Store public RSS: up to 10 pages x 50 reviews per sort order per country.
APP_STORE_COUNTRIES = PLAY_FETCH_COUNTRIES + [
    "ru", "ua", "cz", "hu", "ro", "pt", "gr", "il", "eg", "ng",
    "ke", "pk", "bd", "lk", "np", "cl", "co", "pe", "ar", "lu",
    "sk", "si", "hr", "bg", "ee", "lv", "lt", "cy", "mt", "is",
]
APP_STORE_SORT_ORDERS = ("mostrecent", "mosthelpful")


@dataclass
class FetchReport:
    store: str
    requested: int
    fetched: int
    written: int
    output_path: Path
    note: str = ""


def _play_review_key(review: dict) -> tuple[str, str]:
    """Match ingest dedupe key: normalized text + calendar date (ADR-009)."""
    at = review.get("at")
    if hasattr(at, "date"):
        date_part = at.date().isoformat()
    else:
        date_part = str(at)[:10]
    text = normalize_text(str(review.get("content", "")))
    return text, date_part


def _play_unique_key(review: dict) -> str:
    review_id = review.get("reviewId")
    if review_id:
        return f"id:{review_id}"
    text, date_part = _play_review_key(review)
    return f"text:{text}|{date_part}"


def _fetch_play_country_reviews(
    *,
    country: str,
    lang: str,
    raw_target: int,
    seen: set[str],
    collected: list[dict],
    sleep_ms: int,
) -> None:
    from google_play_scraper import Sort, reviews, reviews_all

    if raw_target <= 20_000:
        token = None
        while len(collected) < raw_target:
            batch, token = reviews(
                GROWW_PLAY_PACKAGE,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=200,
                continuation_token=token,
            )
            if not batch:
                break

            for review in batch:
                key = _play_unique_key(review)
                text_key = _play_review_key(review)
                if not text_key[0] or key in seen:
                    continue
                seen.add(key)
                collected.append(review)
                if len(collected) >= raw_target:
                    break

            if len(collected) >= raw_target:
                break
            if token is None or getattr(token, "token", None) is None:
                break
            if sleep_ms:
                time.sleep(sleep_ms / 1000)
        return

    batch = reviews_all(
        GROWW_PLAY_PACKAGE,
        lang=lang,
        country=country,
        sort=Sort.NEWEST,
        sleep_milliseconds=sleep_ms,
    )
    for review in batch:
        if len(collected) >= raw_target:
            break
        key = _play_unique_key(review)
        text_key = _play_review_key(review)
        if not text_key[0] or key in seen:
            continue
        seen.add(key)
        collected.append(review)


def fetch_play_store_reviews(
    *,
    count: int = 20_000,
    lang: str = "en",
    country: str = "in",
    countries: list[str] | None = None,
    sleep_ms: int = 200,
) -> list[dict]:
    """Fetch a large raw pool so post-filter caps can reach `count` per store."""
    raw_target = max(count * 10, 100_000) if count >= 10_000 else count
    storefronts = countries or PLAY_FETCH_COUNTRIES
    if country and country not in storefronts:
        storefronts = [country, *storefronts]

    collected: list[dict] = []
    seen: set[str] = set()

    for storefront in storefronts:
        if len(collected) >= raw_target:
            break
        before = len(collected)
        _fetch_play_country_reviews(
            country=storefront,
            lang=lang,
            raw_target=raw_target,
            seen=seen,
            collected=collected,
            sleep_ms=sleep_ms,
        )
        logger.info(
            "Play Store: %s raw reviews collected / %s pool target (+%s from %s)",
            len(collected),
            raw_target,
            len(collected) - before,
            storefront,
        )

    return collected


def _parse_itunes_review_entry(entry: dict) -> dict | None:
    """Parse one iTunes RSS JSON review entry; return None for non-review rows."""
    if "im:rating" not in entry:
        return None

    review_id = entry.get("id", {}).get("label")
    if not review_id:
        return None

    title = entry.get("title", {}).get("label", "")
    content = entry.get("content", {}).get("label", "")
    if not content:
        return None

    rating = int(entry["im:rating"]["label"])
    updated = entry.get("updated", {}).get("label", "")
    review_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    version = entry.get("im:version", {}).get("label")

    return {
        "id": str(review_id),
        "rating": rating,
        "title": title,
        "content": content,
        "date": review_date,
        "version": version,
    }


def _fetch_itunes_reviews_page(
    *,
    country: str,
    app_id: int,
    page: int,
    sortby: str,
) -> list[dict]:
    url = (
        f"https://itunes.apple.com/{country}/rss/customerreviews/"
        f"page={page}/id={app_id}/sortby={sortby}/json"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "groww-pulse-fetch/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    entries = payload.get("feed", {}).get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]

    parsed: list[dict] = []
    for entry in entries:
        review = _parse_itunes_review_entry(entry)
        if review:
            review["country"] = country
            parsed.append(review)
    return parsed


def _load_app_store_export_csv(path: Path) -> list[dict]:
    """Load reviews from an official App Store Connect CSV export."""
    loaded: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            review_text = (
                row.get("Review")
                or row.get("review")
                or row.get("Body")
                or row.get("body")
                or ""
            ).strip()
            if not review_text:
                continue

            rating_raw = row.get("Rating") or row.get("rating") or row.get("Star Rating") or ""
            title = (row.get("Review Title") or row.get("Title") or row.get("title") or "").strip()
            date_raw = row.get("Date") or row.get("date") or row.get("Created Date") or ""
            version = row.get("App Version") or row.get("app_version") or row.get("Version") or ""
            territory = row.get("Country") or row.get("Territory") or row.get("country") or "in"

            try:
                rating = int(float(str(rating_raw).strip()))
            except ValueError:
                continue

            try:
                if "T" in date_raw:
                    review_date = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                else:
                    review_date = datetime.strptime(date_raw.strip(), "%Y-%m-%d")
            except ValueError:
                review_date = datetime.now(tz=timezone.utc)

            stable_id = f"export:{normalize_text(review_text)}:{review_date.date().isoformat()}:{rating}"
            loaded.append(
                {
                    "id": stable_id,
                    "rating": rating,
                    "title": title,
                    "content": review_text,
                    "date": review_date,
                    "version": version,
                    "country": str(territory).lower()[:2],
                }
            )
    return loaded


def fetch_app_store_reviews(
    *,
    target: int = 20_000,
    export_csv: Path | None = None,
) -> list[dict]:
    """Aggregate unique App Store reviews from export CSV and/or public RSS."""
    seen_ids: set[str] = set()
    collected: list[dict] = []

    if export_csv is not None and export_csv.is_file():
        export_rows = _load_app_store_export_csv(export_csv)
        logger.info("App Store export CSV: loaded %s rows from %s", len(export_rows), export_csv)
        for review in export_rows:
            review_id = review["id"]
            if review_id in seen_ids:
                continue
            seen_ids.add(review_id)
            collected.append(review)
            if len(collected) >= target:
                return collected[:target]

    for country in APP_STORE_COUNTRIES:
        if len(collected) >= target:
            break

        for sortby in APP_STORE_SORT_ORDERS:
            for page in range(1, 11):
                if len(collected) >= target:
                    break
                try:
                    page_reviews = _fetch_itunes_reviews_page(
                        country=country,
                        app_id=GROWW_APP_STORE_ID,
                        page=page,
                        sortby=sortby,
                    )
                except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
                    logger.debug(
                        "App Store skip %s page=%s sort=%s: %s",
                        country,
                        page,
                        sortby,
                        exc,
                    )
                    break

                if not page_reviews:
                    break

                for review in page_reviews:
                    review_id = review["id"]
                    if review_id in seen_ids:
                        continue
                    seen_ids.add(review_id)
                    collected.append(review)
                    if len(collected) >= target:
                        break

                time.sleep(0.15)

        logger.info(
            "App Store: %s unique reviews after country %s",
            len(collected),
            country,
        )

    return collected[:target]


def write_play_store_csv(reviews: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "App Version Name",
                "Star Rating",
                "Review Title",
                "Review Text",
                "Review Submit Date and Time",
                "Device Language",
            ],
        )
        writer.writeheader()
        for review in reviews:
            at = review.get("at")
            if isinstance(at, datetime):
                if at.tzinfo is None:
                    at = at.replace(tzinfo=timezone.utc)
                date_str = at.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                date_str = str(at)
            writer.writerow(
                {
                    "App Version Name": review.get("reviewCreatedVersion") or "",
                    "Star Rating": review.get("score", ""),
                    "Review Title": "",
                    "Review Text": review.get("content", ""),
                    "Review Submit Date and Time": date_str,
                    "Device Language": "en",
                }
            )


def write_app_store_csv(reviews: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["App Version", "Rating", "Title", "Review", "Date", "Territory"],
        )
        writer.writeheader()
        for review in reviews:
            review_date = review["date"]
            if isinstance(review_date, datetime):
                date_str = review_date.date().isoformat()
            else:
                date_str = str(review_date)
            writer.writerow(
                {
                    "App Version": review.get("version") or "",
                    "Rating": review.get("rating", ""),
                    "Title": review.get("title", ""),
                    "Review": review.get("content", ""),
                    "Date": date_str,
                    "Territory": review.get("country", "in").upper(),
                }
            )


def fetch_and_save(
    *,
    output_dir: Path,
    count_per_store: int = 20_000,
    play_lang: str = "en",
    play_country: str = "in",
    app_store_export_csv: Path | None = None,
    stores: Literal["both", "play", "app"] = "both",
) -> tuple[FetchReport | None, FetchReport | None]:
    output_dir.mkdir(parents=True, exist_ok=True)

    play_path = output_dir / "play_store_reviews.csv"
    app_path = output_dir / "app_store_reviews.csv"

    play_report: FetchReport | None = None
    app_report: FetchReport | None = None

    if stores in ("both", "play"):
        logger.info(
            "Fetching up to %s Play Store reviews for %s",
            count_per_store,
            GROWW_PLAY_PACKAGE,
        )
        play_reviews = fetch_play_store_reviews(
            count=count_per_store,
            lang=play_lang,
            country=play_country,
        )
        write_play_store_csv(play_reviews, play_path)
        play_report = FetchReport(
            store="play_store",
            requested=count_per_store,
            fetched=len(play_reviews),
            written=len(play_reviews),
            output_path=play_path,
            note=(
                f"Fetched {len(play_reviews)} raw written-text reviews across "
                f"{len(PLAY_FETCH_COUNTRIES)} storefronts; ingest caps at "
                f"{count_per_store} per store after normalization filters."
            ),
        )

    if stores in ("both", "app"):
        logger.info(
            "Fetching up to %s App Store reviews for app id %s",
            count_per_store,
            GROWW_APP_STORE_ID,
        )
        app_reviews = fetch_app_store_reviews(
            target=count_per_store,
            export_csv=app_store_export_csv,
        )
        write_app_store_csv(app_reviews, app_path)

        sources = []
        if app_store_export_csv and app_store_export_csv.is_file():
            sources.append(f"App Store Connect export ({app_store_export_csv.name})")
        sources.append(
            f"public RSS across {len(APP_STORE_COUNTRIES)} countries x {len(APP_STORE_SORT_ORDERS)} sort orders"
        )
        app_note = f"Fetched {len(app_reviews)} unique reviews via {' + '.join(sources)}."
        if len(app_reviews) < count_per_store:
            app_note += (
                " Public APIs cannot reach 20k App Store reviews without an official "
                "App Store Connect CSV export (set APP_STORE_EXPORT_CSV)."
            )

        app_report = FetchReport(
            store="app_store",
            requested=count_per_store,
            fetched=len(app_reviews),
            written=len(app_reviews),
            output_path=app_path,
            note=app_note,
        )

    return play_report, app_report
