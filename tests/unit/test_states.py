from app.domain.states import ProjectState, StepKey, StepStatus, progress_percent, step_statuses


def test_progress_percent_bounds():
    assert progress_percent(ProjectState.CREATED) == 0
    assert progress_percent(ProjectState.PUBLISHED) == 100


def test_progress_percent_increases_along_pipeline():
    assert progress_percent(ProjectState.AUDIO_READY) > progress_percent(ProjectState.NARRATION_READY)


def test_step_statuses_marks_completed_steps_as_success():
    statuses = step_statuses(ProjectState.AUDIO_READY)
    assert statuses[StepKey.DADOS] == StepStatus.SUCCESS
    assert statuses[StepKey.NARRACAO] == StepStatus.SUCCESS
    assert statuses[StepKey.AUDIO] == StepStatus.SUCCESS


def test_step_statuses_marks_current_step_as_running():
    statuses = step_statuses(ProjectState.NARRATION_GENERATING)
    assert statuses[StepKey.DADOS] == StepStatus.SUCCESS
    assert statuses[StepKey.NARRACAO] == StepStatus.RUNNING


def test_step_statuses_marks_future_steps_as_pending():
    statuses = step_statuses(ProjectState.CREATED)
    assert statuses[StepKey.NARRACAO] == StepStatus.PENDING
    assert statuses[StepKey.YOUTUBE] == StepStatus.PENDING
