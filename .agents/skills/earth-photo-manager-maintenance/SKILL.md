---
name: earth-photo-manager-maintenance
description: Maintain Earth Photo Manager when adding features, fixing bugs, changing settings or translations, or investigating its PySide6 UI and image workflow.
---

# Earth Photo Manager Maintenance

Work from the repository root and read `AGENTS.md` before acting. Preserve unrelated worktree changes.

## Find the ownership boundary

- Start at `earth_photo_manager.pyw` and `src/app.py` only for startup behavior.
- Use `src/main_window.py` for menus, actions, settings-dialog pages, filtering, selection, and coordination between windows.
- Use the feature window module when behavior is owned by a preview, RAW development, or slideshow window.
- Use `src/settings.py` for persisted values. Add a small dataclass when several values form one setting.
- Use `src/models.py`, `src/image_scanner.py`, `src/image_metadata.py`, `src/thumbnail_cache.py`, and `src/tag_store.py` for their respective data boundaries; avoid moving UI state into them.

Search for an existing adjacent feature before introducing a new interaction pattern. `src/preview_window.py`, `src/raw_development_window.py`, and `src/slideshow_window.py` are useful examples of secondary-window ownership and lifecycle.

## Implement UI changes end to end

For a user-facing feature, trace all affected entry points and state transitions:

1. Identify the canonical data source. For actions over visible photos, derive input from the current list widget order so filtering and sorting remain effective.
2. Add Japanese and English labels to the existing translation dictionaries in `src/main_window.py`.
3. Connect menu, shortcut, context-menu, and window actions to one coordinator method where they represent the same command.
4. Keep a Python reference to modeless Qt windows. Clear it from an explicit `closed` signal or equivalent deterministic close path.
5. Persist settings through `AppSettings`; initialize controls from saved values and save only accepted dialog values.
6. On application shutdown, close owned windows and stop timers/workers before allowing the main window to disappear.

When adding settings, check type conversion from `QSettings`: bool-like strings, missing keys, empty `QByteArray`, and values written by older versions need stable defaults.

## Verify

Read `WUV` from `.env` and use that Windows executable for project commands. Never run Linux `uv` against `.venv`.

Run focused syntax/import checks first, for example:

```sh
"$WUV" run python -m py_compile src/settings.py src/main_window.py
"$WUV" run python -c "from src.main_window import MainWindow; print('ok')"
```

Adjust the file list to the touched modules. For behavior involving focus, multiple monitors, native menus, fullscreen state, or window geometry, explain what still needs a Windows GUI check if it was not exercised interactively.

Before reporting completion, inspect `git diff --check`, the scoped diff, and `git status --short`. Do not include pre-existing changes in the claimed work.

## Related PySide6 examples

The sibling repository `../inf_daken_counter_obsw` may be consulted for established PySide6 patterns, especially `src/main_window.py`, `src/config_dialog.py`, `src/score_viewer.py`, and `notes_counter.pyw`. Treat it as reference code, not as authority: adapt patterns to this repository's existing `QSettings`, worker, and translation conventions.
