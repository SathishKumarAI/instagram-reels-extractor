"""One route group per file. `app.create_app` includes every builder in ROUTERS.

Adding an endpoint means editing exactly one of these, or adding a module here
and one line to ROUTERS — never reopening a 900-line app factory.
"""

from __future__ import annotations

from . import compare, discover, exports, health, library, qa, sync

# order is display order in /docs; route matching does not depend on it, except
# for the SPA catch-all, which create_app mounts after all of these
ROUTERS = [health.build, library.build, qa.build, exports.build,
           sync.build, compare.build, discover.build]
