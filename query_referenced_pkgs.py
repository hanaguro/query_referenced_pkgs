#! /usr/bin/python
# -*- coding: utf-8 -*-;

'''
get_depends.pyで作成した ~/depends.sql3 データベースを元に，
引数で与えられたPlamo Linuxパッケージを参照しているパッケージを調べる
'''

import sqlite3
import os
import sys
import magic
from pathlib import Path

PKG_PATH = '/var/log/packages/'
DB_PATH = './depends.sql3'


def check_elf(file):
    try:
        res = magic.from_file(file)
    except Exception:
        return False

    if res.find('ELF') >= 0 and res.find('dynamically linked') > 0 \
            and res.find('32-bit') == -1:
        return True
    else:
        return False


def extract_file_paths(file_data):
    """
    与えられたファイルから「FILE LIST:」以降のファイルパスを抽出し、
    先頭に'/'を追加してリストとして返します。
    ディレクトリ（'/'で終わる行）は除外されます。
    """
    paths = []
    in_file_list = False

    for line in file_data.strip().split('\n'):
        path = line.strip()

        if path == "FILE LIST:":
            in_file_list = True
            continue

        if in_file_list:
            if not path or path.endswith('/'):
                continue
            paths.append('/' + path)

    return paths


def build_package_file_index():
    """
    /var/log/packages/の全ファイルを読み込み、
    ファイルパス -> パッケージ名のリストのマッピングを作成
    
    同じファイルパスが複数のパッケージに含まれる場合に対応
    """
    packages_dir = Path(PKG_PATH)
    file_to_package = {}

    if not packages_dir.exists():
        print(f"エラー: {packages_dir} が存在しません", file=sys.stderr)
        return file_to_package

#    print("パッケージインデックスを構築中...", file=sys.stderr)

    for package_file in packages_dir.iterdir():
        if package_file.is_file():
            try:
                with open(package_file, 'r',
                          encoding='utf-8', errors='ignore') as f:
                    in_file_list = False
                    for line in f:
                        line = line.strip()
                        if line == "FILE LIST:":
                            in_file_list = True
                            continue
                        if in_file_list and line and not line.endswith('/'):
                            # ファイルパスをキーに、パッケージ名のリストを値として登録
                            if line not in file_to_package:
                                file_to_package[line] = []
                            file_to_package[line].append(package_file.name)
            except Exception as e:
                print(f"警告: {package_file} の読み込み中にエラー: {e}", file=sys.stderr)

#    print(f"インデックス構築完了: {len(file_to_package)} ファイル", file=sys.stderr)
    return file_to_package


def find_package_from_index(filepath, index):
    """
    インデックスから高速にパッケージを検索

    Returns:
        list: 該当するパッケージ名のリスト（見つからない場合は空リスト）
    """
    search_path = filepath.lstrip('/')  # 先頭の'/'を削除
    return index.get(search_path, [])


def get_library_variants(libpath):
    """
    ライブラリパスからバージョン番号を段階的に削除したバリアントを生成

    Returns:
        リスト
    """
    path = Path(libpath)
    variants = [str(path)]

    name = path.name
    parent = path.parent

    if '.so' not in name:
        return variants

    # 'libfoo.so.1.2.3' -> ['libfoo', '.1.2.3']
    # 'libfoo.so' -> ['libfoo', '']
    parts = name.split('.so')
    if len(parts) != 2:
        return variants

    base = parts[0] + '.so'
    version = parts[1]

    if not version:  # 空文字の場合はreturn
        return variants

    # ".1.2.3" -> ['1', '2', '3']
    version_parts = version.lstrip('.').split('.')

    for i in range(len(version_parts) - 1, 0, -1):
        # [1, 2, 3] -> range(2, 0, -1)
        shorter_version = '.'.join(version_parts[:i])  # i=2 なら 1.2
        variant = parent / f"{base}.{shorter_version}"
        variants.append(str(variant))

    variants.append(str(parent / base))

    return variants


def query_referenced(cur, path):
    """
    pathで与えられたファイルを参照しているバイナリファイルを調べる
    """
    sql = 'select realname from depends where realname like ? group by realname;'
    cur.execute(sql, (f'%{path}%',))
    tgt = [row[0] for row in cur]

    paths = []
    for realname in tgt:
        sql = 'select path from depends where realname=?;'
        cur.execute(sql, (realname,))
        paths.extend([row[0] for row in cur])

    return paths


def main():
    dbname = DB_PATH
    if not os.access(dbname, os.R_OK):
        print("cannot open database:{0}".format(dbname))
        sys.exit(1)

    if len(sys.argv) != 2:
        print(f"使い方: {sys.argv[0]} <パッケージ名>")
        sys.exit(1)

    arg = sys.argv[1]

    try:
        with open(PKG_PATH+arg, 'r') as f:
            pkg = f.read()
    except FileNotFoundError:
        print(f"パッケージが見つかりません: {arg}")
        sys.exit(1)
    except Exception as e:
        print(f"予期せぬファイル操作エラーが発生しました: {e}")
        sys.exit(1)

    # パッケージインデックスを事前構築（これが高速化のキー）
    package_index = build_package_file_index()

    file_paths = extract_file_paths(pkg)
    elf_paths = [path for path in file_paths if check_elf(path)]

    # DB接続を1回だけ行う
    conn = sqlite3.connect(dbname)
    cur = conn.cursor()

    packages = set()  # setを使って重複を自動排除
    already_checked = set()  # setで高速化

    for path in elf_paths:
        variants = get_library_variants(path)

        for v in variants:
            if v in already_checked:
                continue
            already_checked.add(v)

            ref_paths = query_referenced(cur, v)

            for ref in ref_paths:
                # インデックスから高速検索（複数パッケージに対応）
                pkgs = find_package_from_index(ref, package_index)
                for pkg in pkgs:
                    packages.add(pkg)

    conn.close()

    # ソート済みでパッケージ名を出力
    for pkg in sorted(packages):
        print(pkg)


if __name__ == "__main__":
    main()
