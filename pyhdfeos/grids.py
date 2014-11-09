import collections
from itertools import filterfalse
import os
import platform
import struct
import textwrap

import numpy as np

from .lib import he4, he5, sd

class _GridVariable(object):
    """
    """
    def __init__(self, gridid, fieldname, he_module):
        self.gridid = gridid
        self.fieldname = fieldname
        self._he = he_module

        x = self._he.gdfieldinfo(self.gridid, fieldname)
        self.shape, self.ntype, self.dimlist = x[0:3]

        # HDFEOS5 only.
        self.attrs = collections.OrderedDict()
        if hasattr(self._he, 'gdinqlocattrs'):
            attr_names = self._he.gdinqlocattrs(self.gridid, self.fieldname)
            for attrname in attr_names:
                self.attrs[attrname] = self._he.gdreadlocattr(self.gridid,
                                                              self.fieldname,
                                                              attrname)

    def __str__(self):
        dimstr = ", ".join(self.dimlist)
        msg = "{0}[{1}]:\n".format(self.fieldname, dimstr)

        for name, value in self.attrs.items():
            msg += "    {0}:  {1} ;\n".format(name, value)
        return msg

    def __getitem__(self, index):
        nrows = self.shape[0]
        ncols = self.shape[1]
        ndims = len(self.shape)

        # Set up defaults.
        start = np.zeros(ndims)
        stride = np.ones(ndims)
        edge = list(self.shape)

        if isinstance(index, int):
            # Retrieve a row.
            start[0] = index
            stride[0] = 1
            edge[0] = 1
            for j in range(1, ndims):
                start[j] = 0
                stride[j] = 1
                edge[j] = self.shape[j]
            data = self._he.gdreadfield(self.gridid, self.fieldname,
                                        start, stride, edge)

            # Reduce dimensionality in the row dimension.
            data = np.squeeze(data, axis=0)
            return data

        if index is Ellipsis:
            # Case of [...]
            # Handle it below.
            return self.__getitem__(slice(None,None,None))

        if isinstance(index, slice):
            if index.start is None and index.stop is None and index.step is None:
                # Case of [:].  Read all of the data.
                return self._he.gdreadfield(self.gridid, self.fieldname,
                                             start, stride, edge)

            msg = "Single slice argument integer is only legal if ':'"
            raise RuntimeError(msg)

        if isinstance(index, tuple) and any(x is Ellipsis for x in index):
            # Remove the first ellipsis we find.
            newindex = []
            first_ellipsis = True
            for j, idx in enumerate(index):
                if idx is Ellipsis and first_ellipsis:
                    newindex.append(slice(0, self.shape[j]))
                    first_ellipsis = False
                else:
                    newindex.append(idx)

            # Run once again because it is possible that there's another
            # Ellipsis object.
            newindex = tuple(newindex)
            return self.__getitem__(newindex)

        if isinstance(index, tuple) and any(isinstance(x, int) for x in index):
            # Find the first such integer argument, replace it with a slice.
            lst = list(index)
            predicate = lambda x: not isinstance(x[1], int)
            g = filterfalse(predicate, enumerate(index))
            idx = next(g)[0]
            lst[idx] = slice(index[idx], index[idx] + 1)
            newindex = tuple(lst)

            # Invoke array-based slicing again, as there may be additional
            # integer argument remaining.
            data = self.__getitem__(newindex)

            # Reduce dimensionality in the scalar dimension.
            data = np.squeeze(data, axis=idx)
            return data

        # Assuming pargs is a tuple of slices from now on.  
        # This is the workhorse section for the general case.
        for j in range(len(index)):

            if index[j].start is not None:
                start[j] = index[j].start

            if index[j].step is not None:
                stride[j] = index[j].step

            if index[j].stop is None:
                edge[j] = np.floor((self.shape[j] - start[j]) / stride[j])
            else:
                edge[j] = np.floor((index[j].stop - start[j]) / stride[j])

        return self._he.gdreadfield(self.gridid, self.fieldname,
                                     start, stride, edge)



