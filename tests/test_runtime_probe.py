from tools.probe_offline_runtime import runtime_errors


def test_ruffle_logged_error_is_not_mistaken_for_success():
    messages = [
        {'type': 'log', 'text': 'Loaded SWF version 32'},
        {'type': 'log', 'text': '%cERROR%c Error running AVM2 construction: TypeError #1010'},
        {'type': 'warning', 'text': 'Unknown tag code: 255'},
    ]
    assert runtime_errors(messages) == [messages[1]]


def test_javascript_and_console_errors_are_retained():
    messages = [{'type': kind, 'text': 'failure'} for kind in ('error', 'pageerror')]
    assert runtime_errors(messages) == messages
