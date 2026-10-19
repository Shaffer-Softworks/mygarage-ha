# Publishing to the HACS Default Store

So users can install this integration from HACS **without** adding a custom repository, include the repo in [hacs/default](https://github.com/hacs/default).

## Prerequisites (this repo)

- [x] `hacs.json` in repo root
- [x] GitHub Actions: `hassfest` + `hacs/action` in `.github/workflows/validate.yaml` (no `ignore: brands`; in-repo brand assets must pass)
- [x] `manifest.json` with required keys (no core deps like `httpx` in `requirements`)
- [x] In-repo brand images under `custom_components/mygarage/brand/`
- [x] HTTP via Home Assistant shared `aiohttp` session (`async_get_clientsession`)
- [x] GitHub description + topics set on the repository About box

## Steps

### 1. Brand assets

Ship brand images under `custom_components/mygarage/brand/` so HACS validation passes without `ignore: brands`.

### 2. Repository About settings

- **Description**: `Home Assistant custom integration for self-hosted MyGarage (homelabforge/mygarage) — vehicles, maintenance, fuel, LiveLink.`
- **Topics**: `hacs`, `home-assistant`, `home-assistant-custom-component`, `python`, `mygarage`, `vehicle-maintenance`, `livelink`
- **Issues**: enabled

### 3. Publish a GitHub Release

Create a release (e.g. `v0.1.0`) matching `manifest.json` version, with the `mygarage.zip` asset from the Create release workflow.

### 4. Submit to hacs/default

1. Fork [hacs/default](https://github.com/hacs/default)
2. Branch from `master`
3. Add `"Shaffer-Softworks/mygarage-ha"` to the `integration` JSON array in **alphabetical order**
4. Open a PR from a **personal** account (owner or major contributor)

Official docs: [Include default repositories](https://hacs.xyz/docs/publish/include/).

### 5. After merge

Update the README with the HACS Default badge and default-feed install instructions.
