"""Smoke test the custom vesync integration against simulated devices.

Needs a venv with homeassistant and the forked pyvesync, and PYVESYNC_TESTS
pointing at the fork's src/tests directory (for its device fixtures):

    PYVESYNC_TESTS=../pyvesync/src/tests .venv/bin/python scripts/smoke_test.py
"""

import asyncio
from datetime import time as dtime
import json
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, os.environ["PYVESYNC_TESTS"])

from call_json import ALL_DEVICE_MAP_DICT, DeviceList  # noqa: E402
from call_json_humidifiers import DETAILS_RESPONSES as HUMIDIFIER_DETAILS  # noqa: E402
from call_json_purifiers import DETAILS_RESPONSES as PURIFIER_DETAILS  # noqa: E402
from defaults import TestDefaults  # noqa: E402

from pyvesync import VeSync  # noqa: E402
from pyvesync.models.vesync_models import ResponseDeviceDetailsModel  # noqa: E402

from custom_components.vesync import fan, select, sensor, switch  # noqa: E402
from custom_components.vesync import time as vs_time  # noqa: E402

TRANSLATIONS = json.loads(
    (ROOT / "custom_components/vesync/translations/en.json").read_text()
)["entity"]
DEVICE_CLASS_NAMED = {"pm1", "pm10", "pm25", "aqi", "humidity", "temperature"}

# Real Eleva 300X getPurifierStatus result from webdjoe/pyvesync#545.
ELEVA_300X_STATUS = {
    "powerSwitch": 1, "filterLifePercent": 94, "filterRemainDay": 676,
    "carbonFilterLifePercent": 83, "carbonFilterResetDate": 0,
    "preFilterLifePercent": 0, "preFilterLastCleanDate": 1788713444,
    "curFilterCert": 1, "authenticatedTsInSec": 1788712844, "workMode": "manual",
    "manualSpeedLevel": 1, "fanSpeedLevel": 1, "AQLevel": 1, "PM25": 1, "PM1": 1,
    "PM10": 1, "AQI": 12, "screenState": 0, "childLockSwitch": 0,
    "screenSwitch": 0, "lightDetectionSwitch": 1, "environmentLightState": 0,
    "resetFilterDate": 0, "totalCleanAir": 100720, "timerRemain": 0,
    "autoPreference": {"autoPreferenceType": "default"}, "scheduleCount": 1,
    "errorCode": 0, "errorCodes": [], "group": 1, "standbyGuardSwitch": 0,
    "manualGuardSwitch": 0, "sleepGuardSwitch": 0,
    "quietPeriod": {"quietPeriodSwitch": 0, "modeIdx": 0, "startTime": 79200,
                    "endTime": 21600},
    "dataScheduleRules": 1,
    "sensorInfos": [{"sensorId": "##", "sensorType": 2, "inUse": True, "PM1": 1,
                     "PM25": 1, "PM10": 1, "AQI": 12, "AQLevel": 1}],
    "supportTrendType": ["AQI", "PM25", "PM1", "PM10"], "aqiLightMode": 1,
}
ELEVA_300X_PROP = {
    "workMode": "manual", "fanSpeedLevel": 2, "manualSpeedLevel": 2, "PM1": 1,
    "AQI": 12, "PM25": 1, "powerSwitch": 1, "healthProtectMode": 1, "AQLevel": 1,
    "connectionStatus": "online", "PM10": 3,
}
NEW_KEYS = {
    "carbon_filter_life", "pre_filter_life", "filter_remaining_days",
    "total_clean_air", "aqi", "voc", "no2", "auto_profile", "light_detection",
    "quiet_period", "indicator_ring", "quiet_period_mode", "quiet_period_start",
    "quiet_period_end",
}


def bypass(result):
    return {"code": 0, "msg": "ok", "result": {"code": 0, "result": result}}


def device_list(*items):
    return ({"code": 0, "msg": "ok", "result": {"list": list(items)}}, 200)


def make_device(manager, setup_entry, device_type):
    manager.devices.clear()
    config = DeviceList.device_list_item(ALL_DEVICE_MAP_DICT[setup_entry])
    config["deviceType"] = device_type
    manager.devices.add_device_from_model(
        ResponseDeviceDetailsModel.from_dict(config), manager
    )
    return next(iter(manager.devices))


