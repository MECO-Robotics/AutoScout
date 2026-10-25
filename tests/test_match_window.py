import pytest

from autoscout.match_window import infer_match_window, parse_clock


def reading(t, seconds, **kwargs):
    return {'timestamp': t, 'texts': [{'text': f'{seconds // 60}:{seconds % 60:02}',
             'confidence': .99, 'x': .5, 'y': .089, **kwargs}]}


def countdown(start=70):
    return [reading(i / 2, max(0, start - int(i / 2))) for i in range(2 * (start + 3))]


def test_end_has_buffer_and_repeated_evidence():
    result = infer_match_window(countdown(), 100)
    assert result['confirmed_end'] == 70
    assert result['inference_end'] == 75
    assert not result['full_clip']


@pytest.mark.parametrize('samples', [countdown(20), countdown(10), [], [reading(70, 0)]])
def test_auto_missing_and_midmatch_unknown(samples):
    assert infer_match_window(samples, 100)['full_clip']


def test_later_reset_or_replay_invalidates_whole_cutoff():
    result = infer_match_window(countdown() + [reading(85, 20)], 100)
    assert result['full_clip']
    assert result['reason'] == 'later_clock_contradicts_end'


def test_auto_reset_then_complete_teleop():
    samples = countdown(20) + [{**r, 'timestamp': r['timestamp'] + 25} for r in countdown()]
    assert infer_match_window(samples, 120)['confirmed_end'] == 95


def test_isolated_zero_does_not_stop_processing():
    samples = countdown()[:140] + [reading(70, 0)]
    assert infer_match_window(samples, 100)['full_clip']


def test_countdown_gap_and_impossible_jump_are_uncertain():
    assert infer_match_window(countdown()[:10] + countdown()[130:], 100)['full_clip']
    assert infer_match_window([reading(0, 140), reading(1, 2)] +
                             [reading(t, 0) for t in (2, 3, 4)], 100)['full_clip']


def test_duplicates_do_not_confirm_zero():
    samples = countdown()[:140] + [reading(70, 0)] * 4
    assert infer_match_window(samples, 100)['full_clip']


def test_delayed_scores_and_missing_overlay_preserve_end():
    samples = countdown() + [{'timestamp': 90, 'blue': 180, 'texts': []}]
    assert infer_match_window(samples, 100)['inference_end'] == 75


def test_wrong_clock_location_and_low_confidence_rejected():
    assert parse_clock(reading(0, 0, y=.137)) is None
    assert parse_clock(reading(0, 0, confidence=.89)) is None
    assert parse_clock(reading(0, 0, x=.44)) is None


def test_configurable_buffer_and_clip_limit():
    assert infer_match_window(countdown(), 100, 10)['inference_end'] == 80
    assert infer_match_window(countdown(), 73, 10)['full_clip']
    with pytest.raises(ValueError):
        infer_match_window([], 100, -1)


def pre_match_countdown():
    return ([reading(t / 2, 20) for t in range(21)] +
            [reading(10 + i / 2, 20 - (i + 1) // 2) for i in range(1, 39)])


def test_start_plateau_preserves_three_second_identification_buffer():
    result = infer_match_window(pre_match_countdown(), 100)
    assert result['confirmed_start'] == 10
    assert result['inference_start'] == 7
    assert result['inference_end'] == 100
    assert not result['full_clip']
    assert len(result['start_evidence']) == 5


@pytest.mark.parametrize('samples', [
    countdown(20), countdown(19),
    [reading(0, 20), reading(10, 20), reading(11, 19), reading(12, 18), reading(13, 17)],
    [reading(t, 20) for t in range(10)] + [reading(10, 19)],
    [reading(t, 20) for t in range(10)] + [reading(10, 19), reading(11, 15), reading(12, 14)],
    [reading(0, 18)] + pre_match_countdown(),
    pre_match_countdown() + [reading(40, 20)],
])
def test_start_ambiguous_clips_keep_beginning(samples):
    result = infer_match_window(samples, 100)
    assert result['confirmed_start'] is None
    assert result['inference_start'] == 0


def test_start_and_end_bounds_coexist_with_teleop_clock_passing_twenty():
    samples = pre_match_countdown() + [
        {**r, 'timestamp': r['timestamp'] + 35} for r in countdown()]
    result = infer_match_window(samples, 120)
    assert result['inference_start'] == 7
    assert result['confirmed_end'] == 105
    assert result['inference_end'] == 110


def test_start_buffer_configurable_and_validated():
    assert infer_match_window(pre_match_countdown(), 100,
                              start_buffer_seconds=20)['inference_start'] == 0
    with pytest.raises(ValueError):
        infer_match_window([], 100, start_buffer_seconds=-1)
