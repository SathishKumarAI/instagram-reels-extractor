"""easyocr returns a frame's detections in its own detection order, not reading
order, and `add_ocr` used to append them exactly as they arrived. The prompt then
offered the block to the model as "unordered" — which the 2026-08-20 ablation
measured as costing 0.5 facts/reel and kept the whole stage switched off.

These tests cover the ordering only. The end-to-end stage is not covered here:
easyocr cannot import on the Windows box (Application Control blocks scipy's
_flapack DLL), which is exactly why the sort lives in a pure function.
"""

from reels_scrap.extract.ocr import order_detections


def _det(text, x0, y0, x1, y1, conf=0.9):
    """One easyocr detail=1 result: (four [x, y] corners, text, confidence)."""
    return ([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], text, conf)


def _texts(dets):
    return [d[1] for d in dets]


def test_detections_come_back_top_to_bottom_then_left_to_right():
    # Two visual lines, fed in deliberately scrambled order. WORLD sits 2px lower
    # than HELLO — real OCR boxes are never flush, and that jitter must not be
    # read as a new line.
    scrambled = [
        _det("WORLD", 100, 12, 150, 42),
        _det("LINE", 80, 100, 140, 130),
        _det("HELLO", 0, 10, 50, 40),
        _det("SECOND", 0, 100, 60, 130),
    ]
    assert _texts(scrambled) != ["HELLO", "WORLD", "SECOND", "LINE"], (
        "fixture must start out of order, or this test proves nothing"
    )

    assert _texts(order_detections(scrambled)) == ["HELLO", "WORLD", "SECOND", "LINE"]


def test_a_few_pixels_of_jitter_does_not_split_one_line():
    # Same row, each box nudged a little. All four belong to one line, so they
    # must come back purely left-to-right regardless of their y wobble.
    row = [
        _det("D", 300, 14, 340, 44),
        _det("B", 100, 8, 140, 38),
        _det("A", 0, 11, 40, 41),
        _det("C", 200, 6, 240, 36),
    ]
    assert _texts(order_detections(row)) == ["A", "B", "C", "D"]


def test_genuinely_separate_lines_stay_separate():
    # A lower line whose left-most box starts far left must NOT overtake the line
    # above it: y decides the line, x only decides position within one.
    dets = [
        _det("BOTTOM", 0, 200, 90, 230),
        _det("TOP", 500, 10, 590, 40),
    ]
    assert _texts(order_detections(dets)) == ["TOP", "BOTTOM"]


def test_it_is_pure():
    dets = [_det("B", 100, 100, 140, 130), _det("A", 0, 10, 40, 40)]
    before = list(dets)
    out = order_detections(dets)
    assert dets == before, "input list was mutated"
    assert out is not dets

    assert order_detections([]) == []
