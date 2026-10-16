import sys

from luna.cli import Program
from luna.test.runner import LunaTest


class Luna(Program):
	name = "luna"
	commands = (LunaTest,)


def main():
	Luna.main(sys.argv)


if __name__ == "__main__":
	main()