def entities(device):
    coord = MagicMock()
    out = []
    for desc in sensor.SENSORS:
        if desc.exists_fn(device):
            ent = sensor.VeSyncSensorEntity(device, desc, coord)
            out.append(("sensor", desc.translation_key or desc.key, ent.native_value))
    for desc in switch.SENSOR_DESCRIPTIONS:
        if desc.exists_fn(device):
            ent = switch.VeSyncSwitchEntity(device, desc, coord)
            out.append(("switch", desc.translation_key or desc.key, ent.is_on))
    for desc in select.SELECT_DESCRIPTIONS:
        if desc.exists_fn(device):
            ent = select.VeSyncSelectEntity(device, desc, coord)
            assert ent.current_option in desc.options, (desc.key, ent.current_option)
            out.append(("select", desc.translation_key, ent.current_option))
    for desc in vs_time.TIME_DESCRIPTIONS:
        if hasattr(device, "set_quiet_period") and getattr(
            device.state, desc.attr, None
        ) is not None:
            ent = vs_time.VeSyncTimeEntity(device, desc, coord)
            out.append(("time", desc.translation_key, ent.native_value))
    if fan.is_purifier(device):
        ent = fan.VeSyncFanHA(device, coord)
        out.append(("fan", "presets", ent.preset_modes))
        out.append(("fan", "percentage", ent.percentage))
    for platform, key, _ in out:
        if platform == "fan" or key in DEVICE_CLASS_NAMED:
            continue
        assert key in TRANSLATIONS.get(platform, {}), f"missing translation {platform}.{key}"
    return out


def show(name, ents):
    print(f"{name}:")
    for ent in ents:
        print("   ", ent)


async def main():
    with patch("pyvesync.vesync.VeSync.async_call_api") as api:
        manager = VeSync(TestDefaults.email, TestDefaults.password)
        manager.auth._token = TestDefaults.token
        manager.auth._account_id = TestDefaults.account_id
        manager.enabled = True

        dev300 = make_device(manager, "LAP-C341S", "LAP-C341S-WUSZ")
        assert type(dev300).__name__ == "VeSyncAirEleva", type(dev300)
        api.side_effect = [
            device_list({"cid": dev300.cid, "deviceProp": ELEVA_300X_PROP}),
            (bypass(ELEVA_300X_STATUS), 200),
        ]
        await dev300.get_details()
        ents = entities(dev300)
        show("Eleva 300X (LAP-C341S-WUSZ)", ents)
        values = {(p, k): v for p, k, v in ents}
        assert values[("sensor", "carbon_filter_life")] == 83
        assert values[("sensor", "pre_filter_life")] == 0
        assert values[("sensor", "filter_life")] == 94
        assert values[("sensor", "aqi")] == 12
        assert values[("sensor", "auto_profile")] == "daily_comfort"
        assert values[("switch", "light_detection")] is True
        assert values[("time", "quiet_period_start")] == dtime(22, 0)
        assert values[("fan", "percentage")] == 50  # deviceProp level 2 of 4
        assert ("sensor", "voc") not in values

        api.side_effect = None
        api.return_value = (bypass({}), 200)

        def sent():
            payload = api.call_args.args[2].payload
            return {"method": payload.method, "data": payload.data}

        ring = next(d for d in select.SELECT_DESCRIPTIONS if d.key == "indicator_ring")
        assert await ring.select_option_fn(dev300, "dim")
        assert sent() == {"method": "setAqiLight", "data": {"mode": 2}}
        assert await vs_time.TIME_DESCRIPTIONS[1].set_fn(dev300, 7 * 3600)
        assert sent()["data"] == {
            "quietPeriodSwitch": 0, "modeIdx": 0, "startTime": 79200, "endTime": 25200
        }
        light = next(d for d in switch.SENSOR_DESCRIPTIONS if d.key == "light_detection")
        assert await light.off_fn(dev300)
        assert sent()["data"] == {"lightDetectionSwitch": 0}
        assert dev300.state.light_detection_switch == "off"

        dev500 = make_device(manager, "LAP-C511S", "LAP-C511S-WUS")
        manager._device_props = None  # drop the 10 s deviceProp reuse window
        api.side_effect = [device_list(), (PURIFIER_DETAILS["LAP-C511S"], 200)]
        await dev500.get_details()
        ents = entities(dev500)
        show("Eleva 500X (LAP-C511S-WUS)", ents)
        keys = {k for _, k, _ in ents}
        assert {"voc", "no2", "carbon_filter_life", "quiet_period"} <= keys

        for dev_type in ("Dual200S", "LUH-O451S-WUS"):
            hum = make_device(manager, dev_type, dev_type)
            api.side_effect = [(HUMIDIFIER_DETAILS[dev_type], 200)]
            await hum.get_details()
            hkeys = {k for _, k, _ in entities(hum)}
            assert not hkeys & NEW_KEYS, (dev_type, hkeys & NEW_KEYS)
            print(f"{dev_type}: {sorted(hkeys)}")
    print("OK")


asyncio.run(main())
