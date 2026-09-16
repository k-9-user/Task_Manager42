import sys

if __package__:
    from scripts.build.commands import main
else:
    from build.commands import main


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
