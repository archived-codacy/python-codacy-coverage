# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='codacy-coverage',

    version='1.1.0',

    description='Codacy coverage reporter for Python',
    long_description=long_description,

    url='https://github.com/codacy/python-codacy-coverage',

    author='Codacy',
    author_email='team@codacy.com',

    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],

    keywords='development coverage',

    packages=find_packages('src'),
    package_dir={'': 'src'}, include_package_data=True,

    install_requires=['requests', 'six'],

    extras_require={
        'dev': ['check-manifest'],
        'test': ['nosetests', 'coverage'],
    },

    entry_points={
        'console_scripts': [
            'python-codacy-coverage=codacy:main',
        ],
    },
    test_suite='tests'
)
