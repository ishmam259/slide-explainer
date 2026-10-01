import numpy as np

from slidex.books.raptor import choose_k, soft_clusters, split_oversized


def _blobs(n_per: int = 12, centers: int = 3, dim: int = 40) -> np.ndarray:
    rng = np.random.default_rng(0)
    pts = [rng.normal(loc=c * 10.0, scale=0.3, size=(n_per, dim)) for c in range(centers)]
    return np.vstack(pts)


def test_bic_finds_separated_clusters() -> None:
    x = _blobs()
    assert choose_k(x[:, :5], max_k=6) == 3


def test_soft_clusters_cover_every_member() -> None:
    x = _blobs()
    clusters = soft_clusters(x)
    covered = {i for c in clusters for i in c}
    assert covered == set(range(len(x)))
    assert all(isinstance(i, int) for c in clusters for i in c)


def test_small_input_is_one_cluster() -> None:
    assert soft_clusters(np.ones((3, 8))) == [[0, 1, 2]]


def test_oversized_cluster_is_split() -> None:
    x = _blobs()
    members = list(range(len(x)))
    tokens = [400] * len(x)  # 36 × 400 = 14 400 tokens > 3000 limit
    parts = split_oversized(members, tokens, x)
    assert all(sum(tokens[i] for i in p) <= 3000 or len(p) <= 2 for p in parts)
    assert {i for p in parts for i in p} == set(members)
