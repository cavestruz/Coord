# Copyright (c) 2013-2017 LSST Dark Energy Science Collaboration (DESC)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""@file celestial.py
The CelestialCoord class describing coordinates on the celestial sphere.
"""

import numpy as np
import math
import datetime

from .angle import Angle, _Angle, DMS_Angle
from .angleunit import radians, degrees, arcsec

class CelestialCoord(object):
    """This class defines a position on the celestial sphere, normally given by two angles,
    `ra` and `dec`.

    This class is used to perform various calculations in spherical coordinates, such
    as finding the angular distance between two points in the sky, calculating the angles in
    spherical triangles, projecting from sky coordinates onto a Euclidean tangent plane, etc.

    Initialization
    --------------

    A `CelestialCoord` object is constructed from the right ascension and declination::

        >>> c = coord.CelestialCoord(ra, dec)

    where ra and dec must be `coord.Angle` instances.

    Attributes
    ----------

    After construction, you can access the ra and dec values as read-only attributes::

        >>> ra = c.ra
        >>> dec = c.dec

    Sperical Geometry
    -----------------

    The basic spherical geometry operations are available to work with spherical triangles

    For three coordinates cA, cB, cC making a spherical triangle, one can calculate the
    sides and angles via::

        >>> a = cB.distanceTo(cC)
        >>> b = cC.distanceTo(cA)
        >>> c = cA.distanceTo(cB)
        >>> A = cA.angleBetween(cB, cC)
        >>> B = cA.angleBetween(cC, cA)
        >>> C = cA.angleBetween(cA, cB)

    All of these return values are coord.Angle instances.

    Projections
    -----------

    Local tangent plane projections of an area of the sky can be performed using the project
    method::

        >>> u, v = center.project(sky_coord)

    and back::

        >>> sky_coord = center.deproject(u,v)

    where u,v are Angles and cente, sky_coord are CelestialCoords.
    """
    def __init__(self, ra, dec):
        """
        :param ra:       The right ascension in radians.  Must be an Angle instance.
        :param dec:      The declination in radian.  Must be an Angle instance.
        """
        if not isinstance(ra, Angle):
            raise TypeError("ra must be a coord.Angle")
        if not isinstance(dec, Angle):
            raise TypeError("dec must be a coord.Angle")
        self._ra = ra.wrap()
        if dec/degrees > 90. or dec/degrees < -90.:
            raise ValueError("dec must be between -90 deg and +90 deg.")
        self._dec = dec
        self._x = None  # Indicate that x,y,z are not set yet.

    def get_xyz(self):
        """Get the (x,y,z) coordinates on the unit sphere corresponding to this (RA, Dec).

        :returns: a tuple (x,y,z)
        """
        self._set_aux()
        return self._x, self._y, self._z

    @classmethod
    def from_xyz(cls, x, y, z):
        """Construct a CelestialCoord from a given (x,y,z) position in three dimensions.

        The 3D (x,y,z) position does not need to fall on the unit sphere.

        :returns: a CelestialCoord instance
        """
        norm = np.sqrt(x*x + y*y + z*z)
        if norm == 0.:
            raise ValueError("CelestialCoord for position (0,0,0) is undefined.")
        ret = cls.__new__(cls)
        ret._ra = np.arctan2(y, x) * radians
        ret._dec = np.arctan2(z, np.sqrt(x*x + y*y)) * radians
        ret._x = x/norm
        ret._y = y/norm
        ret._z = z/norm
        return ret

    @property
    def ra(self):
         return self._ra

    @property
    def dec(self): return self._dec

    def _set_aux(self):
        if self._x is None:
            self._sindec, self._cosdec = self._dec.sincos()
            self._sinra, self._cosra = self._ra.sincos()
            self._x = self._cosdec * self._cosra
            self._y = self._cosdec * self._sinra
            self._z = self._sindec

    def distanceTo(self, other):
        """Returns the great circle distance between this coord and another one.
        The return value is an Angle object
        """
        # The easiest way to do this in a way that is stable for small separations
        # is to calculate the (x,y,z) position on the unit sphere corresponding to each
        # coordinate position.
        #
        # x = cos(dec) cos(ra)
        # y = cos(dec) sin(ra)
        # z = sin(dec)

        self._set_aux()
        other._set_aux()

        # The the direct distance between the two points is
        #
        # d^2 = (x1-x2)^2 + (y1-y2)^2 + (z1-z2)^2

        dsq = (self._x-other._x)**2 + (self._y-other._y)**2 + (self._z-other._z)**2

        # This direct distance can then be converted to a great circle distance via
        #
        # sin(theta/2) = d/2

        theta = 2. * math.asin(0.5 * math.sqrt(dsq))
        return _Angle(theta)

    def angleBetween(self, coord1, coord2):
        """Find the open angle at the location of the current coord between `coord1` and `coord2`.

        Note that this returns a signed angle.  The angle is positive if the sweep direction from
        coord1 to coord2 is counter-clockwise (as observed from Earth).  It is negative if
        the direction is clockwise.
        """
        # Call A = coord1, B = coord2, C = self
        # Then we are looking for the angle ACB.
        # If we treat each coord as a (x,y,z) vector, then we can use the following spherical
        # trig identities:
        #
        # (A x C) . B = sina sinb sinC
        # (A x C) . (B x C) = sina sinb cosC
        #
        # Then we can just use atan2 to find C, and atan2 automatically gets the sign right.
        # And we only need 1 trig call, assuming that x,y,z are already set up, which is often
        # the case.

        self._set_aux()
        coord1._set_aux()
        coord2._set_aux()

        AxC = ( coord1._y * self._z - coord1._z * self._y ,
                coord1._z * self._x - coord1._x * self._z ,
                coord1._x * self._y - coord1._y * self._x )
        BxC = ( coord2._y * self._z - coord2._z * self._y ,
                coord2._z * self._x - coord2._x * self._z ,
                coord2._x * self._y - coord2._y * self._x )
        sinC = AxC[0] * coord2._x + AxC[1] * coord2._y + AxC[2] * coord2._z
        cosC = AxC[0] * BxC[0] + AxC[1] * BxC[1] + AxC[2] * BxC[2]
        C = math.atan2(sinC, cosC)
        return _Angle(C)

    def area(self, coord1, coord2):
        """Find the area of the spherical triangle defined by the current coord, `coord1`,
        and `coord2`, returning the area in steradians.
        """
        # The area of a spherical triangle is defined by the "spherical excess", E.
        # There are several formulae for E:
        #    (cf. http://en.wikipedia.org/wiki/Spherical_trigonometry#Area_and_spherical_excess)
        #
        # E = A + B + C - pi
        # tan(E/4) = sqrt(tan(s/2) tan((s-a)/2) tan((s-b)/2) tan((s-c)/2)
        # tan(E/2) = tan(a/2) tan(b/2) sin(C) / (1 + tan(a/2) tan(b/2) cos(C))
        #
        # We use the last formula, which is stable both for small triangles and ones that are
        # nearly degenerate (which the middle formula may have trouble with).
        #
        # Furthermore, we can use some of the math for angleBetween and distanceTo to simplify
        # this further:
        #
        # In angleBetween, we have formulae for sina sinb sinC and sina sinb cosC.
        # In distanceTo, we have formulae for sin(a/2) and sin(b/2).
        #
        # Define: F = sina sinb sinC
        #         G = sina sinb cosC
        #         da = 2 sin(a/2)
        #         db = 2 sin(b/2)
        #
        # tan(E/2) = sin(a/2) sin(b/2) sin(C) / (cos(a/2) cos(b/2) + sin(a/2) sin(b/2) cos(C))
        #          = sin(a) sin(b) sin(C) / (4 cos(a/2)^2 cos(b/2)^2 + sin(a) sin(b) cos(C))
        #          = F / (4 (1-sin(a/2)^2) (1-sin(b/2)^2) + G)
        #          = F / (4-da^2) (4-db^2)/4 + G)

        self._set_aux()
        coord1._set_aux()
        coord2._set_aux()

        AxC = ( coord1._y * self._z - coord1._z * self._y ,
                coord1._z * self._x - coord1._x * self._z ,
                coord1._x * self._y - coord1._y * self._x )
        BxC = ( coord2._y * self._z - coord2._z * self._y ,
                coord2._z * self._x - coord2._x * self._z ,
                coord2._x * self._y - coord2._y * self._x )
        F = AxC[0] * coord2._x + AxC[1] * coord2._y + AxC[2] * coord2._z
        G = AxC[0] * BxC[0] + AxC[1] * BxC[1] + AxC[2] * BxC[2]
        dasq = (self._x-coord1._x)**2 + (self._y-coord1._y)**2 + (self._z-coord1._z)**2
        dbsq = (self._x-coord2._x)**2 + (self._y-coord2._y)**2 + (self._z-coord2._z)**2

        tanEo2 = F / ( 0.25 * (4.-dasq) * (4.-dbsq) + G)
        E = 2. * math.atan( abs(tanEo2) )
        return E

    _valid_projections = [None, 'gnomonic', 'stereographic', 'lambert', 'postel']

    def project(self, other, projection=None):
        """Use the currect coord as the center point of a tangent plane projection to project
        the `other` coordinate onto that plane.

        This function return a tuple (u,v) in the Euclidean coordinate system defined by
        a tangent plane projection around the current coordinate, with +v pointing north and
        +u pointing west. (i.e. to the right on the sky if +v is up.)

        There are currently four options for the projection, which you can specify with the
        optional `projection` keyword argument:

            'gnomonic' [default] uses a gnomonic projection (i.e. a projection from the center of
                    the sphere, which has the property that all great circles become straight
                    lines.  For more information, see
                    http://mathworld.wolfram.com/GnomonicProjection.html
                    This is the usual TAN projection used by most FITS images.
            'stereographic' uses a stereographic proejection, which preserves angles, but
                    not area.  For more information, see
                    http://mathworld.wolfram.com/StereographicProjection.html
            'lambert' uses a Lambert azimuthal projection, which preserves area, but not angles.
                    For more information, see
                    http://mathworld.wolfram.com/LambertAzimuthalEqual-AreaProjection.html
            'postel' uses a Postel equidistant proejection, which preserves distances from
                    the projection point, but not area or angles.  For more information, see
                    http://mathworld.wolfram.com/AzimuthalEquidistantProjection.html

        The distance or angle errors increase with distance from the projection point of course.

        :returns: (u,v) as Angle instances
        """
        if projection not in CelestialCoord._valid_projections:
            raise ValueError('Unknown projection ' + projection)

        self._set_aux()
        other._set_aux()

        # The core calculation is done in a helper function:
        u, v = self._project_core(other._cosra, other._sinra, other._cosdec, other._sindec,
                                  projection)

        return u * arcsec, v * arcsec

    def _project_core(self, cosra, sinra, cosdec, sindec, projection):
        # The equations are given at the above mathworld websites.  They are the same except
        # for the definition of k:
        #
        # x = k cos(dec) sin(ra-ra0)
        # y = k ( cos(dec0) sin(dec) - sin(dec0) cos(dec) cos(ra-ra0) )
        #
        # Lambert:
        #   k = sqrt( 2  / ( 1 + cos(c) ) )
        # Stereographic:
        #   k = 2 / ( 1 + cos(c) )
        # Gnomonic:
        #   k = 1 / cos(c)
        # Postel:
        #   k = c / sin(c)
        # where cos(c) = sin(dec0) sin(dec) + cos(dec0) cos(dec) cos(ra-ra0)

        # cos(dra) = cos(ra-ra0) = cos(ra0) cos(ra) + sin(ra0) sin(ra)
        cosdra = self._cosra * cosra
        cosdra += self._sinra * sinra

        # sin(dra) = -sin(ra - ra0)
        # Note: - sign here is to make +x correspond to -ra,
        #       so x increases for decreasing ra.
        #       East is to the left on the sky!
        # sin(dra) = -cos(ra0) sin(ra) + sin(ra0) cos(ra)
        sindra = self._sinra * cosra
        sindra -= self._cosra * sinra

        # Calculate k according to which projection we are using
        cosc = cosdec * cosdra
        cosc *= self._cosdec
        cosc += self._sindec * sindec
        if projection is None or projection[0] == 'g':
            k = 1. / cosc
        elif projection[0] == 's':
            k = 2. / (1. + cosc)
        elif projection[0] == 'l':
            k = np.sqrt( 2. / (1.+cosc) )
        elif cosc == 1.:
            k = 1.
        else:
            c = np.arccos(cosc)
            k = c / np.sin(c)

        # u = k * cosdec * sindra
        # v = k * ( self._cosdec * sindec - self._sindec * cosdec * cosdra )
        # (Save k multiplication for later when we also multiply by factor.)
        u = cosdec * sindra
        v = cosdec * cosdra
        v *= -self._sindec
        v += self._cosdec * sindec

        # Convert to arcsec
        factor = radians / arcsec
        k *= factor
        u *= k
        v *= k

        return u, v

    def project_rad(self, ra, dec, projection=None):
        """This is basically identical to the project() function except that the input `ra`, `dec`
        are given in radians rather than packaged as a CelestialCoord object and the returned
        u,v are given in arcsec.

        The main advantage to this is that it will work if `ra` and `dec` are NumPy arrays, in which
        case the output `u`, `v` will also be NumPy arrays.
        """
        if projection not in CelestialCoord._valid_projections:
            raise ValueError('Unknown projection ' + projection)

        self._set_aux()

        cosra = np.cos(ra)
        sinra = np.sin(ra)
        cosdec = np.cos(dec)
        sindec = np.sin(dec)

        return self._project_core(cosra, sinra, cosdec, sindec, projection)

    def deproject(self, u, v, projection=None):
        """Do the reverse process from the project() function.

        i.e. This takes in a position (u,v) and returns the corresponding celestial
        coordinate, using the current coordinate as the center point of the tangent plane
        projection.
        """
        if projection not in CelestialCoord._valid_projections:
            raise ValueError('Unknown projection ' + projection)

        # Again, do the core calculations in a helper function
        ra, dec = self._deproject_core(u / arcsec, v / arcsec, projection)

        return CelestialCoord(_Angle(ra), _Angle(dec))

    def _deproject_core(self, u, v, projection):
        # The inverse equations are also given at the same web sites:
        #
        # sin(dec) = cos(c) sin(dec0) + v sin(c) cos(dec0) / r
        # tan(ra-ra0) = u sin(c) / (r cos(dec0) cos(c) - v sin(dec0) sin(c))
        #
        # where
        #
        # r = sqrt(u^2+v^2)
        # c = tan^(-1)(r)     for gnomonic
        # c = 2 tan^(-1)(r/2) for stereographic
        # c = 2 sin^(-1)(r/2) for lambert
        # c = r               for postel

        # Convert from arcsec to radians
        factor = arcsec / radians
        u *= factor
        v *= factor

        # Note that we can rewrite the formulae as:
        #
        # sin(dec) = cos(c) sin(dec0) + v (sin(c)/r) cos(dec0)
        # tan(ra-ra0) = u (sin(c)/r) / (cos(dec0) cos(c) - v sin(dec0) (sin(c)/r))
        #
        # which means we only need cos(c) and sin(c)/r.  For most of the projections,
        # this saves us from having to take sqrt(rsq).

        rsq = u*u
        rsq += v*v
        if projection is None or projection[0] == 'g':
            # c = arctan(r)
            # cos(c) = 1 / sqrt(1+r^2)
            # sin(c) = r / sqrt(1+r^2)
            cosc = sinc_over_r = 1./np.sqrt(1.+rsq)
        elif projection[0] == 's':
            # c = 2 * arctan(r/2)
            # Some trig manipulations reveal:
            # cos(c) = (4-r^2) / (4+r^2)
            # sin(c) = 4r / (4+r^2)
            cosc = (4.-rsq) / (4.+rsq)
            sinc_over_r = 4. / (4.+rsq)
        elif projection[0] == 'l':
            # c = 2 * arcsin(r/2)
            # Some trig manipulations reveal:
            # cos(c) = 1 - r^2/2
            # sin(c) = r sqrt(4-r^2) / 2
            cosc = 1. - rsq/2.
            sinc_over_r = np.sqrt(4.-rsq) / 2.
        else:
            r = np.sqrt(rsq)
            cosc = np.cos(r)
            sinc_over_r = np.sinc(r/np.pi)

        # Compute sindec, tandra
        # Note: more efficient to use numpy op= as much as possible to avoid temporary arrays.
        self._set_aux()
        # sindec = cosc * self._sindec + v * sinc_over_r * self._cosdec
        sindec = v * sinc_over_r
        sindec *= self._cosdec
        sindec += cosc * self._sindec
        # Remember the - sign so +dra is -u.  East is left.
        tandra_num = u * sinc_over_r
        tandra_num *= -1.
        # tandra_denom = cosc * self._cosdec - v * sinc_over_r * self._sindec
        tandra_denom = v * sinc_over_r
        tandra_denom *= -self._sindec
        tandra_denom += cosc * self._cosdec

        dec = np.arcsin(sindec)
        ra = self.ra.rad() + np.arctan2(tandra_num, tandra_denom)

        return ra, dec

    def deproject_rad(self, u, v, projection=None):
        """This is basically identical to the deproject() function except that the output `ra`,
        `dec` are returned as a tuple (ra, dec) in radians rather than packaged as a CelestialCoord
        object and `u` and `v` are in arcsec rather than Angle instances.

        The main advantage to this is that it will work if `u` and `v` are NumPy arrays, in which
        case the output `ra`, `dec` will also be NumPy arrays.
        """
        if projection not in CelestialCoord._valid_projections:
            raise ValueError('Unknown projection ' + projection)

        return self._deproject_core(u, v, projection)

    def deproject_jac(self, u, v, projection=None):
        """Return the jacobian of the deprojection.

        i.e. if the input position is (u,v) (in arcsec) then the return matrix is

        J = ( dra/du cos(dec)  dra/dv cos(dec) )
            (    ddec/du          ddec/dv      )

        :returns: the matrix as a tuple (J00, J01, J10, J11)
        """
        if projection not in CelestialCoord._valid_projections:
            raise ValueError('Unknown projection ' + projection)

        factor = arcsec / radians
        u = u * factor
        v = v * factor

        # sin(dec) = cos(c) sin(dec0) + v sin(c)/r cos(dec0)
        # tan(ra-ra0) = u sin(c)/r / (cos(dec0) cos(c) - v sin(dec0) sin(c)/r)
        #
        # d(sin(dec)) = cos(dec) ddec = s0 dc + (v ds + s dv) c0
        # dtan(ra-ra0) = sec^2(ra-ra0) dra
        #              = ( (u ds + s du) A - u s (dc c0 - (v ds + s dv) s0 ) )/A^2
        # where s = sin(c) / r
        #       c = cos(c)
        #       s0 = sin(dec0)
        #       c0 = cos(dec0)
        #       A = c c0 - v s s0

        rsq = u*u + v*v
        rsq1 = (u+1.e-4)**2 + v**2
        rsq2 = u**2 + (v+1.e-4)**2
        if projection is None or projection[0] == 'g':
            c = s = 1./np.sqrt(1.+rsq)
            s3 = s*s*s
            dcdu = dsdu = -u*s3
            dcdv = dsdv = -v*s3
        elif projection[0] == 's':
            s = 4. / (4.+rsq)
            c = 2.*s-1.
            ssq = s*s
            dcdu = -u * ssq
            dcdv = -v * ssq
            dsdu = 0.5*dcdu
            dsdv = 0.5*dcdv
        elif projection[0] == 'l':
            c = 1. - rsq/2.
            s = np.sqrt(4.-rsq) / 2.
            dcdu = -u
            dcdv = -v
            dsdu = -u/(4.*s)
            dsdv = -v/(4.*s)
        else:
            r = np.sqrt(rsq)
            if r == 0.:
                c = s = 1
                dcdu = -u
                dcdv = -v
                dsdu = dsdv = 0
            else:
                c = np.cos(r)
                s = np.sin(r)/r
                dcdu = -s*u
                dcdv = -s*v
                dsdu = (c-s)*u/rsq
                dsdv = (c-s)*v/rsq

        self._set_aux()
        s0 = self._sindec
        c0 = self._cosdec
        sindec = c * s0 + v * s * c0
        cosdec = np.sqrt(1.-sindec*sindec)
        dddu = ( s0 * dcdu + v * dsdu * c0 ) / cosdec
        dddv = ( s0 * dcdv + (v * dsdv + s) * c0 ) / cosdec

        tandra_num = u * s
        tandra_denom = c * c0 - v * s * s0
        # Note: A^2 sec^2(dra) = denom^2 (1 + tan^2(dra) = denom^2 + num^2
        A2sec2dra = tandra_denom**2 + tandra_num**2
        drdu = ((u * dsdu + s) * tandra_denom - u * s * ( dcdu * c0 - v * dsdu * s0 ))/A2sec2dra
        drdv = (u * dsdv * tandra_denom - u * s * ( dcdv * c0 - (v * dsdv + s) * s0 ))/A2sec2dra

        drdu *= cosdec
        drdv *= cosdec
        return drdu, drdv, dddu, dddv

    def precess(self, from_epoch, to_epoch):
        """This function precesses equatorial ra and dec from one epoch to another.
           It is adapted from a set of fortran subroutines based on (a) pages 30-34 of
           the Explanatory Supplement to the AE, (b) Lieske, et al. (1977) A&A 58, 1-16,
           and (c) Lieske (1979) A&A 73, 282-284.
        """
        if from_epoch == to_epoch: return self

        # t0, t below correspond to Lieske's big T and little T
        t0 = (from_epoch-2000.)/100.
        t = (to_epoch-from_epoch)/100.
        t02 = t0*t0
        t2 = t*t
        t3 = t2*t

        # a,b,c below correspond to Lieske's zeta_A, z_A and theta_A
        a = ( (2306.2181 + 1.39656*t0 - 0.000139*t02) * t +
              (0.30188 - 0.000344*t0) * t2 + 0.017998 * t3 ) * arcsec
        b = ( (2306.2181 + 1.39656*t0 - 0.000139*t02) * t +
              (1.09468 + 0.000066*t0) * t2 + 0.018203 * t3 ) * arcsec
        c = ( (2004.3109 - 0.85330*t0 - 0.000217*t02) * t +
              (-0.42665 - 0.000217*t0) * t2 - 0.041833 * t3 ) * arcsec
        sina, cosa = a.sincos()
        sinb, cosb = b.sincos()
        sinc, cosc = c.sincos()

        # This is the precession rotation matrix:
        xx = cosa*cosc*cosb - sina*sinb
        yx = -sina*cosc*cosb - cosa*sinb
        zx = -sinc*cosb
        xy = cosa*cosc*sinb + sina*cosb
        yy = -sina*cosc*sinb + cosa*cosb
        zy = -sinc*sinb
        xz = cosa*sinc
        yz = -sina*sinc
        zz = cosc

        # Perform the rotation:
        self._set_aux()
        x2 = xx*self._x + yx*self._y + zx*self._z
        y2 = xy*self._x + yy*self._y + zy*self._z
        z2 = xz*self._x + yz*self._y + zz*self._z

        return CelestialCoord.from_xyz(x2, y2, z2)

    def galactic(self, epoch=2000.):
        """Get the longitude and latitude in galactic coordinates corresponding to this position.

        :param epoch:       The epoch of the current coordinate. [default: 2000.]

        :returns: the longitude and latitude as a tuple (el, b), given as Angle instances.
        """
        # The formulae are implemented in terms of the 1950 coordinates, so we need to
        # precess from the current epoch to 1950.
        temp = self.precess(epoch, 1950.)

        # cf. Lang, Astrophysical Formulae, page 13
        # cos(b) cos(el-33) = cos(dec) cos(ra-282.25)
        # cos(b) sin(el-33) = sin(dec) sin(62.6) + cos(dec) sin(ra-282.25) cos(62.6)
        #            sin(b) = sin(dec) cos(62.6) - cos(dec) sin(ra-282.25) sin(62.6)
        el0 = 33. * degrees
        r0 = 282.25 * degrees
        d0 = 62.6 * degrees
        sind0, cosd0 = d0.sincos()

        sind, cosd = temp.dec.sincos()
        sinr, cosr = (temp.ra-r0).sincos()

        cbcl = cosd*cosr
        cbsl = sind*sind0 + cosd*sinr*cosd0
        sb = sind*cosd0 - cosd*sinr*sind0

        b = _Angle(math.asin(sb))
        el = _Angle(math.atan2(cbsl,cbcl)) + el0

        return (el, b)


    @staticmethod
    def from_galactic(el, b, epoch=2000.):
        """Create a CelestialCoord from the given galactic coordinates

        :param el:          The longitude in galactic coordinates (an Angle instance)
        :param b:           The latitude in galactic coordinates (an Angle instance)
        :param epoch:       The epoch of the returned coordinate. [default: 2000.]

        :returns: the CelestialCoord corresponding to these galactic coordinates.
        """
        el0 = 33. * degrees
        r0 = 282.25 * degrees
        d0 = 62.6 * degrees
        sind0, cosd0 = d0.sincos()

        sinb, cosb = b.sincos()
        sinl, cosl = (el-el0).sincos()
        x1 = cosb*cosl
        y1 = cosb*sinl
        z1 = sinb

        x2 = x1
        y2 = y1 * cosd0 - z1 * sind0
        z2 = y1 * sind0 + z1 * cosd0

        temp = CelestialCoord.from_xyz(x2, y2, z2)
        c1950 = CelestialCoord(temp.ra + r0, temp.dec)
        return c1950.precess(1950., epoch)


    def ecliptic(self, epoch=2000., date=None):
        """Get the longitude and latitude in ecliptic coordinates corresponding to this position.

        The `epoch` parameter is used to get an accurate value for the (time-varying) obliquity of
        the ecliptic.  The formulae for this are quite straightforward.  It requires just a single
        parameter for the transformation, the obliquity of the ecliptic (the Earth's axial tilt).

        :param epoch:       The epoch to be used for estimating the obliquity of the ecliptic, if
                            `date` is None.  But if `date` is given, then use that to determine the
                            epoch.  [default: 2000.]
        :param date:        If a date is given as a python datetime object, then return the
                            position in ecliptic coordinates with respect to the sun position at
                            that date.  If None, then return the true ecliptic coordiantes.
                            [default: None]

        :returns: the longitude and latitude as a tuple (lambda, beta), given as Angle instances.
        """
        # We are going to work in terms of the (x, y, z) projections.
        self._set_aux()

        # Get the obliquity of the ecliptic.
        if date is not None:
            epoch = date.year
        ep = CelestialCoord._ecliptic_obliquity(epoch)
        sin_ep, cos_ep = ep.sincos()

        # Coordinate transformation here, from celestial to ecliptic:
        x_ecl = self._x
        y_ecl = cos_ep*self._y + sin_ep*self._z
        z_ecl = -sin_ep*self._y + cos_ep*self._z

        beta = _Angle(math.asin(z_ecl))
        lam = _Angle(math.atan2(y_ecl, x_ecl))

        if date is not None:
            # Find the sun position in ecliptic coordinates on this date.  We have to convert to
            # Julian day in order to use our helper routine to find the Sun position in ecliptic
            # coordinates.
            lam_sun = CelestialCoord._sun_position_ecliptic(date)
            # Subtract it off, to get ecliptic coordinates relative to the sun.
            lam -= lam_sun

        return (lam.wrap(), beta)

    @staticmethod
    def from_ecliptic(lam, beta, epoch=2000., date=None):
        """Create a CelestialCoord from the given ecliptic coordinates

        :param lam:         The longitude in ecliptic coordinates (an Angle instance)
        :param beta:        The latitude in ecliptic coordinates (an Angle instance)
        :param epoch:       The epoch to be used for estimating the obliquity of the ecliptic, if
                            `date` is None.  But if `date` is given, then use that to determine the
                            epoch.  [default: 2000.]
        :param date:        If a date is given as a python datetime object, then return the
                            position in ecliptic coordinates with respect to the sun position at
                            that date.  If None, then return the true ecliptic coordiantes.
                            [default: None]

        :returns: the CelestialCoord corresponding to these ecliptic coordinates.
        """
        if date is not None:
            lam += CelestialCoord._sun_position_ecliptic(date)

        # Get the (x, y, z)_ecliptic from (lam, beta).
        sinbeta, cosbeta = beta.sincos()
        sinlam, coslam = lam.sincos()
        x_ecl = cosbeta*coslam
        y_ecl = cosbeta*sinlam
        z_ecl = sinbeta

        # Get the obliquity of the ecliptic.
        if date is not None:
            epoch = date.year
        ep = CelestialCoord._ecliptic_obliquity(epoch)

        # Transform to (x, y, z)_equatorial.
        sin_ep, cos_ep = ep.sincos()
        x_eq = x_ecl
        y_eq = cos_ep*y_ecl - sin_ep*z_ecl
        z_eq = sin_ep*y_ecl + cos_ep*z_ecl

        return CelestialCoord.from_xyz(x_eq, y_eq, z_eq)


    def copy(self): return CelestialCoord(self._ra, self._dec)

    def __repr__(self): return 'coord.CelestialCoord(%r, %r)'%(self._ra,self._dec)
    def __str__(self): return 'coord.CelestialCoord(%s, %s)'%(self._ra,self._dec)
    def __hash__(self): return hash(repr(self))

    def __eq__(self, other):
        return (isinstance(other, CelestialCoord) and
                self.ra == other.ra and self.dec == other.dec)
    def __ne__(self, other): return not self.__eq__(other)

    # Some helper functions for the ecliptic functionality.
    @staticmethod
    def _sun_position_ecliptic(date):
        """Helper routine to calculate the position of the sun in ecliptic coordinates given a
        python datetime object.
    
        It is most precise for dates between 1950-2050, and is based on

            http://en.wikipedia.org/wiki/Position_of_the_Sun#Ecliptic_coordinates
        """
        # We start by getting the number of days since Greenwich noon on 1 January 2000 (J2000).
        jd = CelestialCoord._date_to_julian_day(date)
        n = jd - 2451545.0
        L = 280.46*degrees + (0.9856474*degrees) * n
        g = 357.528*degrees + (0.9856003*degrees) * n
        lam = L + (1.915*degrees)*g.sin() + (0.020*degrees)*(2*g).sin()
        return lam

    @staticmethod
    def _date_to_julian_day(date):
        """Helper routine to return the Julian day for a given date.
    
        If `date` is a datetime.datetime instance, then it uses the full time info.
        If `date` is a datetime.date, then it does the calculation for noon of that day.
        """
        # From http://code-highlights.blogspot.com/2013/01/julian-date-in-python.html
        if not (isinstance(date, datetime.date) or isinstance(date, datetime.datetime)):
            raise ValueError("Date must be a python datetime object!")
        a = (14. - date.month)//12
        y = date.year + 4800 - a
        m = date.month + 12*a - 3
        retval = date.day + ((153*m + 2)//5) + 365*y + y//4 - y//100 + y//400 - 32045
        if isinstance(date, datetime.datetime):
            dayfrac = (date.hour + date.minute/60. + date.second/3600.)/24
            # The default is the value at noon, so we want to add 0 if dayfrac = 0.5
            dayfrac -= 0.5
            retval += dayfrac
        return retval

    @staticmethod
    def _ecliptic_obliquity(epoch):
        """Helper routine to return the obliquity of the ecliptic for a given date.
        """
        # We need to figure out the time in Julian centuries from J2000 for this epoch.
        t = (epoch - 2000.)/100.
        # Then we use the last (most recent) formula listed under
        # http://en.wikipedia.org/wiki/Ecliptic#Obliquity_of_the_ecliptic, from
        # JPL's 2010 calculations.
        ep = DMS_Angle('23:26:21.406')
        ep -= DMS_Angle('00:00:46.836769')*t
        ep -= DMS_Angle('00:00:0.0001831')*(t**2)
        ep += DMS_Angle('00:00:0.0020034')*(t**3)
        # There are even higher order terms, but they are probably not important for any reasonable
        # calculation someone would do with this package.
        return ep