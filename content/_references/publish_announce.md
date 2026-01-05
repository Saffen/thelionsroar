
1) Deterministic publish decisions
scripts/publish.py
Parses frontmatter
Handles draft, scheduled, published, archived
Bulk mode and single mode
Time override for testing
Machine-readable JSON output
This is the brain of the system.

2) Safe orchestration
scripts/run_publish.py
Bulk scans content
Tracks state in state/published.json
Idempotent
Dry-run vs apply
Meaningful exit codes
This is the control layer.

3) Discord integration (dual-channel)
scripts/announce_discord.py
Creates a forum thread per article
Rich starter post with image, author, publish time, teaser
Posts a secondary announcement in a regular channel
Links back to the forum thread
Stores message IDs and thread IDs
Automatically upgrades older state schemas
This is the distribution layer.

4) State persistence
state/published.json
Article ID as the stable key
Records:
when it was published
forum thread id
starter message id
announcement message id
Prevents duplicates
Enables later edits
This is the memory.

5) Configuration and secrets
.env for secrets
.env.example as documentation
_env.py loader
No secrets in git
This is deploy-safe.




What is intentionally NOT done yet
And this is important: these are separate phases, not missing pieces.
❌ Static HTML rendering
Not started yet, and that is correct.
You explicitly decided:
“Publishing framework first, rendering after”
That was the right call. Rendering can now be built on top without touching any of the above.

❌ Image processing
Right now images are:
validated structurally
passed through to Discord
Later you can add:
file existence checks
thumbnail generation
WebP conversion
But publishing does not depend on that yet.

❌ Cron / automation
You have everything needed, but you have not wired it to cron.
That is a 10-minute job later.