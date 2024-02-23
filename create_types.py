#!/usr/bin/env python3
import subprocess
from argparse import ArgumentParser
from dataclasses import dataclass
from os import listdir, mkdir, path
from sys import stderr
from typing import List, Literal
from typing import get_args as get_typing_args

BaseFolder = Literal["data-staging", "data"]
BASE_FOLDERS: List[BaseFolder] = list(get_typing_args(BaseFolder))

PACKAGE_NAME = "pcpart_types"


class Args:
    _base_folder: BaseFolder

    @property
    def base_folder(self) -> BaseFolder:
        return self._base_folder

    @base_folder.setter
    def base_folder(self, value: BaseFolder) -> None:
        if path.exists(value) and path.isdir(value):
            self._base_folder = value
        else:
            for val in BASE_FOLDERS:
                if value != val:
                    other_val = val
                    break
            print(
                f"Warning: {value} does not exist, using {other_val} instead.",
                file=stderr,
            )
            self._base_folder = other_val

    def __init__(self, base_folder: BaseFolder) -> None:
        self.base_folder = base_folder


DEFAULT_BASE_FOLDER: BaseFolder = (
    "data-staging"
    if (path.exists("data-staging") and path.isdir("data-staging"))
    else "data"
)


def get_args() -> Args:
    parser = ArgumentParser()
    parser.add_argument(
        "-b",
        dest="base_folder",
        choices=BASE_FOLDERS,
        default=DEFAULT_BASE_FOLDER,
        help=f"the base folder to work from (Default: {DEFAULT_BASE_FOLDER})",
    )
    return Args(**vars(parser.parse_args()))


def get_json_files(base_folder: BaseFolder) -> List[str]:
    json_folder = path.join(base_folder, "json")
    return list(
        filter(
            lambda x: (path.isfile(x) and x.split(".")[-1] == "json"),
            [path.join(json_folder, f) for f in listdir(json_folder)],
        )
    )


def create_type(json_file: str) -> str | None:
    package_folder = (
        f"{PACKAGE_NAME}.{path.basename(json_file).split('.')[0].replace('-', '_')}"
    )
    if not path.exists(package_folder) and path.isdir(package_folder):
        mkdir(path=package_folder)
    result = subprocess.run(["xsdata", json_file, "--package", package_folder])
    if result.returncode == 0 and path.exists(
        path.join(package_folder.replace(".", path.sep), "__init__.py")
    ):
        return package_folder
    return None


@dataclass
class PCPart:
    package: str
    module: str
    class_name: str

    def import_line(self) -> str:
        return f"from {self.package}.{self.module} import {self.class_name}\n"


def main(args: Args | None = None) -> None:
    if args is None:
        args = get_args()
    pcparts: List[PCPart] = []
    for file in get_json_files(base_folder=args.base_folder):
        created = create_type(json_file=file)
        if created is not None:
            print(f"Created package:\t{created}")
            module = path.basename(file).split(".")[0].replace("-", "_")
            class_name = module.replace("_", " ").title().replace(" ", "")
            pcparts.append(
                PCPart(package=PACKAGE_NAME, module=module, class_name=class_name)
            )

        else:
            print(f"Failed to create package for {file}.")

    if pcparts != []:
        with open(
            file=path.join(PACKAGE_NAME, "__init__.py"), mode="w", encoding="utf8"
        ) as init_file:
            for pcpart in pcparts:
                init_file.write(pcpart.import_line())
        with open(file="pcparts.py", mode="w", encoding="utf8") as pcparts_file:
            pcparts_file.write("PCPARTS = [\n")
            for pcpart in pcparts:
                pcparts_file.write(f'    "{pcpart.class_name}",\n')
            pcparts_file.write("]")


if __name__ == "__main__":
    main()
