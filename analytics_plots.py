"""Root shim to generate all traffic analytics visualization charts."""

from backend.analytics_plots import generate_all_plots

if __name__ == "__main__":
    generate_all_plots()
