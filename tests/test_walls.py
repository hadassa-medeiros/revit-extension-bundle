"""Testes do nucleo geometrico puro. Rodam sem Revit:
    python -m pytest tests/  (ou)  python tests/test_walls.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.walls import (
    are_parallel,
    perpendicular_distance,
    overlap_along_direction,
    pair_wall_faces,
    wall_axis_and_thickness,
    are_collinear,
    merge_collinear_axes,
)


def approx(a, b, tol=1e-6):
    return abs(a - b) < tol


def approx_point(a, b, tol=1e-6):
    return approx(a[0], b[0], tol) and approx(a[1], b[1], tol)


# ---------------------------------------------------------------------------
# are_parallel / perpendicular_distance / overlap
# ---------------------------------------------------------------------------

def test_horizontal_segments_are_parallel():
    a = ((0, 0), (10, 0))
    b = ((0, 3), (10, 3))
    assert are_parallel(a, b)


def test_vertical_segments_are_parallel():
    a = ((0, 0), (0, 10))
    b = ((3, 0), (3, 10))
    assert are_parallel(a, b)


def test_diagonal_segments_are_parallel():
    a = ((0, 0), (10, 10))
    b = ((1, 0), (11, 10))
    assert are_parallel(a, b)


def test_perpendicular_segments_are_not_parallel():
    a = ((0, 0), (10, 0))
    b = ((0, 0), (0, 10))
    assert not are_parallel(a, b)


def test_perpendicular_distance_is_thickness():
    a = ((0, 0), (10, 0))
    b = ((0, 0.15), (10, 0.15))
    assert approx(perpendicular_distance(a, b), 0.15)


def test_perpendicular_distance_independent_of_direction_drawn():
    # mesma parede, uma face desenhada em sentido oposto -- resultado igual
    a = ((0, 0), (10, 0))
    b = ((10, 0.15), (0, 0.15))
    assert approx(perpendicular_distance(a, b), 0.15)


def test_overlap_positive_when_side_by_side():
    a = ((0, 0), (10, 0))
    b = ((2, 0.15), (8, 0.15))
    assert overlap_along_direction(a, b) > 0


def test_overlap_negative_when_gap_between_them():
    # colineares mas sem overlap: b esta totalmente alem da ponta de a
    a = ((0, 0), (10, 0))
    b = ((20, 0), (30, 0))
    assert overlap_along_direction(a, b) < 0


# ---------------------------------------------------------------------------
# pair_wall_faces
# ---------------------------------------------------------------------------

def test_pairs_two_faces_of_one_wall():
    faces = [
        ((0, 0), (10, 0)),
        ((0, 0.15), (10, 0.15)),
    ]
    pairs = pair_wall_faces(faces, min_thickness=0.02, max_thickness=0.5, min_length=0.5)
    assert len(pairs) == 1
    _, _, thickness = pairs[0]
    assert approx(thickness, 0.15)


def test_does_not_pair_faces_too_far_apart_as_one_wall():
    # 1.5m de distancia = provavelmente duas paredes de um corredor, nao uma parede
    faces = [
        ((0, 0), (10, 0)),
        ((0, 1.5), (10, 1.5)),
    ]
    pairs = pair_wall_faces(faces, min_thickness=0.02, max_thickness=0.5, min_length=0.5)
    assert len(pairs) == 0


def test_diagonal_wall_pairs_correctly():
    faces = [
        ((0, 0), (10, 10)),
        ((0.10, -0.10), (10.10, 9.90)),  # deslocada perpendicularmente ~0.1414
    ]
    pairs = pair_wall_faces(faces, min_thickness=0.05, max_thickness=0.5, min_length=0.5)
    assert len(pairs) == 1


# ---------------------------------------------------------------------------
# wall_axis_and_thickness
# ---------------------------------------------------------------------------

def test_axis_is_exactly_between_faces():
    a = ((0, 0), (10, 0))
    b = ((0, 0.20), (10, 0.20))
    axis, thickness = wall_axis_and_thickness(a, b)
    assert approx(thickness, 0.20)
    assert approx_point(axis[0], (0, 0.10))
    assert approx_point(axis[1], (10, 0.10))


def test_axis_keeps_longer_face_extent():
    short = ((0, 0), (5, 0))
    long = ((0, 0.20), (10, 0.20))
    axis, _ = wall_axis_and_thickness(short, long)
    # eixo deve ter a extensao da face mais longa (10), nao da mais curta (5)
    length = ((axis[1][0] - axis[0][0]) ** 2 + (axis[1][1] - axis[0][1]) ** 2) ** 0.5
    assert approx(length, 10.0)


# ---------------------------------------------------------------------------
# are_collinear
# ---------------------------------------------------------------------------

def test_segments_on_same_line_are_collinear():
    a = ((0, 0), (5, 0))
    b = ((7, 0), (10, 0))
    assert are_collinear(a, b)


def test_parallel_but_offset_segments_are_not_collinear():
    # mesma direcao, mas em retas DIFERENTES (ex.: dois eixos de parede
    # separados por um corredor) -- nao sao a mesma parede
    a = ((0, 0), (5, 0))
    b = ((0, 1.5), (5, 1.5))
    assert not are_collinear(a, b)


# ---------------------------------------------------------------------------
# merge_collinear_axes -- o item central: "colinear same width walls"
# ---------------------------------------------------------------------------

def test_merges_two_axes_that_touch():
    axes = [
        (((0, 0), (5, 0)), 0.15),
        (((5, 0), (10, 0)), 0.15),
    ]
    merged = merge_collinear_axes(axes, max_gap=0.05)
    assert len(merged) == 1
    axis, thickness = merged[0]
    assert approx(thickness, 0.15)
    length = abs(axis[1][0] - axis[0][0])
    assert approx(length, 10.0)


def test_bridges_a_door_sized_gap():
    # dois trechos com um vao de 0.9m (abertura de porta) entre eles
    axes = [
        (((0, 0), (5, 0)), 0.15),
        (((5.9, 0), (10, 0)), 0.15),
    ]
    merged = merge_collinear_axes(axes, max_gap=1.0)
    assert len(merged) == 1


def test_does_not_bridge_a_corridor_sized_gap():
    # vao de 1.84m (corredor) nao deve fechar quando max_gap = 1.0
    axes = [
        (((0, 0), (5, 0)), 0.15),
        (((6.84, 0), (10, 0)), 0.15),
    ]
    merged = merge_collinear_axes(axes, max_gap=1.0)
    assert len(merged) == 2


def test_does_not_merge_different_thickness():
    # mesma reta, mas espessuras diferentes -- paredes distintas, nao fundir
    axes = [
        (((0, 0), (5, 0)), 0.15),
        (((5, 0), (10, 0)), 0.25),
    ]
    merged = merge_collinear_axes(axes, max_gap=1.0)
    assert len(merged) == 2


def test_does_not_merge_parallel_but_not_collinear():
    # dois eixos paralelos mas em retas diferentes (ex.: dois lados de um
    # corredor) -- nunca devem virar uma parede so, mesmo com max_gap grande
    axes = [
        (((0, 0), (5, 0)), 0.15),
        (((0, 1.5), (5, 1.5)), 0.15),
    ]
    merged = merge_collinear_axes(axes, max_gap=10.0)
    assert len(merged) == 2


def test_merges_three_fragments_interrupted_by_two_doors():
    # uma parede com 3 fragmentos (2 portas no meio) -> deve virar 1 so eixo
    axes = [
        (((0, 0), (3, 0)), 0.15),
        (((3.8, 0), (7, 0)), 0.15),
        (((7.9, 0), (12, 0)), 0.15),
    ]
    merged = merge_collinear_axes(axes, max_gap=1.0)
    assert len(merged) == 1
    axis, _ = merged[0]
    length = abs(axis[1][0] - axis[0][0])
    assert approx(length, 12.0)


def test_diagonal_collinear_axes_merge_too():
    axes = [
        (((0, 0), (5, 5)), 0.15),
        (((5, 5), (10, 10)), 0.15),
    ]
    merged = merge_collinear_axes(axes, max_gap=0.1)
    assert len(merged) == 1


def _run_all():
    tests = [(name, fn) for name, fn in globals().items() if name.startswith("test_")]
    passed, failed = 0, 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print("PASS  {}".format(name))
        except AssertionError as e:
            failed += 1
            print("FAIL  {}  -> {}".format(name, e))
    print("\n{} passed, {} failed".format(passed, failed))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
