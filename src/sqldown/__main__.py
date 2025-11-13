"""Enable running sqldown as a module: python -m sqldown"""

from .cli import main

if __name__ == '__main__':
    main()
