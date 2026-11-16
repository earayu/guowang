# -*- coding: utf-8 -*-
"""把合成投标包按顺序传进受审库，等索引完成。

串行上传：并发会撞函数/文档服务的限流，且失败重试时难以判断哪一份卡住。
每份传完立刻报索引状态，失败的不静默跳过——少一份，受审侧就缺一家，
后面判定会看起来「这家没违规」，其实是没数据。
"""
import io
import json
import os
import subprocess
import sys

CLI = "./apemind-cli/apemind.exe"
KB = "cold848aad8f57412ce"
DIR = "bid_packs"
OUT = "bid_packs/_upload_result.json"


def docs():
    p = subprocess.run([CLI, "document", "list", "--kb", KB, "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return set()
    try:
        d = json.loads(p.stdout)["data"]
        items = d if isinstance(d, list) else d.get("items", [])
        return {x.get("name") for x in items}
    except Exception:
        return set()


def upload(path):
    p = subprocess.run([CLI, "document", "upload", "--file", path,
                        "--kb", KB, "--wait", "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return None, (p.stderr or p.stdout)[-300:]
    try:
        d = json.loads(p.stdout)["data"]
        return d, None
    except Exception as e:
        return None, "解析失败 %s: %s" % (e, p.stdout[-200:])


def main():
    files = sorted(f for f in os.listdir(DIR) if f.endswith((".docx", ".xlsx")))
    already = docs()
    res = {"kb": KB, "uploaded": [], "skipped": [], "failed": []}
    print("待传 %d 份，库内已有 %d 份" % (len(files), len(already)))

    for i, f in enumerate(files, 1):
        if f in already:
            res["skipped"].append(f)
            print("[%2d/%d] 跳过（已存在）%s" % (i, len(files), f))
            continue
        d, err = upload(os.path.join(DIR, f))
        if d is None:
            res["failed"].append({"file": f, "error": err})
            print("[%2d/%d] 失败 %s :: %s" % (i, len(files), f, err))
            continue
        res["uploaded"].append({"file": f, "doc_id": d.get("id"),
                                "status": d.get("status"),
                                "vector": d.get("vector_index_status"),
                                "fulltext": d.get("fulltext_index_status"),
                                "windows": d.get("total_windows")})
        print("[%2d/%d] %s  doc=%s status=%s vec=%s ft=%s windows=%s"
              % (i, len(files), f, d.get("id"), d.get("status"),
                 d.get("vector_index_status"), d.get("fulltext_index_status"),
                 d.get("total_windows")))

    io.open(OUT, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print("\n已传 %d，跳过 %d，失败 %d → %s"
          % (len(res["uploaded"]), len(res["skipped"]), len(res["failed"]), OUT))
    return 0 if not res["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
