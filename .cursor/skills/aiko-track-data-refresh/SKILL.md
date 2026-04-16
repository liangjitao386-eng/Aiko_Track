---
name: aiko-track-data-refresh
description: Update the Aiko Track static webpage with the latest SMM data by running the local refresh script, verifying that `index.html` reflects the newest dates, and fixing leftover text such as share meta descriptions. Use when the user says "更新网页数据", "获取最新数据更新网页", "同步最新 SMM 数据", or asks to refresh the Aiko Track page data.
---

# Aiko Track Data Refresh

## Purpose

Use this skill for the `Aiko_Track` project when the user wants the webpage refreshed with the latest market data.

The default workflow is:

1. Inspect the existing update path before changing files.
2. Run the local data refresh script.
3. Verify that `index.html` was updated to the newest available date.
4. Check for leftover stale text that the script may not cover.
5. Fix any leftover text manually.
6. Report the main updated values back to the user.

## Project Files

- Main page: `index.html`
- Refresh script: `update_smm_data.py`

## Required Workflow

### 1. Confirm the current update mechanism

Before running anything, read `update_smm_data.py` and confirm:

- It fetches SMM data and writes back into `index.html`.
- Which visible date fields it updates.
- Whether it also updates share metadata such as `og:description`.

Also inspect `index.html` for current update text such as:

- `数据更新时间`
- `SMM真实数据`
- `og:description`

### 2. Run the refresh script

From the project root, run:

```bash
python3 "update_smm_data.py"
```

Treat a successful script run as necessary but not sufficient. The page is not fully updated until the follow-up checks below pass.

### 3. Verify the HTML really changed

After the script finishes, verify in `index.html`:

- The visible page update text now shows the newest date.
- The embedded `smmData` block contains the latest fetched rows.
- No expected core dataset is missing.

If helpful, inspect the diff for `index.html` to confirm what changed.

### 4. Check for stale text outside the script's replacement scope

This project has an important edge case: the script may update the page data and visible update labels, but miss other text fields.

Always search `index.html` for:

- The previously displayed date, if known
- Compact date strings such as `YYYYMMDD`
- Share metadata like `og:description`

If any stale date remains in user-visible or share-visible text, update it manually.

Important: do not stop after the script succeeds. The manual stale-text sweep is part of the standard workflow.

### 5. Validate after edits

After any manual edit:

- Re-run a targeted search to make sure the stale date is gone.
- Run lints on edited files when available.

## Response Format

Keep the final response short and outcome-focused. Include:

- That the webpage data was updated
- The new page date
- Any manual follow-up fix applied beyond the script
- A few key latest values if the script printed them

## Example Outcome

Example summary:

```markdown
网页数据已经更新到最新。

我执行了 `update_smm_data.py`，并把 `index.html` 同步到了最新 SMM 数据，页面显示更新时间现为 `2026-04-16`。另外我修正了分享卡片里的 `og:description` 日期，避免外部分享时还显示旧日期。
```

## Notes

- Prefer the existing project script over ad hoc manual data edits.
- Do not assume script success means all webpage text is current.
- Preserve unrelated user changes in `index.html`.