class _Grid(object):
    """
    """
    def __init__(self, gdfid, gridname, he_module):
        self._he = he_module
        self.gridid = self._he.gdattach(gdfid, gridname)
        self.gridname = gridname

        dimnames, dimlens = self._he.gdinqdims(self.gridid)
        dims = [(k, v) for (k, v) in zip(dimnames, dimlens)]
        self.dims = collections.OrderedDict(dims)

        self.shape, self.upleft, self.lowright = self._he.gdgridinfo(self.gridid)

        projcode, zonecode, spherecode, projparms = self._he.gdprojinfo(self.gridid)
        self.projcode = projcode
        self.zonecode = zonecode
        self.spherecode = spherecode
        self._sphere = _SPHERE[spherecode]
        self.projparms = projparms

        self.origincode = self._he.gdorigininfo(self.gridid)
        self.pixregcode = self._he.gdpixreginfo(self.gridid)

        # collect the fieldnames
        self._fields, _, _ = self._he.gdinqfields(self.gridid)
        self.fields = collections.OrderedDict()
        for fieldname in self._fields:
            self.fields[fieldname] = _GridVariable(self.gridid,
                                                      fieldname,
                                                      self._he)

        attr_list = self._he.gdinqattrs(self.gridid)
        self.attrs = {}
        for attr in attr_list:
            self.attrs[attr] = self._he.gdreadattr(self.gridid, attr)

    def __del__(self):
        self._he.gddetach(self.gridid)

    def __str__(self):
        msg = "Grid:  {0}\n".format(self.gridname)
        msg += "    Shape:  {0}\n".format(self.shape)

        msg += "    Dimensions:\n"
        for dimname, dimlen in self.dims.items():
            msg += "        {0}:  {1}\n".format(dimname, dimlen)

        msg += "    Upper Left (x,y):  {0}\n".format(self.upleft)
        msg += "    Lower Right (x,y):  {0}\n".format(self.lowright)
        msg += "    Sphere:  {0}\n".format(self._sphere)
        if self.projcode == 0:
            msg += "    Projection:  Geographic\n"
        elif self.projcode == 1:
            msg += "    Projection:  UTM\n"
            msg += self._projection_lonz_latz()
        elif self.projcode == 3:
            msg += "    Projection:  Albers Conical Equal Area\n"
            msg += self._projection_semi_major_semi_minor()
            msg += self._projection_latitudes_of_standard_parallels()
            msg += self._projection_longitude_of_central_meridian()
            msg += self._projection_latitude_of_projection_origin()
            msg += self._projection_false_easting_northing()
        elif self.projcode == 6:
            msg += "    Projection:  Polar Stereographic\n"
            msg += self._projection_semi_major_semi_minor()
            msg += self._projection_longitude_pole()
            msg += self._projection_true_scale()
            msg += self._projection_false_easting_northing()
        elif self.projcode == 11:
            msg += "    Projection:  Lambert Azimuthal\n"
            msg += self._projection_sphere()
            msg += self._projection_center_lon_lat()
            msg += self._projection_false_easting_northing()
        elif self.projcode == 16:
            msg += "    Projection:  Sinusoidal\n"
            msg += self._projection_sphere()
            msg += self._projection_longitude_of_central_meridian()
            msg += self._projection_false_easting_northing()

        msg += "    Fields:\n"
        for field in self.fields.keys():
            msg += textwrap.indent(str(self.fields[field]), ' ' * 8)

        msg += "    Grid Attributes:\n"
        for attr in self.attrs.keys():
            msg += "        {0}:  {1}\n".format(attr, self.attrs[attr])

        
        return msg

    def _projection_lonz_latz(self):
        """
        __str__ helper method for utm projections
        """
        if self.projparms[0] == 0 and self.projparms[1] == 0:
            msg = "        UTM zone:  {0}\n".format(self.zonecode)
        else:
            lonz = self.projparms[0] / 1e6
            latz = self.projparms[1] / 1e6
            msg = "        UTM zone longitude:  {0}\n".format(lonz)
            msg += "        UTM zone latitude:  {0}\n".format(latz)
        return msg

    def _projection_longitude_pole(self):
        """
        __str__ helper method for projections with longitude below pole of map
        """
        longpole = self.projparms[4] / 1e6
        return "        Longitude below pole of map:  {0}\n".format(longpole)

    def _projection_true_scale(self):
        """
        __str__ helper method for projections with latitude of true scale
        """
        truescale = self.projparms[5] / 1e6
        return "        Latitude of true scale:  {0}\n".format(truescale)

    def _projection_sphere(self):
        """
        __str__ helper method for projections with known reference sphere radius
        """
        sphere = self.projparms[0] / 1000
        if sphere == 0:
            sphere = 6370.997
        return "        Radius of reference sphere(km):  {0}\n".format(sphere)

    def _projection_semi_major_semi_minor(self):
        """
        __str__ helper method for projections semi-major and semi-minor values
        """
        if self.projparms[0] == 0:
            # Clarke 1866
            semi_major = 6378.2064
        else:
            semi_major = self.projparms[0] / 1000
        if self.projparms[1] == 0:
            # spherical
            semi_minor = semi_major
        elif self.projparms[1] < 0:
            # eccentricity
            semi_minor = semi_major * np.sqrt(1 - self.projparms[1]**2)
        else:
            # semi minor axis
            semi_minor = self.projparms[1]
        msg = "        Semi-major axis(km):  {0}\n".format(semi_major)
        msg += "        Semi-minor axis(km):  {0}\n".format(semi_minor)
        return msg

    def _projection_latitudes_of_standard_parallels(self):
        """
        __str__ helper method for projections with 1st, 2nd standard parallels
        """
        msg = "        Latitude of 1st Standard Parallel:  {0}\n"
        msg += "        Latitude of 2nd Standard Parallel:  {1}\n"
        msg = msg.format(self.projparms[2]/1e6, self.projparms[3]/1e6)
        return msg

    def _projection_center_lon_lat(self):
        """
        __str__ helper method for projections center of projection lat and lon
        """
        msg = "        Center Longitude:  {0}\n".format(self.projparms[4]/1e6)
        msg += "        Center Latitude:  {0}\n".format(self.projparms[5]/1e6)
        return msg

    def _projection_latitude_of_projection_origin(self):
        """
        __str__ helper method for latitude of projection origin
        """
        val = self.projparms[5]/1e6
        msg = "        Latitude of Projection Origin:  {0}\n".format(val)
        return msg

    def _projection_longitude_of_central_meridian(self):
        """
        __str__ helper method for longitude of central meridian
        """
        val = self.projparms[4]/1e6
        msg = "        Longitude of Central Meridian:  {0}\n".format(val)
        return msg

    def _projection_false_easting_northing(self):
        """
        __str__ helper method for projections with false easting and northing
        """
        msg = "        False Easting:  {0}\n".format(self.projparms[6])
        msg += "        False Northing:  {0}\n".format(self.projparms[7])
        return msg

    def __getitem__(self, index):
        """
        Retrieve grid coordinates.
        """
        numrows, numcols = self.shape

        if isinstance(index, int):
            raise RuntimeError("A scalar integer is not a legal argument.")

        if index is Ellipsis:
            # Case of [...]
            # Handle it below.
            rows = cols = slice(None, None, None)
            return self.__getitem__((rows, cols))

        if isinstance(index, slice):
            if index.start is None and index.stop is None and index.step is None:
                # Case of jp2[:]
                return self.__getitem__((index,index))

            msg = "Single slice argument integer is only legal if ':'"
            raise RuntimeError(msg)

        if isinstance(index, tuple) and len(index) > 2:
            msg = "More than two slice arguments are not allowed."
            raise RuntimeError(msg)

        if isinstance(index, tuple) and any(x is Ellipsis for x in index):
            # Remove the first ellipsis we find.
            rows = slice(0, numrows)
            cols = slice(0, numcols)
            if index[0] is Ellipsis:
                newindex = (rows, index[1])
            else:
                newindex = (index[0], cols)

            # Run once again because it is possible that there's another
            # Ellipsis object.
            return self.__getitem__(newindex)

        if isinstance(index, tuple) and any(isinstance(x, int) for x in index):
            # Replace the first such integer argument, replace it with a slice.
            lst = list(pargs)
            predicate = lambda x: not isinstance(x[1], int)
            g = filterfalse(predicate, enumerate(pargs))
            idx = next(g)[0]
            lst[idx] = slice(pargs[idx], pargs[idx] + 1)
            newindex = tuple(lst)

            # Invoke array-based slicing again, as there may be additional
            # integer argument remaining.
            lat, lon = self.__getitem__(newindex)

            # Reduce dimensionality in the scalar dimension.
            lat = np.squeeze(lat, axis=idx)
            lon = np.squeeze(lon, axis=idx)
            return lat, lon

        # Assuming pargs is a tuple of slices from now on.  
        # This is the workhorse section for the general case.
        rows = index[0]
        cols = index[1]

        rows_start = 0 if rows.start is None else rows.start
        rows_step = 1 if rows.step is None else rows.step
        rows_stop = numrows if rows.stop is None else rows.stop
        cols_start = 0 if cols.start is None else cols.start
        cols_step = 1 if cols.step is None else cols.step
        cols_stop = numcols if cols.stop is None else cols.stop

        if (((rows_start < 0) or (rows_stop > numrows) or (cols_start < 0) or
             (cols_stop > numcols))):
            msg = "Grid index arguments are out of bounds."
            raise RuntimeError(msg)

        col = np.arange(cols_start, cols_stop, cols_step)
        row = np.arange(rows_start, rows_stop, rows_step)
        cols, rows = np.meshgrid(col,row)
        cols = cols.astype(np.int32)
        rows = rows.astype(np.int32)
        lon, lat = self._he.gdij2ll(self.projcode, self.zonecode, self.projparms,
                             self.spherecode, self.shape[1], self.shape[0],
                             self.upleft, self.lowright,
                             rows, cols,
                             self.pixregcode, self.origincode)
        return lat, lon


