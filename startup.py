import os
import pathlib
import pty
import subprocess
import threading

import typer
import yaml
from pydantic import BaseModel, Field
from colorama import Fore, Style

app = typer.Typer()
COLORS = [Fore.RED, Fore.YELLOW, Fore.CYAN, Fore.BLUE, Fore.GREEN, Fore.MAGENTA]
MAX_LINE_SIZE = 2048


class Service(BaseModel):
    path: str
    startup: list[str]
    pre_startup: list[str] | None = Field(alias="pre-startup", default=None)
    teardown: list[str] | None = None


class TestConf(BaseModel):
    services: dict[str, Service]


def start_service(name: str, path: str, commands: list[str], color: str):
    command_combined = " && ".join(commands)
    print(f"{wrap(color, name)}: {wrap(Fore.LIGHTBLUE_EX, command_combined)}\n")

    master_fd, slave_fd = pty.openpty()

    process = subprocess.Popen(
        command_combined,
        shell=True,
        cwd=path,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )

    os.close(slave_fd)

    thread = threading.Thread(target=stream_output, args=(master_fd, name, color))
    thread.start()

    return process, thread


def wrap(color: str, msg: str) -> str:
    return f"{color}{msg}{Style.RESET_ALL}"


def stream_output(master_fd: int, service_name: str, color: str) -> None:
    while True:
        try:
            if not (output := os.read(master_fd, MAX_LINE_SIZE).decode("utf-8", errors='backslashreplace')):
                break
            print(
                (
                    "\n".join(
                        [
                            f"{wrap(color, f'[{service_name}]'):<25} {line}"
                            for line in output.splitlines()
                        ]
                    ).strip()
                    + "\n"
                ),
                end="",
                flush=True,
            )
        except (OSError, UnicodeError):
            break
    os.close(master_fd)


def get_services_to_run(conf: TestConf, only: str, excpt: str) -> set[str]:
    if only and excpt:
        raise ValueError("--only and --except cannot be both specified")
    original = set(conf.services.keys())
    only_list = [i.strip() for i in (only.split(",") if only else [])]
    except_list = [i.strip() for i in (excpt.split(",") if excpt else [])]
    if only_list:
        if invalid := [i for i in only_list if i not in original]:
            raise ValueError(f"Invalid service names: {', '.join(invalid)}")
        return set(only_list)
    elif except_list:
        if invalid := [i for i in except_list if i not in original]:
            raise ValueError(f"Invalid service names: {', '.join(invalid)}")
        return original - set(except_list)
    return original


@app.command()
def run(
    only: str = typer.Option(
        None,
        "-o",
        "--only",
        help="Comma-separated list of services to run (e.g., -o service_1,service_3)",
    ),
    except_: str = typer.Option(
        None,
        "-e",
        "--except",
        help="Comma-separated list of services to exclude (e.g., -e service_2,service_4)",
    ),
    include_pre_steps: bool = typer.Option(False, "--pre", "-p", help="Whether to run the `pre-startup` steps")
) -> None:
    with pathlib.Path("test-conf.yaml").open() as f:
        conf = TestConf.model_validate(yaml.safe_load(f))
    services_to_run = get_services_to_run(conf, only, except_)


    print(f"\n Spinning up: {', '.join(services_to_run)}\n")
    processes, threads = [], []
    for idx, (name, details) in enumerate(conf.services.items()):
        if services_to_run and name not in services_to_run:
            continue
        commands = details.startup
        if include_pre_steps:
            commands = (details.pre_startup or []) + commands
        process, thread = start_service(
            name, details.path, commands, COLORS[idx % len(COLORS)]
        )
        processes.append(process)
        threads.append(thread)

    try:
        for thread in threads:
            thread.join()
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        print("Terminating all services...")
        for process in processes:
            process.terminate()
        for idx, (name, details) in enumerate(conf.services.items()):
            if details.teardown is None:
                continue
            if services_to_run and name not in services_to_run:
                continue
            process, thread = start_service(
                name, details.path, details.teardown, COLORS[idx % len(COLORS)]
            )
            processes.append(process)
            threads.append(thread)


if __name__ == "__main__":
    app()
