""" Testing vizualization with fvtk
"""
import numpy as np

from dipy.viz import fvtk

from numpy.testing import assert_array_almost_equal, assert_
import numpy.testing as npt


@npt.dec.skipif(not fvtk.have_vtk)
def test_fvtk_functions():

    # Create a renderer
    r = fvtk.ren()

    # Create 2 lines with 2 different colors
    lines = [np.random.rand(10, 3), np.random.rand(20, 3)]
    colors = np.random.rand(2, 3)
    c = fvtk.line(lines, colors)
    fvtk.add(r, c)

    # Create a volume and return a volumetric actor using volumetric rendering
    vol = 100 * np.random.rand(100, 100, 100)
    vol = vol.astype('uint8')
    r = fvtk.ren()
    v = fvtk.volume(vol)
    fvtk.add(r, v)

    # Remove all objects
    fvtk.rm_all(r)

    # Put some text
    l = fvtk.label(r, text='Yes Men')
    fvtk.add(r, l)

    # Show everything
    # fvtk.show(r)


@npt.dec.skipif(not fvtk.have_vtk)
def test_fvtk_ellipsoid():

    evals = np.array([1.4, .35, .35]) * 10 ** (-3)
    evecs = np.eye(3)

    mevals = np.zeros((3, 2, 4, 3))
    mevecs = np.zeros((3, 2, 4, 3, 3))

    mevals[..., :] = evals
    mevecs[..., :, :] = evecs

    from dipy.data import get_sphere

    sphere = get_sphere('symmetric724')
    ren = fvtk.ren()
    fvtk.add(ren, fvtk.tensor(mevals, mevecs, sphere))
    
    fvtk.show(ren)