class GridFile(object):
    """
    Access to HDF-EOS grid files.
    """
    def __init__(self, filename):
        self.filename = filename
        try:
            self.gdfid = he4.gdopen(filename)
            self._he = he4
        except IOError as err:
            self.gdfid = he5.gdopen(filename)
            self._he = he5

        gridlist = self._he.gdinqgrid(filename)
        self.grids = collections.OrderedDict()
        for gridname in gridlist:
            self.grids[gridname] = _Grid(self.gdfid, gridname, self._he)
        
            if not hasattr(self._he, 'gdinqlocattrs'):
                # Inquire about hdf4 attributes using SD interface
                _, sdid = he4.ehidinfo(self.gdfid)
                for fieldname in self.grids[gridname].fields.keys():
                    attrs = self._hdf4_attrs(sdid, fieldname) 
                    self.grids[gridname].fields[fieldname].attrs = attrs

    def _hdf4_attrs(self, sdid, fieldname):
        attrs = collections.OrderedDict()
        try:
            idx = sd.nametoindex(sdid, fieldname)
        except:
            return attrs

        try:
            sds_id = sd.select(sdid, idx)
        except:
            return attrs

        try:
            _, _, _, _, nattrs = sd.getinfo(sds_id)
            for idx in range(nattrs):
                name, _, _ = sd.attrinfo(sds_id, idx)
                attrs[name] = sd.readattr(sds_id, idx)
        except:
            pass
        finally:
            sd.endaccess(sds_id)
        return attrs

    def __str__(self):
        msg = "{0}\n".format(os.path.basename(self.filename))
        for grid in self.grids.keys():
            msg += str(self.grids[grid])
        return msg

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __del__(self):
        """
        Clean up any open grids, close the file
        """
        for gridname in self.grids:
            grid = self.grids[gridname]
            self.grids[gridname] = None
            del grid
        self._he.gdclose(self.gdfid)


_SPHERE = {
        -1: 'Unspecified',
        0: 'Clarke 1866',
        1: 'Clarke 1880',
        2: 'Bessel',
        3: 'International 1967',
        4: 'International 1909',
        5: 'WGS 72',
        6: 'Everest',
        7: 'WGS 66',
        8: 'GRS 1980',
        9: 'Airy',
        10: 'Modified Airy',
        11: 'Modified Everest',
        12: 'WGS 84',
        13: 'Southeast Asia',
        14: 'Australian National',
        15: 'Krassovsky',
        16: 'Hough',
        17: 'Mercury 1960',
        18: 'Modified Mercury 1968',
        19: 'Sphere of Radius 6370997m',
        20: 'Sphere of Radius 6371228m',
        21: 'Sphere of Radius 6371007.181'
}
