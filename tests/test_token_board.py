"""Token 看板的渲染自检（不需要设备、不需要 Windows）。

验证的是「版式契约」：尺寸、格式、数字缩写、确定性、空数据不崩。
这些一旦破坏，屏上就是溢出或者糊成一团，所以用测试钉住。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demos" / "token-board"
sys.path.insert(0, str(DEMO))
sys.path.insert(0, str(ROOT))

from render import draw_board, fmt_tokens  # noqa: E402  (demos/token-board/render.py)

SAMPLE = {
    "today": {"tokens": 155330000, "cost": 16.67, "messages": 1046},
    "month": {"tokens": 412860000, "cost": 42.31, "messages": 2884},
    "all_time": {"tokens": 1284000000, "cost": 131.77, "messages": 9137},
    "top_models": [
        {"name": "deepseek-v4.1-flash", "tokens": 77620000, "cost": 1.68},
        {"name": "gpt-6.1-sol", "tokens": 49570000, "cost": 14.20},
    ],
}


class TestFormat(unittest.TestCase):
    def test_units(self):
        self.assertEqual(fmt_tokens(155330000), "155.33M")
        self.assertEqual(fmt_tokens(1284000000), "1.28B")
        self.assertEqual(fmt_tokens(1000000), "1M")          # 末尾 0 要削掉
        self.assertEqual(fmt_tokens(2400), "2.4K")
        self.assertEqual(fmt_tokens(0), "0")

    def test_none_is_zero(self):
        self.assertEqual(fmt_tokens(None), "0")


class TestRender(unittest.TestCase):
    def test_size_and_mode(self):
        img = draw_board(SAMPLE)
        self.assertEqual(img.size, (240, 240))
        self.assertEqual(img.mode, "RGB")

    def test_deterministic(self):
        a = draw_board(SAMPLE).tobytes()
        b = draw_board(SAMPLE).tobytes()
        self.assertEqual(a, b, "同一份数据两次渲染必须逐像素相同")

    def test_no_models_does_not_crash(self):
        data = dict(SAMPLE, top_models=[])
        img = draw_board(data)
        self.assertEqual(img.size, (240, 240))

    def test_long_model_name_is_clipped(self):
        data = dict(SAMPLE, top_models=[
            {"name": "a-really-absurdly-long-model-name-that-would-overflow",
             "tokens": 77620000, "cost": 1.68}])
        self.assertEqual(draw_board(data).size, (240, 240))

    def test_zero_values(self):
        data = {"today": {}, "month": {}, "all_time": {}, "top_models": []}
        self.assertEqual(draw_board(data).size, (240, 240))

    def test_custom_size(self):
        self.assertEqual(draw_board(SAMPLE, 320, 240).size, (320, 240))


if __name__ == "__main__":
    unittest.main()
