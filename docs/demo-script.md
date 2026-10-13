# Demo capture and spoken explanation

The recorder captures a real browser investigation, asserts observed states and
regression outcomes, and saves the exact evidence ZIP and run record alongside
the raw footage. Its default is a local reference run with provider credentials
blanked in the server environment. A reference clip is labelled throughout and
cannot demonstrate the hackathon's actual NVIDIA/Nebius integration.

```bash
npm run build --prefix apps/web
REPLAYLAB_BROWSER_PATH=/path/to/chrome npm run demo --prefix apps/web
python scripts/render_demo.py docs/demo/reference-TIMESTAMP --espeak /path/to/espeak-ng
```

Install Playwright Chromium if using its bundled browser. Rendering requires
FFmpeg/ffprobe and eSpeak NG (or the explicit path to a local build). Narration
text is original and uses a generic synthetic English voice. See
[third-party notices](../THIRD_PARTY_NOTICES.md). Artifacts in `docs/demo/` are
excluded from source control and container builds.

After live preflight passes, load the private provider environment and rerun:

```bash
REPLAYLAB_DEMO_MODE=live npm run demo --prefix apps/web
python scripts/render_demo.py docs/demo/live-TIMESTAMP
```

Live capture requires an actual verified run with model calls, NVIDIA model IDs,
and Sandbox operation IDs. Failed recordings retain raw footage and do not yield
a success-labelled final clip. Preserve failed run evidence in evaluation too.

The eight scenes explain the incident, reviewed contract, real execution,
original/candidate observations, red/green regression, restart, independent
scenario matrix, and export. Rendering trims idle time and explicitly labels
compressed waiting. The manifest retains actual execution time. The final clip
must be below three minutes and show over a minute of the application in action.

Before publishing a final live clip, watch it with sound, confirm the exact run
matches its evidence, check spoken NVIDIA/Nebius attribution, and confirm it
contains no private account configuration. Upload the live clip to a public
YouTube video from the owner's account, then test its URL signed out. No public
upload or final qualifying live video exists yet. An initial local reference
clip is useful for reviewing the explanation while account access is pending.
