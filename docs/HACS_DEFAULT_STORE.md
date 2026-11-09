# HACS Default Store

MyGarage is included in the [HACS default integration list](https://github.com/hacs/default/blob/master/integration) as `Shaffer-Softworks/mygarage-ha`.

Users can search for **MyGarage** directly in HACS, download it, restart Home Assistant, and add it from **Settings → Devices & Services**. Adding a custom repository is no longer required.

## Maintaining the listing

- Keep `hacs.json` in the repository root and the integration under `custom_components/mygarage/`.
- Keep the required integration metadata in `manifest.json`, including the version, documentation, issue tracker, and codeowners.
- Keep the in-repo brand images under `custom_components/mygarage/brand/`, including `icon.png`.
- Keep both Hassfest and HACS validation passing in `.github/workflows/validate.yaml`, without ignored checks.
- Keep the GitHub repository public and active, with a description, topics, issues enabled, and an identifiable open-source license.

## Publishing updates

Use the **Create release** workflow to publish a version matching `manifest.json`, with the `mygarage.zip` release asset required by `hacs.json`. The archive must contain the integration files at its root, including `manifest.json` and `brand/`, rather than a nested `custom_components/mygarage/` directory.

Check validation for the release tag and merge the workflow's manifest bump PR so the default branch stays in sync with the published version.

The existing default-list entry covers future releases; a new `hacs/default` submission is not needed for each update.

Official requirements: [HACS default repositories](https://github.com/hacs/documentation/blob/main/source/docs/publish/include.md).
