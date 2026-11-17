import importlib.util
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "spine_inventory.py"
spec = importlib.util.spec_from_file_location("spine_inventory", p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SAMPLE = """2026/11/15 12:00:00 [DISCOVERY] device ski=SECRETDEVICEID type=HeatGenerationSystem entities=2
[DISCOVERY]   entity addr=5:1:1 type=HVACRoom features=[HVAC/server, Setpoint/server]
[DISCOVERY]     feature addr=5:1:1:18 type=Setpoint role=server functions=[setpointDescriptionListData(r), setpointListData(r,w,wp)]
[DISCOVERY]     feature addr=5:1:1:9 type=HVAC role=server functions=[hvacSystemFunctionListData(r,w)]
[DISCOVERY]   usecase actor=HeatGenerator name=configurationOfRoomHeatingTemperature v1.0.0 available=true scenarios=[1,2]
2026/11/15 12:00:01 debug Bearer secret and token=my-secret
"""


class InventoryTests(unittest.TestCase):
    def test_parses_and_removes_identifier(self):
        devices = module.parse(SAMPLE)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["device_type"], "HeatGenerationSystem")
        self.assertEqual(devices[0]["features"][0]["functions"][1]["operations"], ["r", "w", "wp"])
        self.assertEqual(devices[0]["use_cases"][0]["scenarios"], [1, 2])
        dumped = module.markdown(devices)
        self.assertIn("setpointListData", dumped)
        self.assertNotIn("SECRETDEVICEID", dumped)
        self.assertNotIn("my-secret", dumped)

    def test_no_discovery(self):
        self.assertEqual(module.parse("2026/11/15 monitoring recovery: stale"), [])

    def test_multidevice(self):
        self.assertEqual(len(module.parse(SAMPLE + SAMPLE)), 2)

    def test_partial_feature_and_empty_permissions(self):
        d = module.parse("""[DISCOVERY] device ski=X type=Gateway entities=0
[DISCOVERY] feature addr=3:2 type=Foo role=server functions=[a(-), b(rp)]
""")
        self.assertEqual(d[0]["features"][0]["functions"][0]["operations"], [])
        self.assertEqual(d[0]["features"][0]["functions"][1]["operations"], ["rp"])


if __name__ == "__main__":
    unittest.main()
