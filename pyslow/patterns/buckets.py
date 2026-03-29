"""Bucket mapping used by the classic evaluator."""

from __future__ import annotations

from pyslow.patterns.shapes import ShapeLabel

DOUBLE_SHAPE: tuple[tuple[int, ...], ...] = (
    (1,),
    (2, 3),
    (4, 5, 6),
    (7, 8, 9, 10),
    (11, 12, 13, 14, 15),
    (16, 17, 18, 19, 20, 21),
    (22, 23, 24, 25, 26, 27, 28),
    (29, 30, 31, 32, 33, 34, 35, 36),
    (37, 38, 39, 40, 41, 42, 43, 44, 45),
    (46, 47, 48, 49, 50, 51, 52, 53, 54, 55),
    (56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66),
    (67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78),
    (79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91),
)


def bucket_for_lines(first: int, second: int) -> int:
    """Map the top two normalized line strengths to a bucket id."""
    if first < second:
        first, second = second, first
    if not (0 <= second <= first < ShapeLabel.L6):
        raise ValueError(f"invalid line strengths: {(first, second)}")
    return DOUBLE_SHAPE[first][second]
