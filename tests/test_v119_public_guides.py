from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from public_content import PUBLIC_GUIDES, discover_public_updates, public_sitemap_paths, related_updates

APP=(ROOT/'app.py').read_text(encoding='utf-8')
BASE=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
GUIDES=(ROOT/'templates'/'public_guides.html').read_text(encoding='utf-8')
GUIDE=(ROOT/'templates'/'public_guide.html').read_text(encoding='utf-8')
UPDATES=(ROOT/'templates'/'public_updates.html').read_text(encoding='utf-8')
SITEMAP=(ROOT/'sitemap.xml').read_text(encoding='utf-8')


def test_public_footer_links_and_routes_exist():
    assert "@app.route('/guides')" in APP
    assert "@app.route('/guides/<slug>')" in APP
    assert "@app.route('/updates')" in APP
    assert "@app.route('/updates/<slug>')" in APP
    assert "url_for('public_guides')" in BASE
    assert "url_for('public_updates')" in BASE


def test_public_pages_are_indexable_only_on_canonical_production_host():
    assert "public_seo_endpoints={'home','public_guides','public_guide','public_updates','public_update_detail'}" in APP
    assert "and is_public_seo_host()" in APP
    assert "X-Robots-Tag','noindex, nofollow" in APP


def test_visual_guide_registry_covers_major_workflows():
    expected={'admin-assistant','question-bank','exam-delivery','attendance','practical-assessment','placement-readiness','student-practice','offline-exams'}
    assert expected.issubset(PUBLIC_GUIDES)
    for slug in expected:
        guide=PUBLIC_GUIDES[slug]
        assert len(guide['workflow']) == 4
        assert guide['description']
        assert guide['capabilities']


def test_public_release_metadata_is_discovered_and_attached_to_guides():
    updates=discover_public_updates(ROOT)
    titles={item['title'] for item in updates}
    assert 'Bulk Question Review & Approval' in titles
    assert 'Rotating Room QR Attendance' in titles
    assert 'Placement Readiness Command Center' in titles
    attendance=related_updates(ROOT,'attendance')
    assert attendance and attendance[0]['guide_slug']=='attendance'
    assert all(item['summary'] for item in updates)


def test_visual_pages_use_auto_latest_update_panel():
    assert 'latest_update' in GUIDE
    assert 'Latest improvement' in GUIDE
    assert 'Generated from public guide data' in GUIDE
    assert 'PUBLIC_UPDATE' in UPDATES
    assert 'Automatically refreshed' in GUIDES


def test_live_sitemap_registry_includes_guides_and_public_updates():
    paths=public_sitemap_paths(ROOT)
    assert '/guides' in paths
    assert '/updates' in paths
    assert '/guides/question-bank' in paths
    assert '/updates/bulk-question-review-approval-2026-08-29' in paths
    assert '<loc>https://exam.learnwithhemant.com/guides</loc>' in SITEMAP
    assert '<loc>https://exam.learnwithhemant.com/updates</loc>' in SITEMAP


def test_public_update_pages_do_not_expose_internal_version_labels():
    public_templates=[GUIDES, GUIDE, UPDATES, (ROOT/'templates'/'public_update_detail.html').read_text(encoding='utf-8')]
    assert all('update.version' not in template for template in public_templates)
    assert all('latest_update.version' not in template for template in public_templates)
    updates=discover_public_updates(ROOT)
    assert updates
    assert all('version' not in item for item in updates)
    assert all(not item['slug'].startswith('v') or not item['slug'][1:2].isdigit() for item in updates)
