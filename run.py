"""PyInstaller entry point — avoids relative import issues when frozen."""
from service.main import main

if __name__ == '__main__':
    main()
