from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PUBLIC_GUIDES: dict[str, dict[str, Any]] = {
    'admin-assistant': {
        'slug': 'admin-assistant',
        'title': 'Admin Assistant & Faster Exam Setup',
        'short_title': 'Admin Assistant',
        'eyebrow': 'For faculty & administrators',
        'description': 'Use natural-language and voice-assisted workflows to move around the exam system and prepare common administrative tasks faster.',
        'audiences': ['Faculty', 'Admin'],
        'icon': 'AI',
        'workflow': [
            {'label': 'Ask', 'title': 'Say what you need', 'text': 'Use a natural instruction instead of memorising every menu path.'},
            {'label': 'Understand', 'title': 'Interpret the intent', 'text': 'The assistant maps the request to supported exam-system actions and destinations.'},
            {'label': 'Review', 'title': 'Keep the human in control', 'text': 'Sensitive changes remain visible for staff review before they are committed.'},
            {'label': 'Continue', 'title': 'Open the right workflow', 'text': 'Move into question banks, exams, attendance, placement or other staff tools.'},
        ],
        'capabilities': ['Natural-language navigation', 'Voice-assisted commands', 'Safe form assistance', 'Role-aware staff tools'],
        'why_it_matters': 'Faculty can spend less time searching through menus while keeping approval and academic decisions under human control.',
    },
    'question-bank': {
        'slug': 'question-bank',
        'title': 'Question Bank, Review & Exam Blueprint',
        'short_title': 'Question Bank',
        'eyebrow': 'Assessment preparation',
        'description': 'Organize questions by subject and unit, review draft content, approve eligible questions and reuse trusted items when building assessments.',
        'audiences': ['Faculty', 'Admin'],
        'icon': 'QB',
        'workflow': [
            {'label': 'Organize', 'title': 'Build the bank', 'text': 'Group questions by subject, unit, difficulty and question type.'},
            {'label': 'Review', 'title': 'Check individual drafts', 'text': 'Faculty can inspect and correct generated or imported items before approval.'},
            {'label': 'Approve', 'title': 'Approve selected questions', 'text': 'Select reviewed eligible drafts and approve them together when appropriate.'},
            {'label': 'Reuse', 'title': 'Create exam blueprints', 'text': 'Use approved content to prepare controlled question pools and assessments.'},
        ],
        'capabilities': ['Subject & unit organization', 'Draft review', 'Bulk approval', 'Difficulty-aware banks', 'Exam blueprints'],
        'why_it_matters': 'A reviewed reusable question bank reduces repeated preparation work without removing faculty oversight.',
    },
    'exam-delivery': {
        'slug': 'exam-delivery',
        'title': 'Secure Online Exam Delivery',
        'short_title': 'Online Exams',
        'eyebrow': 'From schedule to submission',
        'description': 'Schedule browser-based exams, deliver randomized papers, preserve answers with autosave and guide students through a controlled submission flow.',
        'audiences': ['Faculty', 'Admin', 'Student'],
        'icon': 'EX',
        'workflow': [
            {'label': 'Create', 'title': 'Prepare the assessment', 'text': 'Choose the subject, question pool, duration and student access rules.'},
            {'label': 'Schedule', 'title': 'Open at the right time', 'text': 'Students see eligible assessments according to the configured exam window.'},
            {'label': 'Attempt', 'title': 'Answer with autosave', 'text': 'Randomized delivery and autosave help protect the integrity and continuity of the attempt.'},
            {'label': 'Submit', 'title': 'Finish with a receipt', 'text': 'Manual or timed submission ends on a clear confirmation screen.'},
        ],
        'capabilities': ['Scheduling', 'Randomized questions/options', 'Autosave & resume', 'Timed submission', 'Integrity controls'],
        'why_it_matters': 'Students get a clearer exam journey while faculty retain control over timing, access and assessment configuration.',
    },
    'attendance': {
        'slug': 'attendance',
        'title': 'Classroom Attendance Verification',
        'short_title': 'Attendance',
        'eyebrow': 'Presence with classroom context',
        'description': 'Create a short attendance window, display a rotating room QR or code, and let students complete the permitted verification flow from the classroom network.',
        'audiences': ['Faculty', 'Student'],
        'icon': 'AT',
        'workflow': [
            {'label': 'Start', 'title': 'Faculty opens a session', 'text': 'The attendance window is tied to the class and configured network rules.'},
            {'label': 'Display', 'title': 'Show rotating room access', 'text': 'A short-lived QR and room code are displayed for students in the room.'},
            {'label': 'Verify', 'title': 'Student confirms presence', 'text': 'The server validates the active session and permitted verification conditions.'},
            {'label': 'Record', 'title': 'Attendance is saved', 'text': 'The completed verification is attached to the logged-in student and session.'},
        ],
        'capabilities': ['Rotating room QR', 'Short room code', 'Session window', 'Network checks', 'Student-bound completion'],
        'why_it_matters': 'The workflow is designed to be quick in class while making simple remote attendance sharing harder.',
    },
    'practical-assessment': {
        'slug': 'practical-assessment',
        'title': 'Practical Assessment & Lab Marks',
        'short_title': 'Practical Assessment',
        'eyebrow': 'Lab evaluation workflow',
        'description': 'Track practical attendance, records, code performance, viva and component marks in one place while keeping the student view clear.',
        'audiences': ['Faculty', 'Student'],
        'icon': 'PR',
        'workflow': [
            {'label': 'Prepare', 'title': 'Set the practical task', 'text': 'Faculty maps the experiment, reference expectations and assessment window.'},
            {'label': 'Perform', 'title': 'Student completes the work', 'text': 'Students submit or demonstrate the practical work during the allowed period.'},
            {'label': 'Evaluate', 'title': 'Record component marks', 'text': 'Attendance, record, performance and viva can be reviewed in the same workflow.'},
            {'label': 'View', 'title': 'Student sees the breakdown', 'text': 'Published practical marks are shown in a readable component-wise view.'},
        ],
        'capabilities': ['Practical registers', 'Record tracking', 'Code evaluation support', 'Viva marks', 'Component-wise results'],
        'why_it_matters': 'Practical assessment stays connected to the exam system instead of being split across unrelated sheets and tools.',
    },
    'placement-readiness': {
        'slug': 'placement-readiness',
        'title': 'Placement Readiness & Skill Passport',
        'short_title': 'Placement Readiness',
        'eyebrow': 'Evidence-based preparation',
        'description': 'Combine assessment evidence into skill views, identify gaps and launch targeted practice or mock-drive preparation without treating missing evidence as failure.',
        'audiences': ['Faculty', 'Admin', 'Student'],
        'icon': 'PL',
        'workflow': [
            {'label': 'Measure', 'title': 'Collect available evidence', 'text': 'Use exam, practice or imported evidence that is actually available for a skill.'},
            {'label': 'Map', 'title': 'Build the skill passport', 'text': 'Students can see measured strengths while unmeasured areas remain clearly labelled.'},
            {'label': 'Improve', 'title': 'Target the gaps', 'text': 'Faculty can create improvement plans that reuse existing practice workflows.'},
            {'label': 'Simulate', 'title': 'Prepare for drives', 'text': 'Skills-based mock assessments can be prepared without presenting them as leaked company papers.'},
        ],
        'capabilities': ['Skill passport', 'Readiness dashboard', 'Gap analysis', 'Improvement plans', 'Drive simulation'],
        'why_it_matters': 'Placement preparation becomes evidence-led and actionable instead of relying only on one overall score.',
    },
    'student-practice': {
        'slug': 'student-practice',
        'title': 'Student Practice Centre',
        'short_title': 'Student Practice',
        'eyebrow': 'Practice before the exam',
        'description': 'Give students a separate place to practise approved questions, learn from attempts and strengthen weak topics without changing the live exam workflow.',
        'audiences': ['Student', 'Faculty'],
        'icon': 'ST',
        'workflow': [
            {'label': 'Choose', 'title': 'Select a practice area', 'text': 'Students start from available subjects or targeted improvement activities.'},
            {'label': 'Attempt', 'title': 'Work through questions', 'text': 'Practice stays separate from formal exam attempts and results.'},
            {'label': 'Review', 'title': 'See the learning outcome', 'text': 'Students can use the result to understand which topics need more attention.'},
            {'label': 'Repeat', 'title': 'Strengthen weak areas', 'text': 'The same practice workflow can support targeted improvement plans over time.'},
        ],
        'capabilities': ['Separate practice mode', 'Approved-question reuse', 'Attempt results', 'Targeted improvement'],
        'why_it_matters': 'Students can practise within the same academic ecosystem without mixing practice attempts with formal examinations.',
    },
    'offline-exams': {
        'slug': 'offline-exams',
        'title': 'Offline & LAN-Ready Exams',
        'short_title': 'Offline Exams',
        'eyebrow': 'Internet-independent option',
        'description': 'Run a Windows-based local exam setup over a LAN when internet connectivity is unreliable or an institution prefers a local examination environment.',
        'audiences': ['Faculty', 'Admin', 'Student'],
        'icon': 'LAN',
        'workflow': [
            {'label': 'Install', 'title': 'Prepare the local host', 'text': 'Use the packaged Windows exam system on the designated machine.'},
            {'label': 'Connect', 'title': 'Use the local network', 'text': 'Student devices connect to the exam host through the institution LAN.'},
            {'label': 'Conduct', 'title': 'Run the assessment locally', 'text': 'The exam workflow continues without depending on public internet connectivity.'},
            {'label': 'Review', 'title': 'Keep results in the local workflow', 'text': 'Faculty can continue with the supported evaluation and result processes.'},
        ],
        'capabilities': ['Windows package', 'LAN-ready access', 'Internet-independent delivery', 'Local examination environment'],
        'why_it_matters': 'Institutions have a practical fallback when internet reliability should not determine whether an exam can proceed.',
    },
}


