import sys


def help_message(message: str):
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(message)
        sys.exit(0)
