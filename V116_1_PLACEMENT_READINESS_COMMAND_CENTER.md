# V116.1 Placement Readiness Command Center

This release adds a placement-focused layer without replacing the existing exam, practice, curriculum, attendance or practical systems.

## Included
- Placement Readiness Command Center by batch/section.
- Evidence-based Student Skill Passport.
- Company Drive Simulator with reusable approved questions first and AI generation only for shortages.
- Curriculum-to-placement coverage signals from uploaded syllabus text/topics.
- Targeted improvement plans that launch existing Practice Mode questions.
- CSV import for normalized external evidence from coding/certification/placement platforms.
- Navigation links for staff and students.

## Important design constraints
- Employer names are labels only. Generated mocks are original skills-based simulations and must not be presented as official/leaked company papers.
- Readiness scores summarize available evidence. Missing evidence is shown as Not measured, not as a negative student judgement.
- AI-generated placement questions remain Draft/Pending Review until faculty approval, consistent with the existing AI exam workflow.
- No destructive migration is required. New SQLAlchemy tables are created by the existing Base.metadata.create_all startup path.

## External evidence CSV
Columns:
`roll_no,provider,skill,score,max_score,evidence_label`

Skill must match an active placement skill name.
