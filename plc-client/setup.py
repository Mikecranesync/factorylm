"""Setup script for FactoryLM PLC Client."""

from setuptools import setup, find_packages

setup(
    name="factorylm-plc",
    version="0.3.0",
    description="FactoryLM PLC Client - Industrial I/O Layer",
    author="FactoryLM",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "pymodbus>=3.6.1",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
        ],
    },
)
