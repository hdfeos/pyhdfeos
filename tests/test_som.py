import os
import unittest

import numpy as np

from pyhdfeos import GridFile
from pyhdfeos.lib import he4

from . import fixtures

def print_kij(block, i, j):
    R2D = 57.2957795131
    somx, somy = misr.inv(block+1, i, j)
    lon, lat = som.inv(somx, somy)
    lon *= R2D
    lat *= R2D
    print("({0} {1} {2}):  {3:.3f} {4:.3f}".format(block, i, j, lat, lon))

@unittest.skipIf('HDFEOS_ZOO_DIR' not in os.environ,
                 'HDFEOS_ZOO_DIR environment variable not set.')
class TestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        cls.som_file = fixtures.test_file_path(file)

    def test_point(self):
        """
        retrieve a single point from SOM grid.
        """
        gdf = GridFile(self.som_file)

    def test_ellipsis_complete_grid(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        lat, lon = gdf.grids['GeometricParameters'][...]
        self.assertEqual(lat.shape, (180, 8, 32))

    def test_colon_complete_grid(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        lat, lon = gdf.grids['GeometricParameters'][:]
        self.assertEqual(lat.shape, (180, 8, 32))

    def test_ellipsis_1D(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        lat, lon = gdf.grids['GeometricParameters'][..., 0, 0]
        self.assertEqual(lat.shape, (180,))

        lat, lon = gdf.grids['GeometricParameters'][0, ..., 0]
        self.assertEqual(lat.shape, (8,))

        lat, lon = gdf.grids['GeometricParameters'][0, 0, ...]
        self.assertEqual(lat.shape, (32,))

    def test_colon_1D(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        lat, lon = gdf.grids['GeometricParameters'][:, 0, 0]
        self.assertEqual(lat.shape, (180,))

        lat, lon = gdf.grids['GeometricParameters'][0, :, 0]
        self.assertEqual(lat.shape, (8,))

        lat, lon = gdf.grids['GeometricParameters'][0, 0, :]
        self.assertEqual(lat.shape, (32,))

    def test_first_point_first_block(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        lat, lon = gdf.grids['BlueBand'][0, 0, 0]
        np.testing.assert_almost_equal(lat, 66.226321, 5)
        np.testing.assert_almost_equal(lon, -68.775228, 5)

    def test_points_last_block_subset(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        # upper left corner
        lat, lon = gdf.grids['BlueBand'][179, 0, 0]
        np.testing.assert_almost_equal(lat, -65.731, 3)
        np.testing.assert_almost_equal(lon, -46.159, 3)

        # upper right corner
        lat, lon = gdf.grids['BlueBand'][179, 0, 511]
        np.testing.assert_almost_equal(lat, -67.423, 3)
        np.testing.assert_almost_equal(lon, -58.112, 3)

        # lower left corner
        lat, lon = gdf.grids['BlueBand'][179, 127, 0]
        np.testing.assert_almost_equal(lat, -64.591, 3)
        np.testing.assert_almost_equal(lon, -47.390, 3)

        # lower right corner
        lat, lon = gdf.grids['BlueBand'][179, 127, 511]
        np.testing.assert_almost_equal(lat, -66.207, 3)
        np.testing.assert_almost_equal(lon, -58.865, 3)

    def test_square_last_block(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        lat, lon = gdf.grids['BlueBand'][179, 0:2, 0:2]

        expected = np.array([[-65.731, -65.735], [-65.722, -65.726]])
        np.testing.assert_almost_equal(lat, expected, 3)

        expected = np.array([[-46.159, -46.181], [-46.170, -46.191]])
        np.testing.assert_almost_equal(lon, expected, 3)

    def test_last_block_subset(self):
        file = 'MISR_AM1_GRP_ELLIPSOID_GM_P117_O058421_BA_F03_0024.hdf'
        som_file = fixtures.test_file_path(file)
        gdf = GridFile(som_file)

        lat, lon = gdf.grids['BlueBand'][179, :, :]
        self.assertEqual(lat.shape, (128, 512))

        # First point of last block.
        np.testing.assert_almost_equal(lat[0, 0], -65.731, 3)
        np.testing.assert_almost_equal(lon[0, 0], -46.159, 3)

        # 2nd point of block 0
        np.testing.assert_almost_equal(lat[0, 1], -65.735, 3)
        np.testing.assert_almost_equal(lon[0, 1], -46.181, 3)

        # last point of line 1
        np.testing.assert_almost_equal(lat[0, -1], -67.423, 3)
        np.testing.assert_almost_equal(lon[0, -1], -58.112, 3)

        # last point of first block
        np.testing.assert_almost_equal(lat[-1, -1], -66.207, 3)
        np.testing.assert_almost_equal(lon[-1, -1], -58.865, 3)
