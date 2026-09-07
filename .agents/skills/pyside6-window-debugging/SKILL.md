---
name: pyside6-window-debugging
description: Diagnose and fix PySide6 desktop window behavior involving modeless dialogs, focus, signals, timers, context menus, fullscreen or multi-monitor placement, and saved geometry.
---

# PySide6 Window Debugging

Use this workflow for bugs such as a window opening only on the second attempt, controls being clipped after restoring position, menus inheriting unreadable colors, or cleanup running inconsistently.

## Trace lifecycle before changing layout

Map these separately:

- Python ownership: which object keeps the window alive.
- Qt ownership: parent, window flags, and whether deletion on close is enabled.
- Visibility: `show`, `showFullScreen`, `hide`, `close`, and deferred deletion.
- State cleanup: timers, animations, workers, signal connections, and the owner's stored reference.

Prefer a feature-level `closed` signal emitted from `closeEvent` when an owner must clear its reference. Do not rely only on `destroyed`: closing commonly hides a QWidget without immediately destroying its wrapper. Make close handling idempotent because keyboard, menu, parent shutdown, and native window controls may converge on it.

Stop active `QTimer` and `QPropertyAnimation` objects during close. Avoid callbacks that can update a closing widget. For modeless windows, retain an instance attribute and raise/activate an already-visible instance instead of creating duplicates.

## Check input routing

Inspect the event target as well as the containing window. Child labels and viewports can receive keys, wheel events, mouse events, and context-menu events first.

- Use actions and shortcuts for window-level commands when possible.
- Use `eventFilter` only when the receiving child must be intercepted.
- Return the correct handled state and preserve the base implementation for unhandled events.
- Give helper windows explicit focus policies when their controls should or should not take keyboard navigation from the main experience.

For context menus with application stylesheets, set explicit menu foreground, background, disabled, and selected colors when native palette inheritance produces unreadable text.

## Restore windows defensively

Saved coordinates are untrusted because monitors, DPI, fonts, translations, and content length can change.

1. Build content and call `adjustSize()` or establish constraints before clamping position.
2. Use the current screen's `availableGeometry()` for ordinary windows; use the owning fullscreen window's global frame when a tool must remain inside it.
3. Clamp using the window's actual `frameGeometry()`, accounting for frame and title-bar size.
4. Keep a usable margin and fall back to a centered/default position when the saved point is invalid or entirely off-screen.
5. Re-clamp after dynamic text changes if they can alter `sizeHint()`.

When a helper window should restore consistently regardless of which monitor launches the feature, store coordinates relative to the owning feature window, then convert with `mapToGlobal` and clamp at restore time. Store absolute screen coordinates only when that is the intended contract.

## Multi-monitor and fullscreen checks

Choose the target `QScreen` from the initiating widget's current geometry, not from the cursor or global primary screen unless the product requires that. Move the window to the target screen geometry before entering fullscreen. Confirm behavior for negative desktop coordinates and mixed DPI arrangements.

## Verification

Use a focused import/compile check and, when feasible, a minimal `QApplication` harness that creates, shows, closes, and reopens the affected window while processing events. Assertions should cover reference cleanup, timer shutdown, visibility, saved position, and clamping.

Native window flags, fullscreen focus, popup styling, and multi-monitor placement still require a real GUI check on the target OS. Report that residual check explicitly when automation did not cover it.

For additional examples, inspect the active repository first. The sibling `../inf_daken_counter_obsw` contains useful PySide6 lifecycle and geometry code, but its configuration and ownership conventions may differ.
