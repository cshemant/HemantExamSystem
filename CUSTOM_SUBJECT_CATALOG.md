# Custom Subject Catalog – V14.2

This update adds a persistent Subject Catalog to the Question Bank.

## Faculty workflow

1. Open **Question Bank**.
2. In **Subject Catalog**, enter or choose a **Category**.
3. Enter the **New Subject** name and an optional default **Course / Semester**.
4. Click **Add Subject**.
5. The subject immediately appears inside that category in the **Add Bank Question** subject selector and in Question Bank filters.

Example:

- Category: `Emerging Technologies`
- Subject: `Quantum Computing`
- Default Course / Semester: `B.Tech CSE / Sem 7`

The question form will then show `Quantum Computing` under the `Emerging Technologies` group.

## Existing data

No existing question-bank data needs to be deleted or recreated. On startup, the system creates the new `subject_catalog` table automatically and registers bundled/pre-existing subjects. Existing custom subjects from older databases are preserved under `Custom / Other` until a better category is assigned.

## Bulk import

Question Bank CSV/XLSX templates now include an optional `category` column. When importing a new subject, the category is automatically registered in the Subject Catalog. If the column is blank, a new imported subject is placed under `Imported / Other`.
