"""
FactoryLM Core Package Setup
"""

from setuptools import setup, find_packages
import os

# Read version from package
def get_version():
    init_path = os.path.join(
        os.path.dirname(__file__), "src", "factorylm", "__init__.py"
    )
    with open(init_path, "r") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.1.0"


# Read long description from README
def get_long_description():
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


setup(
    name="factorylm",
    version=get_version(),
    author="FactoryLM Team",
    author_email="team@factorylm.com",
    description="LLM Abstraction Layer for Industrial Applications",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/factorylm/core",
    project_urls={
        "Bug Tracker": "https://github.com/factorylm/core/issues",
        "Documentation": "https://github.com/factorylm/core/docs",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "python-dotenv>=1.0.0",
        "groq>=0.14.0",
        "openai>=1.6.1",
        "anthropic>=0.28.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "pytest-asyncio>=0.21.1",
            "black>=23.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
            "isort>=5.13.2",
        ],
        "otel": [
            "opentelemetry-api>=1.20.0",
            "opentelemetry-sdk>=1.20.0",
            "opentelemetry-exporter-otlp-proto-http>=1.20.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "factorylm=factorylm.cli:main",
        ],
    },
)
