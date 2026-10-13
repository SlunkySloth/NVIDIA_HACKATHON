# Third-party components and attribution

The MIT license covers this repository's original application code, fixture
handlers, synthetic inputs, and authored reference patches. It does not relicense
dependencies, provider services, or model weights. Python and JavaScript package
versions are pinned in `requirements.lock` and `apps/web/package-lock.json`;
their distributions contain the applicable licenses.

The live inference provider is Nebius Token Factory. The execution provider is
Token Factory Sandboxes, via `contree-sdk==0.3.6`. Hosting configuration targets
Nebius AI Cloud Compute. Live evidence records exact model and immutable image
IDs; the selected NVIDIA model's terms apply independently of this source license.
No model weights or provider keys are redistributed by this repository.

The web UI uses React, Lucide icons, Vite and TypeScript, with Playwright for
browser verification. Caddy provides HTTPS; Python and Node images provide build
and runtime environments. Review their own licenses when redistributing images.

Optional local demo narration was synthesized with
[eSpeak NG 1.52.0](https://github.com/espeak-ng/espeak-ng/tree/1.52.0), licensed
under GPL-3.0-or-later. Its source is available at that link. The executable and
its voice data are local tools, excluded from this repository and its app images.
The narration text and recorded original application UI are our own work. No
celebrity voice, third-party speech recording, or downloaded music is used.
