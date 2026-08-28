from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'static/app.js').read_text(encoding='utf-8')

def test_secure_final_submit_uses_background_request():
    assert 'async function submitExamToServer' in JS
    assert "response=await fetch(form.action" in JS
    assert "'Accept':'application/json'" in JS

def test_result_navigation_is_delegated_to_outer_shell():
    assert "type:'secure-exam-submitted'" in JS
    assert "window.parent.postMessage" in JS
    assert 'payload.submitted_url' in JS

def test_rejected_submit_keeps_shell_alive():
    assert "examSubmissionInProgress=false" in JS
    assert 'return {ok:false,payload:payload,status:response.status}' in JS
