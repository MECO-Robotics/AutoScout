"""Main-view crop and image-scale compensation; no metric field calibration.

The single full-width crop covers the main field and excludes the scoreboard
and duplicate lower broadcast camera tiles. Bounds describe the actual
integer crop, so coordinates round-trip exactly.
"""
import math


def robot_crops(frame):
    """Return one full-width main-field crop and its normalized bounds."""
    height, width = frame.shape[:2]
    top, bottom = int(height * .17), int(height * .68)
    left, right = 0, width
    return [(frame[top:bottom, left:right],
             (left / width, top / height, right / width, bottom / height))]


def map_crop_boxes(boxes, bounds):
    """Map normalized crop detections into normalized original-frame space."""
    left, top, right, bottom = bounds
    return [[left + max(0., min(1., float(box[0]))) * (right-left),
             top + max(0., min(1., float(box[1]))) * (bottom-top),
             left + max(0., min(1., float(box[2]))) * (right-left),
             top + max(0., min(1., float(box[3]))) * (bottom-top)] for box in boxes]


def box_iou(first, second):
    intersection = max(0., min(first[2], second[2])-max(first[0], second[0])) * max(0., min(first[3], second[3])-max(first[1], second[1]))
    area1 = max(0., first[2]-first[0]) * max(0., first[3]-first[1])
    area2 = max(0., second[2]-second[0]) * max(0., second[3]-second[1])
    return intersection / max(1e-12, area1+area2-intersection)


def merge_detections(boxes, scores, iou=.45):
    """Confidence-ordered NMS removes duplicate overlapping-crop detections."""
    if len(boxes) != len(scores):
        raise ValueError('Each box requires a score')
    selected = []
    for index in sorted(range(len(boxes)), key=lambda index: -scores[index]):
        if all(box_iou(boxes[index], boxes[other]) <= iou for other in selected):
            selected.append(index)
    return [boxes[index] for index in selected], [scores[index] for index in selected]


def perspective_distance(first, second, predicted_center=None):
    """Distance in local robot-width/height units rather than image fractions.

    Distant robots occupy fewer pixels: an identical pixel displacement should
    cost more for those robots. This compensates apparent image scale, not lens
    distortion or full field perspective. Use alongside velocity/appearance.
    """
    center1 = predicted_center if predicted_center is not None else ((first[0]+first[2])/2, (first[1]+first[3])/2)
    center2 = ((second[0]+second[2])/2, (second[1]+second[3])/2)
    width = math.sqrt(max(1e-8, first[2]-first[0]) * max(1e-8, second[2]-second[0]))
    height = math.sqrt(max(1e-8, first[3]-first[1]) * max(1e-8, second[3]-second[1]))
    return math.hypot((center1[0]-center2[0])/width, (center1[1]-center2[1])/height)
