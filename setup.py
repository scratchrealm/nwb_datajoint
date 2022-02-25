from setuptools import setup, find_packages
  
setup(
    scripts=["bin/spyglass"],
    install_requires=[
        'sortingview>=0.7.3',
        'click'
    ]
)
