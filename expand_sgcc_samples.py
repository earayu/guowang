# -*- coding: utf-8 -*-
"""只读展开两份国网招标文件包（四层嵌套）到工作区目录。

约束：
- 桌面源文件只读，绝不改动；
- 不脱敏：原样写出全部字节，不删不改内容；
- 生成 manifest.json 供后续按格式白名单筛选上传。
"""
import os, io, json, zipfile, glob, hashlib, collections

DESK = r"C:\Users\linkz\Desktop"
OUT = r"C:\Users\linkz\WorkBuddy\PC办公\国网样本_展开"
MAX_DEPTH = 7
BAD = '<>:"/\\|?*'


def dec(n):
    """zip 内文件名 CP437/GBK 混排解码回退。"""
    try:
        return n.encode("cp437").decode("gbk")
    except Exception:
        return n


def safe(n):
    s = "".join("_" if c in BAD else c for c in n)
    return s.strip().strip(".") or "unnamed"


def walk(data, parts, out, manifest, batch, depth=0, chain=""):
    """递归展开一个 zip 的字节流。parts 为路径片段列表。"""
    if depth > MAX_DEPTH:
        manifest.append({"path": "/".join(parts), "kind": "depth_stop", "batch": batch})
        return
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception as e:
        manifest.append({"path": "/".join(parts), "kind": "zip_error",
                         "error": f"{type(e).__name__}: {e}", "batch": batch})
        return
    with z:
        for info in z.infolist():
            name = dec(info.filename)
            nm = safe(os.path.basename(name.rstrip("/")))
            if not nm:
                continue
            if info.is_dir():
                continue
            blob = z.read(info.filename)
            subparts = parts + ([nm] if not name.endswith("/") else [])
            if name.lower().endswith(".zip"):
                manifest.append({"path": "/".join(subparts), "kind": "nested_zip",
                                 "batch": batch, "size": len(blob),
                                 "chain": chain + ">" + nm})
                walk(blob, subparts[:-1] + [nm[:-4]], out, manifest, batch,
                     depth + 1, chain + ">" + nm)
            else:
                rel = os.path.join(*subparts)
                dst = os.path.join(out, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                # 同名冲突时不覆盖，自动加后缀
                if os.path.exists(dst):
                    base, ext = os.path.splitext(dst)
                    k = 2
                    while os.path.exists(f"{base}__{k}{ext}"):
                        k += 1
                    dst = f"{base}__{k}{ext}"
                with open(dst, "wb") as f:
                    f.write(blob)
                manifest.append({
                    "path": os.path.relpath(dst, OUT).replace("\\", "/"),
                    "kind": "file", "batch": batch,
                    "size": len(blob),
                    "ext": os.path.splitext(nm)[1].lower(),
                    "sha1": hashlib.sha1(blob).hexdigest()[:12],
                    "chain": chain + ">" + nm,
                })


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    zips = sorted(glob.glob(os.path.join(DESK, "*.zip")))
    print("outer zips:", len(zips))
    for p in zips:
        bn = os.path.basename(p)
        batch = "S1_1525K1" if "1525K1" in bn or "受托工程" in bn else "S2_152507"
        print("=" * 70)
        print("OUTER:", bn, "| batch:", batch,
              "| MB:", round(os.path.getsize(p) / 1048576, 2))
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                name = dec(info.filename)
                if name.lower().endswith(".zip"):
                    blob = z.read(info.filename)
                    pkg = safe(os.path.basename(name)[:-4])
                    print("  PKG:", pkg[:60])
                    walk(blob, [batch, pkg], OUT, manifest, batch, 1, bn + ">" + name)
                elif not info.is_dir():
                    blob = z.read(info.filename)
                    dst = os.path.join(OUT, batch, safe(os.path.basename(name)))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with open(dst, "wb") as f:
                        f.write(blob)
                    manifest.append({
                        "path": os.path.relpath(dst, OUT).replace("\\", "/"),
                        "kind": "file", "batch": batch, "size": len(blob),
                        "ext": os.path.splitext(name)[1].lower(),
                        "sha1": hashlib.sha1(blob).hexdigest()[:12],
                        "chain": bn + ">" + name,
                    })

    files = [m for m in manifest if m["kind"] == "file"]
    exts = collections.Counter(m["ext"] for m in files)
    batches = collections.Counter(m["batch"] for m in files)
    print("=" * 70)
    print("TOTAL files:", len(files), "| MB:",
          round(sum(m["size"] for m in files) / 1048576, 2))
    print("batches:", dict(batches))
    print("exts:", dict(exts))
    print("errors:", [m for m in manifest if m["kind"] in ("zip_error", "depth_stop")])
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"outer_zips": [os.path.basename(p) for p in zips],
                   "file_count": len(files),
                   "total_bytes": sum(m["size"] for m in files),
                   "exts": dict(exts), "batches": dict(batches),
                   "items": manifest}, f, ensure_ascii=False, indent=1)
    print("SAVED manifest.json")


if __name__ == "__main__":
    main()
