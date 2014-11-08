from setuptools import setup, find_packages
import os
import re
import sys

import pyhdfeos

kwargs = {'name': 'pyhdfeos',
          'description': 'Tools for accessing HDF-EOS grids',
          'long_description': open('README.md').read(),
          'author': 'John Evans',
          'author_email': 'john.g.evans.ne@gmail.com',
          'url': 'http://hdfeos.org',
          'packages': ['pyhdfeos', 'pyhdfeos.lib'],
          'version': '0.1.0rc3',
          'zip_safe':  False,
          'ext_modules': [pyhdfeos.lib.he4.ffi.verifier.get_extension(),
                          pyhdfeos.lib.he5.ffi.verifier.get_extension()],
          'entry_points': {
              'console_scripts': ['eosdump=pyhdfeos.command_line:dump_metadata'],
              },
          'license': 'MIT'}

clssfrs = ["Programming Language :: Python",
           "Programming Language :: Python :: 2.7",
           "Programming Language :: Python :: 3.3",
           "Programming Language :: Python :: 3.4",
           "Programming Language :: Python :: Implementation :: CPython",
           "License :: OSI Approved :: MIT License",
           "Development Status :: 3 - Production/Alpha",
           "Operating System :: MacOS",
           "Operating System :: POSIX :: Linux",
           "Intended Audience :: Science/Research",
           "Intended Audience :: Information Technology",
           "Topic :: Software Development :: Libraries :: Python Modules"]
kwargs['classifiers'] = clssfrs

setup(**kwargs)
