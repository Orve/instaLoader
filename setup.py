"""Setup configuration for Multi-Platform Instagram Downloader Bot."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="instagram-downloader-bot",
    version="1.0.0",
    author="Instagram Downloader Bot Contributors",
    description="Multi-platform bot for downloading Instagram media (LINE & Discord)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/instagram-downloader-bot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Communications :: Chat",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "line-bot=run_line:main",
            "discord-bot=run_discord:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)