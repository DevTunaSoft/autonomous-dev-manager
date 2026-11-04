"""Frozen Windows entrypoint for ADM supervisor (not a graphical interface)."""
from adm.daemon import main
if __name__ == "__main__":
    main()
