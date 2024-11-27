from setuptools import setup, find_packages

setup(
    name="weibo-favorites",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "selenium",
        "requests",
    ],
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
