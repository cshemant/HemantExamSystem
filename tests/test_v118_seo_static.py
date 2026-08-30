from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BASE=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
LOGIN=(ROOT/'templates'/'login.html').read_text(encoding='utf-8')
CSS=(ROOT/'static'/'style.css').read_text(encoding='utf-8')


def test_public_home_has_search_metadata_and_schema():
    assert 'Online Exam System for Colleges & Faculty | Learn with Hemant' in APP
    assert "'seo_canonical_url':canonical" in APP
    assert 'name="description"' in BASE
    assert 'rel="canonical"' in BASE
    assert 'application/ld+json' in BASE
    assert "'@type':'WebSite'" in APP
    assert "'@type':'Organization'" in APP
    assert "'@type':'WebApplication'" in APP


def test_crawler_endpoints_and_private_noindex_exist():
    assert "@app.route('/robots.txt')" in APP
    assert "@app.route('/sitemap.xml')" in APP
    assert "X-Robots-Tag','noindex, nofollow" in APP
    assert 'SEO_CANONICAL_HOST' in APP


def test_login_workflow_fields_are_preserved():
    assert 'name="login_type" value="student"' in LOGIN
    assert 'name="login_type" value="admin"' in LOGIN
    assert 'name="csrf_token" value="{{ csrf_token }}"' in LOGIN
    assert 'name="roll_no"' in LOGIN
    assert 'name="username"' in LOGIN
    assert 'name="password" type="password"' in LOGIN


def test_visible_homepage_content_targets_exam_system_naturally():
    assert 'Secure online and offline exam system' in LOGIN
    assert 'One exam system for the complete assessment workflow' in LOGIN
    assert 'From question creation to results' in LOGIN
    assert 'Common questions' in LOGIN
    assert '.public-seo-section' in CSS


def test_physical_crawler_files_are_packaged():
    robots=(ROOT/'robots.txt').read_text(encoding='utf-8')
    sitemap=(ROOT/'sitemap.xml').read_text(encoding='utf-8')
    assert 'User-agent: *' in robots
    assert 'Sitemap: https://exam.learnwithhemant.com/sitemap.xml' in robots
    assert '<loc>https://exam.learnwithhemant.com/</loc>' in sitemap

def test_hero_is_clean_while_descriptive_seo_copy_remains_visible():
    hero_start=LOGIN.index('<div class="intro-main">')
    hero_end=LOGIN.index('<div class="offline-download-box">')
    hero=LOGIN[hero_start:hero_end]
    assert 'Create, schedule and conduct assessments with question banks' not in hero
    assert 'helps faculty create, schedule and conduct assessments with question banks' in LOGIN
    assert 'randomized papers, autosave, automatic scoring, attendance and practical evaluation tools' in LOGIN

