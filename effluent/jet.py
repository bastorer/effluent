import xarray as xr
import numpy as np


def pipe_discharge():
    """Simulate a pipe discharge and return a description of the jet"""
    return jet(None, None)


def pipe_discharge_single_timestep(
        dt, t, m, c, rho, u, v, w, h, b, x, y, z, ua, va, rho_a):
    """
    :param dt: Time step length (s)
    :param t: Elapsed time since start of simulation
    :param m: Mass of element (kg)
    :param c: Element tracer concentration
    :param rho: Element density
    :param u: Element velocity in x direction
    :param v: Element velocity in y direction
    :param w: Element velocity in z direction
    :param h: Thickness
    :param b: Radius
    :param x: X position
    :param y: Y position
    :param z: Z position
    :param ua: Ambient velocity in x direction
    :param va: Ambient velocity in y direction
    :param rho_a: Ambient density
    :return:
    """
    wa = 0  # Ambient vertical velocity
    g = 9.81  # Acceleration of gravity

    t_new = t + dt

    # Compute entrainment
    # TODO: Replace this simplified model with a more complete one
    alpha_s = np.sqrt(2) * 0.057
    vel = np.sqrt(u * u + v * v + w * w)
    delta_u = vel - np.dot([ua, va, wa], [u, v, w]) / vel  # Velocity difference in jet direction
    dm = 2 * np.pi * alpha_s * b * h * delta_u * dt
    m_new = m + dm  # TODO: Trenger vi m?
    # Svar: Nei. Vi trenger b, og kan alltid regne ut m fra b når vi trenger det.

    # Inmixing
    rho_new = (m * rho + dm * rho_a) / m_new
    c_new = m * c / m_new  # TODO: Gir det mening å ha en variabel med konsentrasjon?
    # Svar: Nei. Denne er redundant, og ekvivalent med m_init / m_new.
    u_new = (m * u + dm * ua) / m_new
    v_new = (m * v + dm * va) / m_new

    # Vertical momentum
    w_new = (m * w + m_new * ((rho_new - rho_a) / rho_new) * g * dt)
    vel_new = np.sqrt(u_new * u_new + v_new * v_new + w_new * w_new)

    # Thickness/radius
    h_new = (vel_new / vel) * h  # TODO: Gir det mening å ha en variabel med tykkelse?
    # Svar: Nei. Vi kan erstatte "vel" med initialhastighet, og "h" med en vilkårlig tykkelse, f.eks. 1.
    b_new = np.sqrt(m_new / (rho_new * np.pi * h_new))

    # Location
    x_new = x + u_new * dt
    y_new = y + v_new * dt
    z_new = z + w_new * dt

    return (
        t_new, m_new, c_new, rho_new, u_new, v_new, w_new, h_new, b_new, x_new,
        y_new, z_new,
    )


def jet(time, density):
    return xr.Dataset(
        data_vars=dict(
            density=xr.Variable(
                dims='time',
                data=[],
                attrs=dict(),
            ),
        ),
        coords=dict(
            time=xr.Variable(
                dims='time',
                data=[],
                attrs=dict(),
            ),
        ),
    )
