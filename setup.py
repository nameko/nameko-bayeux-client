#!/usr/bin/env python
from setuptools import find_packages, setup

setup(
    name='nameko-bayeux-client',
    version='1.0.0',
    description=(
        'Nameko extension with a Cometd client implementing Bayeux protocol'
    ),
    author='Student.com',
    url='http://github.com/nameko/nameko-bayeux-client',
    packages=find_packages(exclude=['test', 'test.*']),
    install_requires=[
        "nameko>=2.5.4",
    ],
    extras_require={
        'dev': [
            "coverage",
            "flake8",
            "pylint",
            "pytest",
            "requests-mock",
        ]
    },
    dependency_links=[],
    zip_safe=True,
    license='Apache License, Version 2.0',
    classifiers=[
        "Programming Language :: Python",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
    ]
)
