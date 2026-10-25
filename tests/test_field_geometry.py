import numpy as np
import pytest

from autoscout.field_geometry import robot_crops, map_crop_boxes, merge_detections, perspective_distance


def test_crop_coordinates_round_trip_odd_sized_frame():
    frame = np.zeros((1081, 1921, 3), dtype=np.uint8)
    crops = robot_crops(frame)
    assert len(crops) == 1
    assert crops[0][1][0] == 0 and crops[0][1][2] == 1
    for image, bounds in crops:
        assert map_crop_boxes([[0, 0, 1, 1]], bounds)[0] == list(bounds)
        assert image.shape[1] == pytest.approx((bounds[2]-bounds[0])*1921)
        assert image.shape[0] == pytest.approx((bounds[3]-bounds[1])*1081)
        assert bounds[1] >= .169 and bounds[3] <= .68


def test_midfield_duplicate_suppressed_but_adjacent_robots_remain():
    boxes = [[.48, .3, .52, .4], [.481, .301, .521, .401], [.52, .3, .56, .4]]
    kept, scores = merge_detections(boxes, [.8, .9, .7])
    assert kept == [boxes[1], boxes[2]]
    assert scores == [.9, .7]
    assert merge_detections([], []) == ([], [])


def test_same_relative_motion_equal_cost_across_perspective_scales():
    near = [0, 0, .2, .1]
    far = [0, 0, .1, .05]
    assert perspective_distance(near, [.1, 0, .3, .1]) == pytest.approx(perspective_distance(far, [.05, 0, .15, .05]))
    assert perspective_distance(far, [.05, 0, .15, .05]) > perspective_distance(near, [.05, 0, .25, .1])


def test_predicted_center_accounts_for_velocity():
    assert perspective_distance([0, 0, .1, .1], [.1, 0, .2, .1], predicted_center=(.15, .05)) == pytest.approx(0)
