# VeSync (Eleva 300X/500X)

A drop-in copy of Home Assistant 2026.11.1's built-in **VeSync** integration that adds the
**Levoit Eleva 300X** (`LAP-C341S-WUSZ`, `LAP-C341S-WEU`) and **Eleva 500X** (`LAP-C511S-WUS`)
air purifiers.

It overrides the core `vesync` domain, so your existing VeSync config entry, devices and
entities stay the same. Remove it when upstream support lands.

## How it works

- **Library:** the integration installs [`eyalgal/pyvesync@eleva-support`](https://github.com/eyalgal/pyvesync/tree/eleva-support)
  (`3.5.1.post1`). That is pyvesync 3.5.1 plus these open upstream PRs:
  - [webdjoe/pyvesync#563](https://github.com/webdjoe/pyvesync/pull/563): Eleva 500X support (`VeSyncAirEleva`)
  - [#562](https://github.com/webdjoe/pyvesync/pull/562): light-detection toggle fix
  - [#561](https://github.com/webdjoe/pyvesync/pull/561): timer fix
  - Eleva 300X model codes on the same class, following the data in [#545](https://github.com/webdjoe/pyvesync/issues/545)
- **Integration:** this is core's 2026.11.1 code, plus the entities below. They only appear on devices that report the matching fields, so other VeSync devices are unchanged.

| Platform | Entity | Eleva 300X | Eleva 500X |
| --- | --- | :-: | :-: |
| fan | Power, speed 1–4, presets `auto` / `sleep` | ✔ | ✔ |
| sensor | PM1, PM2.5, PM10, AQI, air quality | ✔ | ✔ |
| sensor | VOC index, NO2 index | | ✔ |
| sensor | Filter / carbon filter / pre-filter lifetime, filter remaining (days) | ✔ | ✔ |
| sensor | Total clean air, auto mode profile (read-only) | ✔ | ✔ |
| switch | Display, child lock, light detection, quiet period | ✔ | ✔ |
| select | Indicator ring (bright / dim), quiet period mode | ✔ | ✔ |
| time | Quiet period start / end | ✔ | ✔ |

## Install (Marketplace, fka HACS)

1. Marketplace (fka HACS) → ⋮ → **Custom repositories** → add `https://github.com/eyalgal/ha-vesync-eleva`, type **Integration**.
2. Download **VeSync (Eleva 300X/500X)**, then restart Home Assistant.
3. Your existing VeSync entry reloads on this code. New Eleva devices appear automatically (or after **Reload**).

To go back to core, remove the repository from Marketplace (fka HACS) and restart.

## Known limitations

- The Eleva cloud status (`getPurifierStatus`) can lag the device by about 3 minutes. Power, mode, fan level and air quality come from the device list (`deviceProp`), which is current within about 15 seconds. Other settings are held at the value you set until the cloud catches up.
- **Auto mode profile** (Daily Comfort / Focused Care / Advanced Care) is read-only: the `setHealthProtect` parameters are still unknown.
- The 300X's fan levels 1–4 follow #546, where the app's "Turbo" is level 4, not a separate mode.

## Development

`scripts/smoke_test.py` builds both Eleva models from captured API payloads (the 300X one is a real response from #545). It checks every entity's value, its translations and its command payloads, and checks that humidifiers get no new entities:

```sh
uv venv -p 3.14 .venv
uv pip install -p .venv homeassistant==2026.11.1 \
  "pyvesync @ https://github.com/eyalgal/pyvesync/releases/download/eleva-3.5.1.post1/pyvesync-3.5.1.post1-py3-none-any.whl"
git clone -b eleva-support https://github.com/eyalgal/pyvesync ../pyvesync
PYVESYNC_TESTS=../pyvesync/src/tests .venv/bin/python scripts/smoke_test.py
```

`custom_components/vesync/translations/en.json` is `strings.json` with HA's `[%key:…]` references resolved. Custom integrations cannot use those references.
