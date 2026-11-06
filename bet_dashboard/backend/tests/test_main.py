import runpy
from pathlib import Path
from unittest.mock import patch


def test_direct_launch_reuses_module_app() -> None:
    main_path = Path(__file__).parents[1] / "main.py"
    logic = object()

    with (
        patch("core.logic.AppLogic", return_value=logic) as app_logic,
        patch("uvicorn.run") as run_server,
    ):
        namespace = runpy.run_path(str(main_path), run_name="__main__")

    app_logic.assert_called_once()
    run_server.assert_called_once_with(namespace["app"], host="127.0.0.1", port=8000, reload=False)
