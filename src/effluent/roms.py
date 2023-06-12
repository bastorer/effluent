"""
The module contains functions for working with ROMS datasets
"""

import numpy as np
import glob


def open_location(file, lat, lon, az):
    """
    Open ROMS dataset at specific location

    The output coordinates are 'time' and 'depth'. Fields are interpolated to the
    desired position, and the depth of each vertical level is computed. Current
    velocities are rotated according to the specified azimuthal orientation.

    :param file: Name of ROMS file(s), or wildcard pattern
    :param lat: Latitude of location
    :param lon: Longitude of location
    :param az: Azimuthal orientation of u velocity (0 is north, 90 is east)
    :return: An xarray.Dataset object
    """

    # Select position
    dset = open_dataset(file, z_rho=True, dens=True)
    dset = interpolate_latlon(dset, lat, lon)

    # Set coordinates
    dset = dset.rename(z_rho_star='depth', ocean_time='time')
    dset = dset.swap_dims({'s_rho': 'depth'})

    # Rotate velocity
    u = compute_azimuthal_vel(dset, az * (np.pi / 180))
    v = compute_azimuthal_vel(dset, (az + 90) * (np.pi / 180))
    dset = dset.assign(u=u, v=v)

    return dset


def open_dataset(file, z_rho=False, dens=False):
    """
    Open ROMS dataset

    Variables are lazily loaded or computed.

    :param file: Name of ROMS file(s), or wildcard pattern
    :param z_rho: True if rho depths should be added (default: False)
    :param dens: True if density should be added (implies z_rho, default: False)
    :return: An xarray.Dataset object
    """
    import xarray as xr

    fnames = sorted(glob.glob(file))
    if len(fnames) == 0:
        raise ValueError(f'No files found: "{fnames}"')

    if len(fnames) == 1:
        dset = xr.open_dataset(fnames[0])
    else:
        dset = xr.open_mfdataset(
            paths=fnames,
            chunks={'ocean_time': 1},
            concat_dim='ocean_time',
            compat='override',
            data_vars='minimal',
            coords='minimal',
            combine='nested',
            join='override',
            combine_attrs='override',
        )

    if z_rho or dens:
        dset = add_zrho(dset)

    if dens:
        dset = add_dens(dset)

    return dset


def add_zrho(dset):
    """
    Add z_rho variable to a ROMS dataset

    :param dset: An xarray.Dataset object representing a ROMS dataset
    :return: A new dataset with z_rho added
    """
    vtrans = dset['Vtransform']

    if vtrans == 1:
        z_rho_star = dset.hc * (dset.s_rho - dset.Cs_r) + dset.Cs_r * dset.h
        z_rho = z_rho_star + dset.zeta * (1 + z_rho_star / dset.h)
    elif vtrans == 2:
        z_rho_0 = (dset.hc * dset.s_rho + dset.Cs_r * dset.h) / (dset.hc + dset.h)
        z_rho_star = z_rho_0 * dset.h
        z_rho = dset.zeta + z_rho_0 * (dset.zeta + dset.h)
    else:
        raise ValueError(f'Unknown Vtransform: {vtrans}')

    return dset.assign_coords(
        z_rho=z_rho.transpose('ocean_time', 's_rho', 'eta_rho', 'xi_rho'),
        z_rho_star=z_rho_star.transpose('s_rho', 'eta_rho', 'xi_rho'),
    )


def add_dens(dset):
    """
    Add variable ``dens`` to a ROMS dataset

    :param dset: An xarray.Dataset object representing a ROMS dataset
    :return: A new dataset with ``dens`` added
    """
    from effluent.eos import roms_rho
    dens = roms_rho(dset.temp, dset.salt, dset.z_rho_star)
    return dset.assign_coords(dens=dens)


def interpolate_latlon(dset, lat, lon):
    """
    Interpolate fields in ROMS dataset

    The function uses bilinear interpolation for regular field variables, and
    unidirectional interpolation (which preserves divergence) for the ``u`` and ``v``
    variables.

    :param dset: An xarray.Dataset object
    :param lat: The latitude
    :param lon: The longitude
    :return: A new dataset, with all variables interpolated to the specified location
    """
    from .numerics import bilin_inv

    lat_rho = dset.lat_rho.values
    lon_rho = dset.lon_rho.values

    y, x = bilin_inv(lat, lon, lat_rho, lon_rho)

    x_min = 0.5
    y_min = 0.5
    x_max = dset.dims['xi_rho'] - 1.5
    y_max = dset.dims['eta_rho'] - 1.5
    x = np.clip(x, x_min, x_max)
    y = np.clip(y, y_min, y_max)

    dset = dset.interp(
        xi_rho=x,
        eta_rho=y,
        xi_u=x - 0.5,
        eta_u=int(y + 0.5),
        xi_v=int(x + 0.5),
        eta_v=y - 0.5,
    )

    return dset


def compute_azimuthal_vel(dset, az):
    """
    Compute directional current velocity

    :param dset: An xarray.Dataset object
    :param az: The direction in which to measure the current
    :return: An xarray.DataArray representing the current velocity
    """

    assert dset.angle.units == "radians"

    u = dset.u
    v = dset.v
    theta = az + np.pi / 2 - dset.angle
    return u * np.cos(theta) + v * np.sin(theta)
