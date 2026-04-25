from gateway.notebooklm_hub_state import (
    clear_selected_notebook,
    get_selected_notebook,
    set_selected_notebook,
)



def test_set_and_get_selected_notebook(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    result = set_selected_notebook(
        "agent:main:telegram:group:-1003586456169:3",
        notebook="NLM Lab",
        notebook_id="nb-hub",
    )

    assert result == {
        "notebook": "NLM Lab",
        "notebook_id": "nb-hub",
    }
    assert get_selected_notebook("agent:main:telegram:group:-1003586456169:3") == {
        "notebook": "NLM Lab",
        "notebook_id": "nb-hub",
    }



def test_clear_selected_notebook(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    session_key = "agent:main:telegram:group:-1003586456169:3"

    set_selected_notebook(session_key, notebook="NLM Lab", notebook_id="nb-hub")

    assert clear_selected_notebook(session_key) is True
    assert get_selected_notebook(session_key) is None
    assert clear_selected_notebook(session_key) is False
