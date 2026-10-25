"""Conservative, offline match-boundary inference from the existing broadcast OCR.

No cutoff is safe until all readings, including the tail, have been inspected.
This deliberately supports only the current central-clock broadcast layout;
unsupported layouts and clips beginning too late retain full inference coverage.
"""
from __future__ import annotations

import math
import re
import time
from collections.abc import Callable, Iterable


def parse_clock(reading: dict) -> int | None:
    """Return seconds for one unambiguous, high-confidence main clock."""
    clocks = set()
    for item in reading.get('texts', []):
        if (item.get('confidence', 0) < .9 or
                not .47 <= item.get('x', -1) <= .53 or
                not .05 <= item.get('y', -1) <= .12):
            continue
        match = re.fullmatch(r'([0-2]):([0-5][0-9])', str(item.get('text', '')).replace(' ', ''))
        if match:
            clocks.add(int(match[1]) * 60 + int(match[2]))
    return next(iter(clocks)) if len(clocks) == 1 else None


def _infer_start(ordered: list[tuple[float, int]], buffer_seconds: float) -> dict:
    """Require initial 20s plateau and three coherent downward clock ticks."""
    result = {'confirmed_start': None, 'inference_start': 0.0,
              'start_buffer_seconds': buffer_seconds,
              'start_reason': 'insufficient_initial_countdown', 'start_evidence': []}
    if not ordered or ordered[0][1] != 20:
        return result
    first_drop = next((i for i, (_, value) in enumerate(ordered) if value != 20), None)
    if first_drop is None:
        return result
    plateau = ordered[:first_drop]
    if plateau[-1][0] - plateau[0][0] < 2:
        return result
    if any(b[0] - a[0] > 2 for a, b in zip(plateau, plateau[1:])):
        return result
    previous = plateau[-1]
    ticks = []
    for sample in ordered[first_drop:]:
        t, seconds = sample
        dt, drop = t - previous[0], previous[1] - seconds
        if dt > 2 or drop < 0 or drop > dt + 1 or seconds <= 0:
            return result
        if drop > 0:
            ticks.append(sample)
        previous = sample
        if len(ticks) >= 3:
            break
    if len(ticks) < 3 or ticks[0][1] != 19:
        return result
    # Clock quantization makes onset approximate; retain last plateau sample
    # plus a prebuffer to preserve early play and robot identification.
    onset = plateau[-1][0]
    if abs((ticks[-1][0] - onset) - (20 - ticks[-1][1])) > 1.5:
        return result
    if any(b[1] == 20 and a[1] < 20
           for a, b in zip(ordered[first_drop:], ordered[first_drop + 1:])):
        result['start_reason'] = 'repeated_autonomous_clock_ambiguous'
        return result
    result.update(confirmed_start=onset, inference_start=max(0.0, onset - buffer_seconds),
                  start_reason='initial_plateau_and_countdown_confirmed',
                  start_evidence=[{'timestamp': t, 'seconds': value}
                                  for t, value in [plateau[0], plateau[-1], *ticks]])
    return result


