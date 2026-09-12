# HACS submission checklist

Use this checklist before publishing the repository and submitting to HACS.

## 1. Create the GitHub repository

1. Create a **public** repository on GitHub (this project uses `cesme/nws_forecast`).
2. Push this project to the repository.
3. Set a repository **description**, for example:
   `Home Assistant integration for U.S. National Weather Service forecast and observation data`
4. Add repository **topics** (required for HACS validation). On GitHub:
   1. Open your repo main page (`https://github.com/cesme/nws_forecast`)
   2. Make sure you are on the **Code** tab (not Settings)
   3. In the right sidebar, find **About**
   4. Click the **gear icon** next to "About"
   5. In the dialog, add topics such as:
      `home-assistant`, `hacs`, `homeassistant`, `weather`, `nws`, `integration`
   6. Click **Save changes**

   If you do not see **About**, add a short description in that same gear dialog first.

   Or from a terminal (if GitHub CLI is installed):

   ```bash
   gh repo edit cesme/nws_forecast --add-topic home-assistant --add-topic hacs --add-topic homeassistant --add-topic weather --add-topic nws --add-topic integration
   ```
5. Ensure **Issues** are enabled.

## 2. Update placeholder URLs and ownership

If your GitHub username or repository name is not `cesme/nws_forecast`, update these files:

- `custom_components/nws_forecast/manifest.json`
  - `codeowners`
  - `documentation`
  - `issue_tracker`
- `README.md` (badges, HACS custom repo URL, links)
- `LICENSE` (copyright name, if needed)

## 3. Validate with GitHub Actions

After pushing to GitHub:

1. Open **Actions** in your repository.
2. Confirm the **Validate** workflow passes:
   - Hassfest validation
   - HACS validation

Fix any failures before continuing.

## 4. Register brand assets

Integration icons come **only** from the [home-assistant/brands](https://github.com/home-assistant/brands)
repository. Home Assistant does not read an icon out of the `custom_components` folder, so brands is
both what gives the integration an icon in the HA UI and a requirement for the HACS default store.

Submit a pull request to brands adding:

```text
custom_integrations/nws_forecast/icon.png      256x256 PNG (required)
custom_integrations/nws_forecast/icon@2x.png   512x512 PNG (required)
custom_integrations/nws_forecast/logo.png      optional
```

Correctly sized files are prepared in `../brand-assets/custom_integrations/nws_forecast/`
(outside this repository), alongside the 1024x1024 master.

## 5. Create a GitHub release

1. Tag a release, for example `v1.0.0`.
2. Publish a **GitHub Release** (not just a tag).
3. HACS will then offer release versions to users.

## 6. Publish to HACS

### Custom repository (fastest way to share)

Users can add your repo manually in HACS:

- **Settings → Devices & Services → HACS → Integrations → Custom repositories**
- URL: `https://github.com/cesme/nws_forecast`
- Category: **Integration**

### Default HACS store (optional, review required)

To be included in the default HACS integration list:

1. Complete all steps above.
2. Ensure GitHub Actions pass without `ignore` overrides.
3. Open an issue using the HACS default repository template:
   [Submit integration to default store](https://github.com/hacs/default/issues/new?template=integration.yml)
4. Follow the review process documented at [hacs.xyz/docs/publish/include](https://www.hacs.xyz/docs/publish/include/).

## 7. Final manual test

On a real Home Assistant instance:

1. Install via HACS or manual copy.
2. Restart Home Assistant.
3. Add integration with a US zip code (for example `80304`).
4. Confirm the weather entity updates and forecasts appear on a weather card.
5. Check logs for errors under **Settings → System → Logs**.

## Repository structure reference

```text
.github/workflows/validate.yml
.github/ISSUE_TEMPLATE/
custom_components/nws_forecast/
hacs.json
LICENSE
README.md
```
