# -*- coding: utf-8 -*-
"""本地静态核验：从原始 docx 生成客观参照基准（不联网、不改源文件）。

用途：为 L1 题库提供可人工核对的"标准答案线索"，避免凭印象判定 AI 回答。
输出 sgcc_ground_truth.json。
"""
import os, re, json, zipfile, collections

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
EXPAND = os.path.join(ROOT, "国网样本_展开")
OUT = os.path.join(ROOT, "sgcc_ground_truth.json")

KW = ["资格预审", "资格后审", "型式试验", "检测报告", "业绩", "型号", "品牌",
      "排斥", "否决投标", "否决其投标", "废标", "最高限价", "投标保证金",
      "履约保证金", "质保期", "交货期", "评标办法", "评分标准", "异议", "投诉",
      "打分表", "评分表", "评标报告", "技术得分"]


def docx_paras(p):
    try:
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception as e:
        return []
    xml = re.sub(r"</w:p>", "\n", xml)
    txt = re.sub(r"<[^>]+>", "", xml)
    return [s.strip() for s in txt.split("\n") if s.strip()]


def main():
    m = json.load(open(os.path.join(EXPAND, "manifest.json"), encoding="utf-8"))
    files = [x for x in m["items"] if x["kind"] == "file"]
    out = {"source": "本地只读解析（未联网、未上传）", "generated_at": ""}

    # 1) 库内是否存在评标域文件（V6 故意失败题的客观依据）
    forbidden = ["打分", "评分表", "评标报告", "技术得分", "投标人", "投标文件",
                 "评标委员会", "开标记录"]
    hits = [os.path.basename(x["path"]) for x in files
            if any(k in os.path.basename(x["path"]) for k in forbidden)]
    out["v6_evidence"] = {
        "total_files": len(files),
        "filenames_matching_bid_evaluation": hits,
        "conclusion": "文件名层面无评标报告/打分表/投标文件" if not hits else "存在疑似文件，需复核",
    }

    # 2) S1 同一标包两版采购文件：真实差异（V1 客观参照）
    s1 = [x for x in files if x["batch"] == "S1_1525K1" and x["ext"] == ".docx"
          and "采购文件" in os.path.basename(x["path"])]
    pkg = s1[0]["path"].split("/")[1] if s1 else None
    pair = [x for x in s1 if x["path"].startswith("S1_1525K1/" + pkg + "/")]
    pair.sort(key=lambda x: os.path.basename(x["path"]))
    out["v1_pair_package"] = pkg
    out["v1_pair"] = []
    for x in pair:
        p = os.path.join(EXPAND, x["path"].replace("/", os.sep))
        paras = docx_paras(p)
        body = "\n".join(paras)
        counts = {k: body.count(k) for k in KW if body.count(k) > 0}
        samples = {}
        for k in ["型式试验", "检测报告", "业绩", "型号", "否决投标", "最高限价"]:
            ss = [s[:180] for s in paras if k in s][:4]
            if ss:
                samples[k] = ss
        out["v1_pair"].append({
            "file": os.path.basename(x["path"]),
            "sha1": x["sha1"], "size": x["size"],
            "paragraphs": len(paras), "chars": len(body),
            "keyword_counts": counts, "clause_samples": samples,
        })

    # 3) 全库文件名与去重概览
    h = collections.Counter(x["sha1"] for x in files)
    out["corpus"] = {
        "files": len(files), "unique_by_sha1": len(h),
        "duplicate_copies": len(files) - len(h),
        "ext_counts": dict(collections.Counter(x["ext"] for x in files)),
    }
    import time
    out["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SAVED", OUT)
    print("V6 filename hits:", hits)
    for v in out["v1_pair"]:
        print("PAIR", v["file"][:50], "paras", v["paragraphs"], "chars", v["chars"])
        print("  counts", v["keyword_counts"])


if __name__ == "__main__":
    main()
