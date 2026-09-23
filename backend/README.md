# Backend scaffold

This is a contract-only scaffold for the future on-premise backend. Audio processing, model downloads, Ollama calls, and DOCX/PDF generation are intentionally not implemented or run at this stage.

The future application entrypoint is `app.main:app`. See the root [README](../README.md) and [architecture](../docs/architecture.md).

The team now implements backend, Local AI, and Android in parallel. Follow the [role boundaries](../docs/team-workflow.md) and [target HTTP contract](../docs/api-contract.md). Local AI owns concrete `local.py` adapters and its dependency file; Medet integrates those adapters into the server. `requirements.txt` lists planned dependencies, not a tested lockfile. Model installation on the AI participant's machine is authorized by that participant's task prompt.
