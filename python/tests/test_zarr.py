# Copyright (c) 2021-2023, NVIDIA CORPORATION. All rights reserved.
# See file LICENSE for terms.


import pytest

cupy = pytest.importorskip("cupy")
zarr = pytest.importorskip("zarr")
kvikio_zarr = pytest.importorskip("kvikio.zarr")
GDSStore = kvikio_zarr.GDSStore


if not kvikio_zarr.supported():
    pytest.skip("requires Zarr v2.15+", allow_module_level=True)


@pytest.fixture
def store(tmp_path):
    """Fixture that creates a GDS Store"""
    cupy.arange(1)  # Making sure that CUDA has been initialized
    return GDSStore(tmp_path / "test-file.zarr")


def test_direct_store_access(store, xp):
    """Test accessing the GDS Store directly"""

    a = xp.arange(5, dtype="u1")
    store["a"] = a
    b = store["a"]

    # Notice, when not using getitems(), GDSStore returns bytes always
    assert isinstance(b, bytes)
    a.data == b


@pytest.mark.parametrize("xp_write", ["numpy", "cupy"])
@pytest.mark.parametrize("xp_read_a", ["numpy", "cupy"])
@pytest.mark.parametrize("xp_read_b", ["numpy", "cupy"])
def test_direct_store_access_getitems(store, xp_write, xp_read_a, xp_read_b):
    """Test accessing the GDS Store directly using getitems()"""

    xp_read_a = pytest.importorskip(xp_read_a)
    xp_read_b = pytest.importorskip(xp_read_b)
    xp_write = pytest.importorskip(xp_write)
    a = xp_write.arange(5, dtype="u1")
    b = a * 2
    store["a"] = a
    store["b"] = b

    res = store.getitems(
        keys=["a", "b"],
        contexts={
            "a": {"meta_array": xp_read_a.empty(())},
            "b": {"meta_array": xp_read_b.empty(())},
        },
    )
    assert isinstance(res["a"], xp_read_a.ndarray)
    assert isinstance(res["b"], xp_read_b.ndarray)
    cupy.testing.assert_array_equal(res["a"], a)
    cupy.testing.assert_array_equal(res["b"], b)


def test_array(store, xp):
    """Test Zarr array"""

    a = xp.arange(100)
    z = zarr.array(a, chunks=10, compressor=None, store=store, meta_array=xp.empty(()))
    assert isinstance(z.meta_array, type(a))
    assert a.shape == z.shape
    assert a.dtype == z.dtype
    assert isinstance(a, type(z[:]))
    cupy.testing.assert_array_equal(a, z[:])


def test_group(store, xp):
    """Test Zarr group"""

    g = zarr.open_group(store, meta_array=xp.empty(()))
    g.ones("data", shape=(10, 11), dtype=int, compressor=None)
    a = g["data"]
    assert a.shape == (10, 11)
    assert a.dtype == int
    assert isinstance(a, zarr.Array)
    assert isinstance(a.meta_array, type(xp.empty(())))
    assert isinstance(a[:], xp.ndarray)
    assert (a[:] == 1).all()


def test_open_array(store, xp):
    """Test Zarr's open_array()"""

    a = xp.arange(10)
    z = zarr.open_array(
        store,
        shape=a.shape,
        dtype=a.dtype,
        chunks=(10,),
        compressor=None,
        meta_array=xp.empty(()),
    )
    z[:] = a
    assert a.shape == z.shape
    assert a.dtype == z.dtype
    assert isinstance(a, type(z[:]))
    cupy.testing.assert_array_equal(a, z[:])


@pytest.mark.parametrize("inline_array", [True, False])
def test_dask_read(store, xp, inline_array):
    """Test Zarr read in Dask"""

    da = pytest.importorskip("dask.array")
    a = xp.arange(100)
    z = zarr.array(a, chunks=10, compressor=None, store=store, meta_array=xp.empty(()))
    d = da.from_zarr(z, inline_array=inline_array)
    d += 1
    cupy.testing.assert_array_equal(a + 1, d.compute())


def test_dask_write(store, xp):
    """Test Zarr write in Dask"""

    da = pytest.importorskip("dask.array")

    # Write dask array to disk using Zarr
    a = xp.arange(100)
    d = da.from_array(a, chunks=10)
    da.to_zarr(d, store, compressor=None, meta_array=xp.empty(()))

    # Validate the written Zarr array
    z = zarr.open_array(store)
    cupy.testing.assert_array_equal(a, z[:])
