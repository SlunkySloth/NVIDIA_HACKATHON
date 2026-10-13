"""Apply resource limits after spawning, before starting a fixture or its tests."""

import os
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**2, 2 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
    os.execv(sys.executable, [sys.executable, *sys.argv[1:]])


if __name__ == "__main__":
    main()
