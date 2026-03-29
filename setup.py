from setuptools import setup, find_packages

setup(
    name="memora",
    version="0.1.0",
    description="Decision memory layer for AI agent builders — captures WHY decisions were made.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Memora",
    url="https://github.com/YOUR_USERNAME/Memora",
    packages=find_packages(),
    package_data={
        "memora": [
            "dashboard/*.html",
            "landing/*.html",
            ".env.example",
        ],
    },
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=[
        "click>=8.1.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "all": [
            "fastmcp>=2.0.0",
            "groq>=1.0.0",
            "flask>=3.0.0",
            "flask-cors>=4.0.0",
        ],
        "web": [
            "flask>=3.0.0",
            "flask-cors>=4.0.0",
        ],
        "extract": [
            "groq>=1.0.0",
        ],
        "mcp": [
            "fastmcp>=2.0.0",
        ],
        "turso": [
            "libsql-experimental>=0.0.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "memora=memora.cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