def infer_match_window(readings: Iterable[dict], duration: float,
                       buffer_seconds: float = 5.0, *, start_buffer_seconds: float = 3.0) -> dict:
    """Inspect the entire OCR series before selecting GPU inference boundaries.

    An initial 20-second plateau followed by coherent ticks establishes a start;
    retain a pre-start buffer. Missing or ambiguous start evidence retains frame 0.
    A >=60-second clock establishes a non-autonomous countdown for this layout.
    Require >=30 seconds of coherent observed countdown, a reading <=3 seconds,
    and three zeros over >=1 second. Missing OCR never establishes an end.
    Any later positive clock invalidates a candidate (including possible replay).
    This errs toward full processing rather than guessing whether a reset is live.
    """
    if not math.isfinite(duration) or duration < 0:
        raise ValueError('duration must be finite and nonnegative')
    if not math.isfinite(buffer_seconds) or buffer_seconds < 0:
        raise ValueError('buffer_seconds must be finite and nonnegative')
    if not math.isfinite(start_buffer_seconds) or start_buffer_seconds < 0:
        raise ValueError('start_buffer_seconds must be finite and nonnegative')
    result = {**_infer_start([], start_buffer_seconds), 'confirmed_end': None, 'inference_end': duration, 'full_clip': True,
              'confidence': 'uncertain', 'reason': 'insufficient_final_countdown',
              'buffer_seconds': buffer_seconds, 'evidence': []}
    samples = []
    for reading in readings:
        t = reading.get('timestamp')
        if not isinstance(t, (int, float)) or not math.isfinite(t) or not 0 <= t <= duration:
            continue
        seconds = parse_clock(reading)
        if seconds is not None:
            samples.append((float(t), seconds))
    # Duplicate timestamps cannot supply independent confirmation.
    ordered = sorted(set(samples))
    if any(a[0] == b[0] and a[1] != b[1] for a, b in zip(ordered, ordered[1:])):
        result['reason'] = 'conflicting_clock_readings'
        return result
    result.update(_infer_start(ordered, start_buffer_seconds))
    result['full_clip'] = result['inference_start'] == 0
    anchor = previous = None
    zeros = []
    candidate = None
    for t, seconds in ordered:
        if candidate is not None:
            if seconds > 0:
                result['reason'] = 'later_clock_contradicts_end'
                result['evidence'] = [{'timestamp': candidate, 'seconds': 0},
                                      {'timestamp': t, 'seconds': seconds}]
                return result
            continue
        if previous is not None:
            dt = t - previous[0]
            drop = previous[1] - seconds
            # Long unseen intervals, upward resets, and impossible OCR jumps
            # discard phase evidence. Two seconds tolerates integer clock/OCR jitter.
            if dt > 5 or drop < 0 or drop > dt + 2:
                anchor = None
                zeros = []
        if anchor is None and seconds >= 60:
            anchor = (t, seconds)
        if seconds == 0 and anchor is not None and previous is not None:
            observed = t - anchor[0]
            coherent = abs(observed - anchor[1]) <= 4
            if previous[1] <= 3 and observed >= 30 and coherent:
                zeros.append(t)
                if len(zeros) >= 3 and zeros[-1] - zeros[0] >= 1:
                    candidate = zeros[0]
            else:
                zeros = []
        elif seconds > 0:
            zeros = []
        previous = (t, seconds)
    if candidate is not None:
        end = min(duration, candidate + buffer_seconds)
        result.update(confirmed_end=candidate, inference_end=end,
                      full_clip=end >= duration and result['inference_start'] == 0, confidence='countdown_confirmed',
                      reason='confirmed_final_zero_with_buffer',
                      evidence=[{'timestamp': anchor[0], 'seconds': anchor[1]},
                                {'timestamp': candidate, 'seconds': 0},
                                {'timestamp': zeros[-1], 'seconds': 0}])
    return result


def scan_match_window(video_path, ocr, scoreboard_reader: Callable, *,
                      sample_hz: float = 2.0, buffer_seconds: float = 5.0,
                      start_buffer_seconds: float = 3.0,
                      progress: Callable | None = None, deadline: float | None = None,
                      limit_seconds: float | None = None) -> tuple[dict, list[dict]]:
    """Decode every frame, OCR at sample_hz, and return (window, all readings).

    No GPU detector is invoked. Start and end evidence are inferred independently. The caller can reuse readings for fuel counters
    after the cutoff. deadline is an absolute time.monotonic() deadline;
    limit_seconds restricts a benchmark to its requested clip prefix.
    A decode failure disables skipping. progress(frame_index) may enforce timeout.
    """
    import cv2
    if not math.isfinite(sample_hz) or sample_hz <= 0:
        raise ValueError('sample_hz must be positive')
    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not cap.isOpened() or fps <= 0 or total <= 0:
            raise RuntimeError('Cannot read video timing for match-window scan')
        if limit_seconds is not None:
            if not math.isfinite(limit_seconds) or limit_seconds <= 0:
                raise ValueError('limit_seconds must be positive')
            total = min(total, round(limit_seconds * fps))
        interval = max(1, round(fps / sample_hz))
        readings = []
        index = 0
        while index < total:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Match-window scan exceeded processing deadline')
            ok, frame = cap.read()
            if not ok:
                break
            if index % interval == 0:
                reading = scoreboard_reader(ocr, frame)
                readings.append({**reading, 'timestamp': index / fps})
                if progress:
                    progress(index)
            index += 1
        window = infer_match_window(readings, total / fps, buffer_seconds,
                                    start_buffer_seconds=start_buffer_seconds)
        window['prepass_frames'] = index
        if index != total:
            window.update(confirmed_start=None, inference_start=0.0,
                          start_reason='prepass_decode_incomplete', start_evidence=[],
                          confirmed_end=None, inference_end=total / fps,
                          full_clip=True, confidence='uncertain', reason='prepass_decode_incomplete')
        return window, readings
    finally:
        cap.release()
