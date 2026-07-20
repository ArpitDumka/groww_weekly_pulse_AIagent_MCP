"""In-memory embedding clustering (ADR-007 / ADR-008)."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import KMeans

from groww_pulse.models import Review, ThemeCluster, ThemedCorpus

logger = logging.getLogger("groww_pulse.summarize")


def _review_body(review: Review) -> str:
    title = review.title.strip()
    if title:
        return f"{title}. {review.text}"
    return review.text


def _severity(reviews: list[Review]) -> float:
    if not reviews:
        return 0.0
    low = sum(1 for review in reviews if review.rating <= 2)
    return low / len(reviews)


def cluster_reviews(
    reviews: list[Review],
    *,
    embedding_model: str,
    cluster_k: int = 5,
    top_n: int = 3,
    reps_per_theme: int = 6,
    random_state: int = 42,
) -> ThemedCorpus:
    if len(reviews) < cluster_k:
        cluster_k = max(2, len(reviews))

    texts = [_review_body(review) for review in reviews]
    logger.info("Embedding %s reviews with %s", len(reviews), embedding_model)

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(embedding_model)
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=256)
    embeddings = np.asarray(embeddings)

    kmeans = KMeans(n_clusters=cluster_k, random_state=random_state, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    centroids = kmeans.cluster_centers_

    grouped: dict[int, list[tuple[int, Review]]] = defaultdict(list)
    for index, (review, label) in enumerate(zip(reviews, labels, strict=True)):
        grouped[int(label)].append((index, review))

    themes: list[ThemeCluster] = []
    for cluster_id, items in grouped.items():
        cluster_reviews = [review for _, review in items]
        indices = np.array([idx for idx, _ in items])
        cluster_embeddings = embeddings[indices]
        centroid = centroids[cluster_id]
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        order = np.argsort(distances)

        rep_ids: list[str] = []
        for pos in order[: reps_per_theme * 2]:
            rep_ids.append(cluster_reviews[int(pos)].id)
            if len(rep_ids) >= reps_per_theme:
                break

        severity = _severity(cluster_reviews)
        avg_rating = sum(review.rating for review in cluster_reviews) / len(cluster_reviews)
        rank_score = len(cluster_reviews) * (1.0 + severity)
        themes.append(
            ThemeCluster(
                cluster_id=cluster_id,
                size=len(cluster_reviews),
                avg_rating=round(avg_rating, 2),
                severity=round(severity, 3),
                rank_score=round(rank_score, 2),
                representatives=rep_ids,
            )
        )

    themes.sort(key=lambda theme: theme.rank_score, reverse=True)
    ranked: list[ThemeCluster] = []
    for rank, theme in enumerate(themes, start=1):
        ranked.append(theme.model_copy(update={"rank": rank}))
    themes = ranked

    top_theme_ids = [theme.cluster_id for theme in themes[:top_n]]
    logger.info(
        "Clustering complete: k=%s themes=%s top=%s",
        cluster_k,
        len(themes),
        top_theme_ids,
    )

    return ThemedCorpus(
        themes=themes,
        total_reviews=len(reviews),
        cluster_k=cluster_k,
        embedding_model=embedding_model,
        top_theme_ids=top_theme_ids,
    )


def reviews_by_id(reviews: list[Review]) -> dict[str, Review]:
    return {review.id: review for review in reviews}


def source_split(reviews: list[Review]) -> dict[str, int]:
    counts = Counter(review.source.value for review in reviews)
    return dict(counts)
