# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-09-25

### Added

- README and banner for the desklet's page on the Cinnamon Spices website.

## [1.0.0] - 2026-09-24

First release.

### Added

- One rectangle per workspace, updated live as workspaces are added or removed.
- Click a rectangle to switch workspace. Scroll to move to the previous or next one, with optional wrap-around.
- Layout: horizontal, vertical or grid (rectangles per row or column), with adjustable spacing.
- Position: manual drag, or one of 9 screen positions (corners, edges, center) with an edge margin. The panel area is left clear.
- Multi-monitor: show on the primary monitor, a specific monitor, or all monitors.
- Multiple instances (up to 10), each with its own settings.
- Styling: width, height, border width (normal and active), corner radius, drop shadow, and background and border colors for normal, hover and active, with transparency.
- Labels: numbers, Roman numerals, letters (upper or lower case), or workspace names, with custom names per workspace. Font size, bold and text colors are adjustable.
- Translations: Spanish, Portuguese (Brazil), German, French, Russian, Italian, Polish and Simplified Chinese.
- Tests: `tests/official_checks.py` runs the official Cinnamon Spices checks, and `tests/live_test.py` tests the running desklet.

[1.0.1]: https://github.com/mgldvd/workspace-switcher-desklet/releases/tag/v1.0.1
[1.0.0]: https://github.com/mgldvd/workspace-switcher-desklet/releases/tag/v1.0.0
