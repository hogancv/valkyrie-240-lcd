"""协议常量自检 —— 不用接设备就能跑。

    python -m unittest discover -s tests -v

这些断言锁的是「官方日志里的那三个数字」：帧头、整帧长度、几何命令字节。
改坏任何一处，这里先红。
"""

import unittest

from valkyrie_lcd.protocol import (
    FRAME_FOOTER, PIXFMT_YUV422, build_init_sequence, describe,
    frame_header, frame_size, vic_for,
)


class TestFrameGeometry(unittest.TestCase):
    def test_240x240_vic(self):
        self.assertEqual(vic_for(240, 240), 156)

    def test_frame_size_matches_official_log(self):
        # 官方日志：start screen for data size 115216
        self.assertEqual(frame_size(240, 240), 115216)
        self.assertEqual(frame_size(240, 240), 8 + 240 * 240 * 2 + 8)

    def test_header_bytes(self):
        # FF 00 | x/16 | y(BE16) | width/16 | height(BE16)
        self.assertEqual(frame_header(240, 240).hex(" "), "ff 00 00 00 00 0f 00 f0")
        self.assertEqual(frame_header(320, 240).hex(" "), "ff 00 00 00 00 14 00 f0")

    def test_footer(self):
        self.assertEqual(FRAME_FOOTER.hex(" "), "ff c0 00 00 00 00 00 00")


class TestInitSequence(unittest.TestCase):
    def setUp(self):
        self.seq = build_init_sequence(240, 240)

    def test_length(self):
        self.assertEqual(len(self.seq), 76)

    def test_all_payloads_are_8_bytes(self):
        for payload, need_read in self.seq:
            self.assertEqual(len(payload), 8, payload.hex(" "))
            self.assertIsInstance(need_read, bool)

    def test_geometry_commands(self):
        found = {p[:2]: p for p, _ in self.seq if p[0] == 0xA6 and p[1] in (1, 2)}
        # A6 01 [W BE16] [H BE16] [FMT] 00
        self.assertEqual(found[bytes([0xA6, 0x01])].hex(" "),
                         "a6 01 00 f0 00 f0 22 00")
        # A6 02 [VIC] 00 [W BE16] [H BE16]
        self.assertEqual(found[bytes([0xA6, 0x02])].hex(" "),
                         "a6 02 9c 00 00 f0 00 f0")

    def test_pixfmt_is_yuv422(self):
        a601 = [p for p, _ in self.seq if p[:2] == bytes([0xA6, 0x01])][0]
        self.assertEqual(a601[6], PIXFMT_YUV422)

    def test_unknown_size_raises(self):
        with self.assertRaises(ValueError):
            build_init_sequence(111, 222)

    def test_describe(self):
        text = describe(240, 240)
        self.assertIn("VIC=156", text)
        self.assertIn("115216", text)


if __name__ == "__main__":
    unittest.main()
