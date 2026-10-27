"""The 112 face crop must sample the landmarks, not the corner of the photo."""

from __future__ import annotations

import unittest

import numpy as np

from library.faces import _ARCFACE_DST, _affine_112, _similarity_matrix


class FaceAlignTests(unittest.TestCase):
    def test_template_maps_onto_the_landmarks(self) -> None:
        template = np.asarray(_ARCFACE_DST, dtype=np.float64)
        landmarks = template * 3.0 + np.array([120.0, 80.0])
        mat = _similarity_matrix(template, landmarks)
        got = np.zeros_like(landmarks)
        got[:, 0] = mat[0, 0] * template[:, 0] + mat[0, 1] * template[:, 1] + mat[0, 2]
        got[:, 1] = mat[1, 0] * template[:, 0] + mat[1, 1] * template[:, 1] + mat[1, 2]
        self.assertLess(float(np.abs(got - landmarks).max()), 0.5)

    def test_crop_reads_the_eye_not_the_corner(self) -> None:
        template = np.asarray(_ARCFACE_DST, dtype=np.float64)
        landmarks = template * 2.0 + np.array([40.0, 30.0])
        image = np.zeros((400, 400, 3), dtype=np.uint8)
        image[0, 0] = (1, 2, 3)
        eye_x, eye_y = (int(round(v)) for v in landmarks[0])
        image[eye_y - 2 : eye_y + 3, eye_x - 2 : eye_x + 3] = (10, 20, 240)
        crop = _affine_112(image, landmarks)
        dst_x, dst_y = template[0]
        pixel = crop[int(round(dst_y)), int(round(dst_x))]
        self.assertGreater(int(pixel[2]), 200)
        self.assertFalse(np.array_equal(pixel, image[0, 0]))


if __name__ == "__main__":
    unittest.main()
