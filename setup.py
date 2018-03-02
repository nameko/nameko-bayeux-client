#!/usr/bin/env python
from setuptools import find_packages, setup

setup(
    name='nameko-bayeux-client',
    version='1.0.0',
    description=(
        'Nameko extension with a Cometd client implementing Bayeux protocol'
    ),
    author='Student.com',
    url='http://github.com/iky/nameko-bayeux-client',
    packages=find_packages(exclude=['test', 'test.*']),
    install_requires=[
        "nameko>=2.5.1",
    ],
    extras_require={
        'dev': [
            "coverage==4.3.4",
            "flake8==3.2.1",
            "pylint==1.8.2",
            "pytest==3.0.6",
            "requests-mock==1.3.0",
        ]
    },
    dependency_links=[],
    zip_safe=True,
    license='Apache License, Version 2.0',
    classifiers=[
        "Programming Language :: Python",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
    ]
)