_PUBLIC_UPDATE_RE = re.compile(r'<!--\s*PUBLIC_UPDATE\s*(.*?)-->', re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r'^#\s+(.+?)\s*$', re.MULTILINE)
_VERSION_RE = re.compile(r'^V(\d+)(?:_(\d+))?', re.IGNORECASE)
_NON_SLUG_RE = re.compile(r'[^a-z0-9]+')


def _slugify(value: str) -> str:
    return _NON_SLUG_RE.sub('-', value.lower()).strip('-')


def _version_parts(path: Path) -> tuple[int, int]:
    match = _VERSION_RE.match(path.name)
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2) or 0))



def _parse_public_update(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return None
    marker = _PUBLIC_UPDATE_RE.search(text)
    if not marker:
        return None
    fields: dict[str, str] = {}
    for raw_line in marker.group(1).splitlines():
        line = raw_line.strip()
        if not line or ':' not in line:
            continue
        key, value = line.split(':', 1)
        fields[key.strip().lower()] = value.strip()
    summary = fields.get('summary', '').strip()
    if not summary:
        return None
    title_match = _TITLE_RE.search(text)
    title = fields.get('title', '').strip() or (title_match.group(1).strip() if title_match else path.stem.replace('_', ' '))
    title = re.sub(r'^V\d+(?:\.\d+)?\s*[—–:-]\s*', '', title, flags=re.IGNORECASE).strip()
    audiences = [item.strip() for item in fields.get('audience', 'Everyone').split(',') if item.strip()]
    guide_slug = fields.get('guide', '').strip()
    if guide_slug and guide_slug not in PUBLIC_GUIDES:
        guide_slug = ''
    highlights = [item.strip() for item in fields.get('highlights', '').split('|') if item.strip()]
    date = fields.get('date', '').strip()
    slug_seed = f'{title}-{date}' if date else title
    slug = fields.get('slug', '').strip() or _slugify(slug_seed)
    return {
        'slug': slug,
        'version_parts': _version_parts(path),
        'title': title,
        'summary': summary,
        'audiences': audiences or ['Everyone'],
        'guide_slug': guide_slug,
        'guide': PUBLIC_GUIDES.get(guide_slug),
        'highlights': highlights,
        'date': date,
        'source_file': path.name,
    }


def discover_public_updates(resource_dir: Path) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    for path in resource_dir.glob('V*.md'):
        item = _parse_public_update(path)
        if item:
            updates.append(item)
    updates.sort(key=lambda item: (item['version_parts'][0], item['version_parts'][1], item['slug']), reverse=True)
    return updates


def get_public_guide(slug: str) -> dict[str, Any] | None:
    return PUBLIC_GUIDES.get((slug or '').strip().lower())


def public_update_by_slug(resource_dir: Path, slug: str) -> dict[str, Any] | None:
    for update in discover_public_updates(resource_dir):
        if update['slug'] == slug:
            return update
    return None


def related_updates(resource_dir: Path, guide_slug: str, limit: int | None = None) -> list[dict[str, Any]]:
    items = [item for item in discover_public_updates(resource_dir) if item.get('guide_slug') == guide_slug]
    return items[:limit] if limit else items


def public_sitemap_paths(resource_dir: Path) -> list[str]:
    paths = ['/', '/guides', '/updates']
    paths.extend(f"/guides/{slug}" for slug in PUBLIC_GUIDES)
    paths.extend(f"/updates/{item['slug']}" for item in discover_public_updates(resource_dir))
    return paths
