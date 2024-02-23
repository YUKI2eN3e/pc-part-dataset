#!/usr/bin/env python3
# ruff: noqa: F403
# mypy: disable-error-code="import-not-found"
# type: ignore[import-not-found,syntax]
import json
import sqlite3
from dataclasses import dataclass
from os import path, remove
from sys import stderr
from typing import ClassVar, Dict, List, Protocol

from create_types import get_args

try:
    import pcpart_types
    from pcpart_types import *
    from pcparts import PCPARTS
except ImportError:
    from create_types import main as ct_main

    ct_main(args=get_args())
    import pcpart_types
    from pcpart_types import *
    from pcparts import PCPARTS


class DataClass(Protocol):
    __dataclass_fields__: ClassVar[Dict]


@dataclass
class Table:
    name: str
    fields: str


BASE_FOLDER = get_args().base_folder
DB_FILE = path.join(BASE_FOLDER, "pc_parts.db3")


def module_to_class(module_name: str) -> str:
    return module_name.replace("-", "_").replace("_", " ").title().replace(" ", "")


def get_pcpart_class(pcpart_name: str) -> DataClass | None:
    if "_" in pcpart_name:
        _pcpart_name = module_to_class(module_name=pcpart_name)
        print(f"{pcpart_name} is a module, assuming {_pcpart_name}", file=stderr)
        pcpart_name = _pcpart_name

    try:
        return getattr(pcpart_types, pcpart_name)
    except AttributeError:
        pass
    return None


def setup_db(conn: sqlite3.Connection) -> List[Table] | None:
    tables: List[Table] = []
    for pcpart_name in PCPARTS:
        pcpart = get_pcpart_class(pcpart_name=pcpart_name)
        fields: str = ""
        for key in pcpart.__annotations__.keys():
            if "List" not in str(pcpart.__annotations__[key]):
                types = (
                    str(pcpart.__annotations__[key])
                    .removeprefix("typing.")
                    .removeprefix("Optional[")
                    .removeprefix("Union[")
                    .removesuffix("]")
                )
            else:
                types == "str"
            fields = f"{fields}, {key} {'TEXT' if 'str' in types else ('INTEGER' if ('int' in types or 'float' in types) else ('BOOLEAN' if 'bool' in types else 'BLOB'))}"
        fields = fields.strip().removeprefix(",").removesuffix(",").strip()
        table_name = pcpart.__module__.split(".")[1]
        sql_cmd = f"CREATE TABLE '{table_name}' ({fields});"
        print(sql_cmd)
        conn.execute(sql_cmd)
        tables.append(Table(name=table_name, fields=fields))
    conn.commit()
    return tables if tables != [] else None


def load_pcparts(part_file: str) -> List[DataClass] | None:
    part_file = (part_file if ".json" in part_file else f"{part_file}.json").replace(
        "_", "-"
    )

    if not (path.exists(part_file) and path.isfile(part_file)):
        _part_file = path.join(
            (
                "json"
                if (path.exists("json") and path.isdir("json"))
                else path.join(BASE_FOLDER, "json")
            ),
            part_file,
        )
        if path.exists(_part_file) and path.isfile(_part_file):
            return load_pcparts(part_file=_part_file)
        # search recursively for part_file

    pcpart = get_pcpart_class(
        pcpart_name=module_to_class(module_name=path.basename(part_file.split(".")[0]))
    )
    if pcpart is None:
        return None

    parts: List[DataClass] = []

    with open(file=part_file, mode="r", encoding="utf8") as file:
        for part in json.load(fp=file):
            if "type" in part.keys():
                part["type_value"] = part.pop("type")
            parts.append(pcpart(**part))  # type: ignore[operator]

    return parts


def fill_db(conn: sqlite3.Connection, tables: List[Table]) -> None:
    for table in tables:
        insert_str: str = (
            f"INSERT INTO '{table.name}' ({table.fields.replace('TEXT', '').replace('INTEGER', '').replace('BOOLEAN', '').replace('BLOB', '')}) VALUES ({(', '.join(['?' for i in range(0, len(table.fields.split(',')))])).strip().removeprefix(',').removesuffix(',').strip()})"
        )

        print(insert_str)

        pcparts = load_pcparts(part_file=table.name)
        if pcparts is not None:
            values_list: List[DataClass] = pcparts
            for values_obj in values_list:
                values = tuple(
                    [
                        (
                            values_obj.__getattribute__(key)
                            if not isinstance(values_obj.__getattribute__(key), List)
                            else json.dumps(values_obj.__getattribute__(key))
                        )
                        for key in values_obj.__annotations__.keys()
                    ]
                )
                print(f"{insert_str},\n {values}")
                conn.execute(insert_str, values)
    conn.commit()


def main() -> None:
    if path.exists(DB_FILE) and path.isfile(DB_FILE):
        remove(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    tables = setup_db(conn=conn)
    if tables is not None:
        fill_db(conn=conn, tables=tables)
    conn.close()


if __name__ == "__main__":
    main()
