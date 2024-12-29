from setuptools import find_packages, setup

setup(
    name="weibo-favorites",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "selenium>=4.15.2",
        "webdriver-manager>=4.0.1",
        "flask>=3.0.0",
        "requests>=2.31.0",
        "redis>=5.0.0",
        "rq>=1.15.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
        ],
    },
    python_requires=">=3.8",
    author="xujiajiadexiaokeai",
    author_email="",  # 添加你的邮箱
    description="A Python package for crawling and archiving Weibo favorites",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/xujiajiadexiaokeai/get-weibo-favorites",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
