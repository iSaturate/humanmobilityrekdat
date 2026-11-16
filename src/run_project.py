"""One command: download/verify, build notebook, execute, export figures and reports."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

from create_notebook import ROOT, create
from download_data import main as download


def main(offline=False):
    if not offline:
        download()
    notebook_path = create()
    nb = nbformat.read(notebook_path, as_version=4)
    # Use this interpreter, without installing a persistent user-wide kernel spec.
    with tempfile.TemporaryDirectory(prefix="mobility-kernel-") as tmp:
        spec = Path(tmp) / "mobility"
        spec.mkdir()
        (spec / "kernel.json").write_text(json.dumps({
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Mobility project", "language": "python"}), encoding="utf-8")
        manager = KernelManager(kernel_name="mobility", kernel_spec_manager=KernelSpecManager(kernel_dirs=[tmp]))
        client = NotebookClient(nb, km=manager, timeout=240, resources={"metadata": {"path": str(ROOT)}})
        client.execute()
    # Keep shared notebook metadata portable; only the temporary execution kernel is local.
    nb.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nbformat.validate(nb)
    nbformat.write(nb, notebook_path)
    print("Executed without cell errors:", notebook_path, flush=True)
    print("Figures:", ROOT / "figures", "| Reports:", ROOT / "reports", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use previously downloaded raw data and manifest")
    main(parser.parse_args().offline)
