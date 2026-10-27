"""Face time: landmarks stay on the face, and aligned eyes land together."""

import unittest

from library.errors import AppError
from library.face_film import align_box, align_eyes
from library.faces import _ARCFACE_DST, _numpy, align_portrait
from library.records import read_face


class FaceFilmTests(unittest.TestCase):
    def test_eyes_land_on_the_same_spot(self):
        np = _numpy()
        size = 640
        scale = (size * 0.62) / 112.0
        offset = (size - 112.0 * scale) / 2.0
        src = np.asarray(_ARCFACE_DST, dtype=np.float64)
        photo = src * 3.0 + np.array([90.0, 50.0])
        image = np.zeros((420, 420, 3), dtype=np.uint8)
        ex, ey = photo[0]
        x = int(round(ex))
        y = int(round(ey))
        image[y - 2 : y + 3, x - 2 : x + 3] = (10, 20, 240)
        out = align_portrait(image, photo, size)
        ix = int(round(src[0, 0] * scale + offset))
        iy = int(round(src[0, 1] * scale + offset))
        patch = out[iy - 3 : iy + 4, ix - 3 : ix + 4, 2]
        self.assertGreater(int(patch.max()), 200)

    def test_box_center_lands_in_the_frame(self):
        np = _numpy()
        image = np.zeros((200, 240, 3), dtype=np.uint8)
        image[90:111, 110:131] = (10, 20, 230)
        out = align_box(image, [100 / 240, 80 / 200, 40 / 240, 40 / 200], 640)
        ix, iy = 320, 320
        patch = out[iy - 4 : iy + 5, ix - 4 : ix + 5, 2]
        self.assertGreater(int(patch.max()), 200)

    def test_a_square_on_the_face_stays_square(self):
        np = _numpy()
        image = np.zeros((400, 200, 3), dtype=np.uint8)
        image[190:210, 90:110] = (0, 0, 255)
        out = align_box(image, [80 / 200, 180 / 400, 40 / 200, 40 / 400], 640)
        ys, xs = np.where(out[:, :, 2] > 200)
        self.assertGreater(len(xs), 10)
        wide = int(xs.max() - xs.min())
        tall = int(ys.max() - ys.min())
        self.assertLess(abs(wide - tall) / max(wide, tall), 0.2)

    def test_eyes_share_one_scale(self):
        np = _numpy()
        image = np.zeros((300, 400, 3), dtype=np.uint8)
        image[148:153, 118:123] = (0, 0, 255)
        image[168:173, 198:203] = (0, 255, 0)
        image[140:160, 155:175] = (255, 0, 0)
        out = align_eyes(image, (120, 150), (200, 170), 640)
        # Left eye lands left of center, right eye the same distance to the right, level.
        left = out[int(640 * 0.42) - 6 : int(640 * 0.42) + 7, 320 - 70 - 8 : 320 - 70 + 9, 2]
        right_row = out[int(640 * 0.42) - 6 : int(640 * 0.42) + 7, 320 + 70 - 8 : 320 + 70 + 9, 1]
        self.assertGreater(int(left.max()), 200)
        self.assertGreater(int(right_row.max()), 200)
        red_y, red_x = np.where(out[:, :, 0] > 200)
        self.assertGreater(len(red_x), 10)
        wide = int(red_x.max() - red_x.min())
        tall = int(red_y.max() - red_y.min())
        self.assertLess(abs(wide - tall) / max(wide, tall), 0.25)

    def test_landmarks_round_trip(self):
        points = [[0.2, 0.3], [0.4, 0.3], [0.3, 0.45], [0.25, 0.55], [0.38, 0.55]]
        face = read_face({"personId": "person_a", "box": [0.1, 0.2, 0.3, 0.4], "landmarks": points})
        self.assertEqual(face["landmarks"], points)

    def test_short_landmarks_rejected(self):
        with self.assertRaises(AppError):
            read_face({"personId": "person_a", "landmarks": [[0.1, 0.2]]})


if __name__ == "__main__":
    unittest.main()
